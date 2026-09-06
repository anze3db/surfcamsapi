import asyncio
import json
import logging
from datetime import UTC, datetime

import stamina
from curl_cffi import AsyncSession
from curl_cffi.requests.exceptions import HTTPError, RequestException
from django.shortcuts import render

from cams.models import Cam

logger = logging.getLogger(__name__)

# The error page re-requests itself over htmx. Back off exponentially from
# RETRY_DELAY seconds so a lasting Surfline outage doesn't turn every open cam
# page into a request loop, and stop asking after MAX_RETRIES.
RETRY_DELAY = 3
RETRY_MAX_DELAY = 60
MAX_RETRIES = 5


def error_context(request, cam):
    try:
        attempt = max(int(request.GET.get("attempt", 0)), 0)
    except ValueError:
        attempt = 0
    if attempt >= MAX_RETRIES:
        return {"cam": cam, "give_up": True}
    return {
        "cam": cam,
        "retry_delay": min(RETRY_DELAY * 2**attempt, RETRY_MAX_DELAY),
        "next_attempt": attempt + 1,
    }


async def get_surfline_data(request, cam_id: int):
    try:
        cam = await Cam.objects.aget(id=cam_id)
    except Cam.DoesNotExist:
        return render(request, "surfline-error.html", {"message": "Cam not found"})
    forecast = await fetch_forecast(cam)
    if forecast is None:
        return render(request, "surfline-error.html", error_context(request, cam))
    return render(request, "surfline.html", forecast)


async def fetch_forecast(cam):
    """Build the surfline.html context for a cam.

    Returns None when the cam has a spot but every endpoint failed, so callers
    can show an error instead.
    """
    async with AsyncSession(impersonate="chrome") as client:
        fetcher = SurflineFetcher(cam.spot_id, client)
        tides, sunlight, wind, waves = await fetcher.fetch_all()

    # A partial forecast is still worth showing; only bail out when the spot has
    # data to fetch and every single endpoint failed.
    if cam.spot_id and not any((tides, sunlight, wind, waves)):
        return None

    # Group wind/wave data by day, keyed on the timestamp they share so that one
    # missing endpoint leaves holes rather than misaligning the rows.
    wind_by_date = {w["date"]: w for w in wind}
    waves_by_date = {w["date"]: w for w in waves}
    forecast_days = []
    current_day = None
    for date in sorted(wind_by_date.keys() | waves_by_date.keys()):
        if current_day is None or date.date() != current_day["date"].date():
            current_day = {"date": date, "rows": [], "sunlight": []}
            forecast_days.append(current_day)
        current_day["rows"].append(
            {
                "date": date,
                "wind": wind_by_date.get(date),
                "wave": waves_by_date.get(date),
            }
        )

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

    return {
        "forecast_days": forecast_days,
        "chart_days_json": json.dumps(chart_days),
        "tide_unit": tides["unit"] if tides else "",
    }


class SurflineFetcher:
    def __init__(self, spot_id: str, client):
        self.base_url = "https://services.surfline.com/kbyg/spots/forecasts/"
        self.client = client
        self.day_params = {"spotId": spot_id, "days": 3}
        self.spot_id = spot_id

    # Retries back off exponentially (0.5s, 1s, 2s... jittered) and are capped
    # by wait_max, so a slow Surfline never holds the request open for long.
    @stamina.retry(on=RequestException, attempts=3, wait_initial=0.5, wait_max=5)
    async def fetch(self, endpoint, params=None):
        response = await self.client.get(
            self.base_url + endpoint,
            timeout=5.0,
            params=params or self.day_params,
        )
        if response.status_code != 200:
            raise HTTPError(f"Non-200 response ({response.status_code}) for {endpoint}")
        return response.json()

    async def fetch_tides(self):
        tide_json = await self.fetch("tides", {"spotId": self.spot_id, "days": 4})
        unit = tide_json["associated"]["units"]["tideHeight"].lower()
        today = datetime.now(UTC).date()
        chart_points = []
        extremes = []
        for tide in tide_json["data"]["tides"]:
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

    async def fetch_sunlight(self):
        sunlight_json = await self.fetch("sunlight")

        today = datetime.now(UTC).date()
        chart_data = []
        display_days = []

        for sun in sunlight_json["data"]["sunlight"]:
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

    async def fetch_wind(self):
        res = []
        for d in (await self.fetch("wind"))["data"]["wind"]:
            date = datetime.fromtimestamp(d["timestamp"] + d["utcOffset"] * 3600, tz=UTC)
            if date.hour % 3 != 0 or date.hour < 4:
                continue
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

    async def fetch_waves(self):
        # Surfline retired /forecasts/wave: surf heights and swells now live on
        # two endpoints, joined back together here on their shared timestamp.
        surf_json, swell_json = await asyncio.gather(
            self.fetch("surf"),
            self.fetch("swells"),
        )
        swells_by_timestamp = {s["timestamp"]: s for s in swell_json["data"]["swells"]}
        res = []
        for d in surf_json["data"]["surf"]:
            date = datetime.fromtimestamp(d["timestamp"] + d["utcOffset"] * 3600, tz=UTC)
            if date.hour % 3 != 0 or date.hour < 4:
                continue
            swell = swells_by_timestamp.get(d["timestamp"], {})
            swells = sorted(
                swell.get("swells", []), key=lambda x: x["impact"], reverse=True
            )
            primary = swells[0] if swells else {}
            res.append(
                {
                    "date": date,
                    "min": d["surf"]["min"],
                    "max": d["surf"]["max"],
                    "human": d["surf"]["humanRelation"],
                    "primary_swell_size": primary.get("height"),
                    "primary_swell_period": primary.get("period"),
                    "primary_swell_direction": primary.get("direction"),
                    "power": swell.get("power"),
                }
            )
        return res

    async def fetch_safely(self, name, coro, default):
        try:
            return await coro
        except Exception:
            logger.warning(
                "Surfline %s fetch failed for spot %s", name, self.spot_id, exc_info=True
            )
            return default

    async def fetch_all(self):
        if not self.spot_id:
            return None, None, [], []
        return await asyncio.gather(
            self.fetch_safely("tides", self.fetch_tides(), None),
            self.fetch_safely("sunlight", self.fetch_sunlight(), None),
            self.fetch_safely("wind", self.fetch_wind(), []),
            self.fetch_safely("waves", self.fetch_waves(), []),
        )
