import httpx
from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import render
from ninja import Field, NinjaAPI, Schema

from cams.models import Cam, Category
from surfline.urls import SurflineFetcher

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


@api.get("/cams/{cam_id}")
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
