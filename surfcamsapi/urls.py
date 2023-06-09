"""
URL configuration for surfcamsapi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import asyncio
from datetime import datetime

import httpx
from django.conf import settings
from django.contrib import admin
from django.db.models import Prefetch
from django.shortcuts import render
from django.urls import path
from ninja import Field, NinjaAPI, Schema

from cams.models import Cam, Category

api = NinjaAPI()


class CamSchema(Schema):
    title: str
    subTitle: str = Field(..., alias="subtitle")
    url: str
    titleColor: str = Field(..., alias="title_color")
    subTitleColor: str = Field(..., alias="subtitle_color")
    backgroundColor: str = Field(..., alias="background_color")
    detailUrl: str = Field(..., alias="detail_url")


class CategoriesSchema(Schema):
    title: str
    color: str
    cams: list[CamSchema] = Field(..., alias="cam_set")


class HealthSchema(Schema):
    message: str


@api.exception_handler(AssertionError)
def service_unavailable(request, exc):
    return api.create_response(
        request,
        {"message": "Please retry later"}
        if not settings.DEBUG
        else {"message": str(exc)},
        status=503,
    )


class CamsSchema(Schema):
    categories: list[CategoriesSchema]


@api.get("/cams.json", response=CamsSchema)
async def cams(request):
    categories = [
        cat
        async for cat in Category.objects.all().prefetch_related(
            Prefetch("cam_set", queryset=Cam.objects.order_by("categorycam__order"))
        )
    ]

    return {"categories": list(categories)}


@api.get("/health", response=HealthSchema)
async def health(request):
    assert await Category.objects.acount() > 0, "Not enough categories"
    return {"message": "ok"}


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
                    "speed": d["speed"],
                    "gust": d["gust"],
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
            res.append(
                {
                    "date": date,
                    "min": d["surf"]["min"],
                    "max": d["surf"]["max"],
                    "human": d["surf"]["humanRelation"],
                    "score": d["surf"]["optimalScore"],
                    "primary_swell_size": d["swells"][0]["height"],
                    "primary_swell_period": d["swells"][0]["period"],
                    "primary_swell_direction": d["swells"][0]["direction"],
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


async def get_detail(request, cam_id: int):
    cam = await Cam.objects.aget(id=cam_id)
    async with httpx.AsyncClient() as client:
        fetcher = SurflineFetcher(cam.spot_id, client)
        tides, sunlight, wind, waves = await fetcher.fetch_all()

    return render(
        request,
        "detail.html",
        {
            "cam": cam,
            "tides": tides,
            "sunlight": sunlight,
            "wind_and_waves": zip(wind, waves),
        },
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/cams/<int:cam_id>/", get_detail, name="cam_detail"),
    path("api/", api.urls),
]
