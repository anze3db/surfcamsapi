import asyncio
from datetime import datetime

import httpx
from django.shortcuts import render

from cams.models import Cam


class SurflineFetcher:
    def __init__(self, spot_id: str, client):
        self.base_url = "https://services.surfline.com/kbyg/spots/forecasts/"
        self.client = client
        self.params = {"spotId": spot_id, "days": 1}
        self.day_params = {"spotId": spot_id, "days": 3}
        self.spot_id = spot_id

    async def fetch_tides(self):
        tide_response = await self.client.get(
            self.base_url + "tides",
            timeout=5.0,
            params=self.params,
        )
        res = []
        for tide in tide_response.json()["data"]["tides"]:
            if tide["type"] == "NORMAL":
                continue

            date = datetime.utcfromtimestamp(
                tide["timestamp"] + tide["utcOffset"] * 3600
            )

            if date.day != datetime.utcnow().day:
                continue

            res.append(
                {
                    "date": date,
                    "type": tide["type"],
                    "height": str(tide["height"])
                    + tide_response.json()["associated"]["units"]["tideHeight"],
                }
            )
        return res

    async def fetch_sunlight(self):
        sunlight_response = await self.client.get(
            self.base_url + "sunlight",
            timeout=5.0,
            params=self.params,
        )

        for sun in sunlight_response.json()["data"]["sunlight"]:
            return [
                {
                    "date": datetime.utcfromtimestamp(
                        sun["dawn"] + sun["dawnUTCOffset"] * 3600
                    ),
                    "type": "🌘 First Light",
                },
                {
                    "date": datetime.utcfromtimestamp(
                        sun["sunrise"] + sun["sunriseUTCOffset"] * 3600
                    ),
                    "type": "🌖 Sunrise",
                },
                {
                    "date": datetime.utcfromtimestamp(
                        sun["sunset"] + sun["sunsetUTCOffset"] * 3600
                    ),
                    "type": "🌔 Sunset",
                },
                {
                    "date": datetime.utcfromtimestamp(
                        sun["dusk"] + sun["duskUTCOffset"] * 3600
                    ),
                    "type": "🌒 Last Light",
                },
            ]

    async def fetch_wind(self):
        wind_response = await self.client.get(
            self.base_url + "wind",
            timeout=5.0,
            params=self.day_params,
        )
        res = []
        data = wind_response.json()["data"]["wind"]
        prev_hour = 24
        for d in data:
            date = datetime.utcfromtimestamp(d["timestamp"] + d["utcOffset"] * 3600)
            if date.hour % 3 != 0 or date.hour < 4:
                continue
            if date.hour < prev_hour:
                res.append({"date": date, "break": True})
            prev_hour = date.hour
            res.append(
                {
                    "date": date,
                    "direction": d["direction"],
                    "direction_type": d["directionType"],
                    "speed": d["speed"] * 1.852,  # kts to kph
                    "gust": d["gust"] * 1.852,  # kts to kph
                    "score": d["optimalScore"],
                }
            )
        return res

    async def fetch_waves(self):
        wave_response = await self.client.get(
            self.base_url + "wave",
            timeout=5.0,
            params=self.day_params,
        )
        res = []
        data = wave_response.json()["data"]["wave"]
        prev_hour = 24
        for d in data:
            date = datetime.utcfromtimestamp(d["timestamp"] + d["utcOffset"] * 3600)
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
                }
            )
        return res

    async def fetch_all(self):
        if not self.spot_id:
            return [], [], [], []
        return await asyncio.gather(
            self.fetch_tides(),
            self.fetch_sunlight(),
            self.fetch_wind(),
            self.fetch_waves(),
        )


async def get_surfline_data(request, cam_id: int):
    cam = await Cam.objects.aget(id=cam_id)
    async with httpx.AsyncClient() as client:
        fetcher = SurflineFetcher(cam.spot_id, client)
        try:
            tides, sunlight, wind, waves = await fetcher.fetch_all()
        except httpx.HTTPError:
            return render(request, "surfline-error.html", {"cam": cam})
    return render(
        request,
        "surfline.html",
        {
            "tides": tides,
            "sunlight": sunlight,
            "wind_and_waves": zip(wind, waves),
        },
    )
