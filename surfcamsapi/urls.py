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
from django.conf import settings
from django.contrib import admin
from django.db.models import Prefetch
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
def cams(request):
    categories = Category.objects.all().prefetch_related(
        Prefetch("cam_set", queryset=Cam.objects.order_by("categorycam__order"))
    )

    return {"categories": list(categories)}


@api.get("/health", response=HealthSchema)
def health(request):
    assert Category.objects.count() > 0, "Not enough categories"
    return {"message": "ok"}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
