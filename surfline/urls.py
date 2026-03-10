import asyncio
import json
from datetime import UTC, datetime

import httpx
import stamina
from django.shortcuts import render

from cams.models import Cam


async def get_surfline_data(request, cam_id: int):
    try:
        cam = await Cam.objects.aget(id=cam_id)
    except Cam.DoesNotExist:
        return render(request, "surfline-error.html", {"message": "Cam not found"})
    async with httpx.AsyncClient() as client:
        fetcher = SurflineFetcher(cam.spot_id, client)
        try:
            tides, sunlight, wind, waves = await fetcher.fetch_all()
        except httpx.HTTPError:
            return render(request, "surfline-error.html", {"cam": cam})
    # Group wind/wave data by day
    forecast_days = []
    current_day = None
    for w, wv in zip(wind, waves):
        if w.get("break"):
            current_day = {"date": w["date"], "rows": [], "sunlight": []}
            forecast_days.append(current_day)
        elif current_day is not None:
            current_day["rows"].append({"wind": w, "wave": wv})

    # Attach per-day sunlight display
    if sunlight:
        for i, day in enumerate(forecast_days):
            if i < len(sunlight["display_days"]):
                day["sunlight"] = sunlight["display_days"][i]

    # Build per-day chart data (normalize minutes to 0-1440)
    chart_days = []
    for d in range(len(forecast_days)):
        day_offset = d * 1440
        if tides:
            day_points = [
                {
                    "minutes": p["minutes"] - day_offset,
                    "height": p["height"],
                    "type": p["type"],
                }
                for p in tides["chart_points"]
                if day_offset - 60 <= p["minutes"] <= day_offset + 1500
            ]
            day_extremes = [
                {**e, "minutes": e["minutes"] - day_offset}
                for e in tides["extremes"]
                if day_offset - 60 <= e["minutes"] <= day_offset + 1500
            ]
        else:
            day_points = []
            day_extremes = []

        day_sun = None
        if sunlight and d < len(sunlight["chart_data"]):
            raw = sunlight["chart_data"][d]
            day_sun = {k: v - day_offset for k, v in raw.items()}

        chart_days.append(
            {
                "chart_points": day_points,
                "extremes": day_extremes,
                "sunlight": day_sun,
            }
        )

    return render(
        request,
        "surfline.html",
        {
            "forecast_days": forecast_days,
            "chart_days_json": json.dumps(chart_days),
            "tide_unit": tides["unit"] if tides else "",
        },
    )


