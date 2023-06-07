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


class DetailSchema(Schema):
    id: int
    tides: dict


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


async def get_detail(request, cam_id: int):
    cam = await Cam.objects.aget(id=cam_id)
    baseurl = "https://services.surfline.com/kbyg/spots/forecasts/"
    tides = []
    sunlight = []
    async with httpx.AsyncClient() as client:
        tides_request = client.get(
            baseurl + "tides",
            timeout=5.0,
            params={
                "spotId": "5842041f4e65fad6a7708bc0",
                "days": 2,
            },
        )
        sunlight_request = client.get(
            baseurl + "sunlight",
            timeout=5.0,
            params={
                "spotId": "5842041f4e65fad6a7708bc0",
                "days": 1,
            },
        )
        tide_response, sunlight_response = await asyncio.gather(
            tides_request, sunlight_request
        )
        for tide in tide_response.json()["data"]["tides"]:
            if tide["type"] == "NORMAL":
                continue

            date = datetime.utcfromtimestamp(
                tide["timestamp"] + tide["utcOffset"] * 3600
            )

            if date.day != datetime.utcnow().day:
                continue

            tides.append(
                {
                    "date": date,
                    "type": tide["type"],
                    "height": str(tide["height"])
                    + tide_response.json()["associated"]["units"]["tideHeight"],
                }
            )
        for sun in sunlight_response.json()["data"]["sunlight"]:
            sunlight = [
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

        return render(
            request, "detail.html", {"cam": cam, "tides": tides, "sunlight": sunlight}
        )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/cams/<int:cam_id>/", get_detail, name="cam_detail"),
    path("api/", api.urls),
]
