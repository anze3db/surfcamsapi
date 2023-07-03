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
from django.contrib import admin
from django.db.models import Prefetch
from django.shortcuts import render
from django.urls import path

from api.urls import api
from cams.models import Cam, Category
from surfline.urls import get_surfline_data


async def get_full_detail(request, cam_id: int):
    cam = await Cam.objects.aget(id=cam_id)
    related_cams = await cam.related_cams()

    return render(
        request,
        "fulldetail.html",
        {
            "cam": cam,
            "related_cams": related_cams,
        },
    )


async def cams(request):
    categories = [
        cat
        async for cat in Category.objects.all()
        .prefetch_related(
            Prefetch("cam_set", queryset=Cam.objects.order_by("categorycam__order"))
        )
        .order_by("order")
    ]
    return render(request, "cams.html", {"categories": list(categories)})


urlpatterns = [
    path("", cams, name="cams"),
    path("cams/<int:cam_id>/", get_full_detail, name="cam_full_detail"),
    path("surfline/<int:cam_id>/", get_surfline_data, name="surfline_detail"),
    path("admin/", admin.site.urls),
    path("api/index", cams),  # TODO: remove soon
    path("api/cams/<int:cam_id>/full", get_full_detail),  # TODO: remove soon
    path("api/", api.urls),
]