class SurflineFetcher:
    def __init__(self, spot_id: str, client):
        self.base_url = "https://services.surfline.com/kbyg/spots/forecasts/"
        self.client = client
        self.day_params = {"spotId": spot_id, "days": 3}
        self.spot_id = spot_id

    @stamina.retry(on=httpx.HTTPError, attempts=3)
    async def fetch_tides(self):
        tide_response = await self.client.get(
            self.base_url + "tides",
            timeout=5.0,
            params={"spotId": self.spot_id, "days": 4},
        )
        if tide_response.status_code != 200:
            raise httpx.HTTPError("Non-200 response")
        unit = tide_response.json()["associated"]["units"]["tideHeight"].lower()
        today = datetime.now(UTC).date()
        chart_points = []
        extremes = []
        for tide in tide_response.json()["data"]["tides"]:
            date = datetime.fromtimestamp(
                tide["timestamp"] + tide["utcOffset"] * 3600, tz=UTC
            )
            # Minutes relative to today's midnight
            day_diff = (date.date() - today).days
            minutes = day_diff * 1440 + date.hour * 60 + date.minute
            # Include 3 full days with buffer
            if minutes < -60 or minutes > 4380:
                continue
            chart_points.append(
                {
                    "minutes": minutes,
                    "height": tide["height"],
                    "type": tide["type"],
                }
            )
            if tide["type"] != "NORMAL":
                extremes.append(
                    {
                        "minutes": minutes,
                        "height": tide["height"],
                        "type": tide["type"],
                        "time": date.strftime("%H:%M"),
                        "label": f"{tide['height']:.2f}{unit}",
                    }
                )
        return {
            "chart_points": chart_points,
            "extremes": extremes,
            "unit": unit,
        }

    @stamina.retry(on=httpx.HTTPError, attempts=3)
    async def fetch_sunlight(self):
        sunlight_response = await self.client.get(
            self.base_url + "sunlight",
            timeout=5.0,
            params=self.day_params,
        )
        if sunlight_response.status_code != 200:
            raise httpx.HTTPError("Non-200 response")

        today = datetime.now(UTC).date()
        chart_data = []
        display_days = []

        for sun in sunlight_response.json()["data"]["sunlight"]:
            def to_date(ts, offset):
                return datetime.fromtimestamp(ts + offset * 3600, tz=UTC)

            dawn_date = to_date(sun["dawn"], sun["dawnUTCOffset"])
            day_diff = (dawn_date.date() - today).days
            day_offset = day_diff * 1440

            def to_minutes(ts, offset):
                d = datetime.fromtimestamp(ts + offset * 3600, tz=UTC)
                return day_offset + d.hour * 60 + d.minute

            chart_data.append({
                "dawn": to_minutes(sun["dawn"], sun["dawnUTCOffset"]),
                "sunrise": to_minutes(sun["sunrise"], sun["sunriseUTCOffset"]),
                "sunset": to_minutes(sun["sunset"], sun["sunsetUTCOffset"]),
                "dusk": to_minutes(sun["dusk"], sun["duskUTCOffset"]),
            })

            display_days.append([
                {"date": to_date(sun["dawn"], sun["dawnUTCOffset"]), "type": "🔅 First Light"},
                {"date": to_date(sun["sunrise"], sun["sunriseUTCOffset"]), "type": "☀️ Sunrise"},
                {"date": to_date(sun["sunset"], sun["sunsetUTCOffset"]), "type": "☀️ Sunset"},
                {"date": to_date(sun["dusk"], sun["duskUTCOffset"]), "type": "🔅 Last Light"},
            ])

        return {
            "display_days": display_days,
            "chart_data": chart_data,
        }

    @stamina.retry(on=httpx.HTTPError, attempts=3)
    async def fetch_wind(self):
        wind_response = await self.client.get(
            self.base_url + "wind",
            timeout=5.0,
            params=self.day_params,
        )
        if wind_response.status_code != 200:
            raise httpx.HTTPError("Non-200 response")
        res = []
        data = wind_response.json()["data"]["wind"]
        prev_hour = 24
        for d in data:
            date = datetime.fromtimestamp(d["timestamp"] + d["utcOffset"] * 3600, tz=UTC)
            if date.hour % 3 != 0 or date.hour < 4:
                continue
            if date.hour < prev_hour:
                res.append({"date": date, "break": True})
            prev_hour = date.hour
            direction_type = d["directionType"]
            speed = d["speed"] * 1.852  # kts to kph
            color = "black"

            class Colors:
                red = "#E44D3A"
                green = "#55AB68"
                orange = "#D8833B"

            match direction_type:
                case "Onshore" if speed < 10:
                    color = Colors.green
                case "Onshore" if speed < 30:
                    color = Colors.orange
                case "Onshore":
                    color = Colors.red
                case "Cross-shore" if speed < 20:
                    color = Colors.green
                case "Cross-shore" if speed < 40:
                    color = Colors.orange
                case "Cross-shore":
                    color = Colors.red
                case "Offshore" if speed < 30:
                    color = Colors.green
                case "Offshore":
                    color = Colors.orange
            res.append(
                {
                    "date": date,
                    "direction": d["direction"],
                    "direction_type": d["directionType"],
                    "speed": d["speed"] * 1.852,  # kts to kph
                    "gust": d["gust"] * 1.852,  # kts to kph
                    "score": d["optimalScore"],
                    "color": color,
                }
            )
        return res

    @stamina.retry(on=httpx.HTTPError, attempts=3)
    async def fetch_waves(self):
        wave_response = await self.client.get(
            self.base_url + "wave",
            timeout=5.0,
            params=self.day_params,
        )
        if wave_response.status_code != 200:
            raise httpx.HTTPError("Non-200 response")
        res = []
        data = wave_response.json()["data"]["wave"]
        prev_hour = 24
        for d in data:
            date = datetime.fromtimestamp(d["timestamp"] + d["utcOffset"] * 3600, tz=UTC)
            if date.hour % 3 != 0 or date.hour < 4:
                continue
            if date.hour < prev_hour:
                res.append({"date": date, "break": True})
            prev_hour = date.hour
            swells = sorted(d["swells"], key=lambda x: x["impact"], reverse=True)
            res.append(
                {
                    "date": date,
                    "min": d["surf"]["min"],
                    "max": d["surf"]["max"],
                    "human": d["surf"]["humanRelation"],
                    "score": d["surf"]["optimalScore"],
                    "primary_swell_size": swells[0]["height"],
                    "primary_swell_period": swells[0]["period"],
                    "primary_swell_direction": swells[0]["direction"],
                    "power": d["power"],
                }
            )
        return res

    async def fetch_all(self):
        if not self.spot_id:
            return None, None, [], []
        return await asyncio.gather(
            self.fetch_tides(),
            self.fetch_sunlight(),
            self.fetch_wind(),
            self.fetch_waves(),
        )
