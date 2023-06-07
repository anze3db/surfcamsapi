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
    baseurl = "https://services.surfline.com/kbyg/spots/forecasts/tides"
    tides = []
    async with httpx.AsyncClient() as client:
        response = await client.get(
            baseurl,
            timeout=5.0,
            params={
                "spotId": "5842041f4e65fad6a7708bc0",
                "days": 2,
            },
        )
        json = response.json()
        for tide in json["data"]["tides"]:
            if tide["type"] == "NORMAL":
                continue
            tides.append(
                {
                    "date": datetime.utcfromtimestamp(
                        tide["timestamp"] + tide["utcOffset"] * 3600
                    ),
                    "type": tide["type"],
                    "height": str(tide["height"])
                    + json["associated"]["units"]["tideHeight"],
                }
            )
        return render(request, "detail.html", {"cam": cam, "tides": tides})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/cams/<int:cam_id>/", get_detail, name="cam_detail"),
    path("api/", api.urls),
]
