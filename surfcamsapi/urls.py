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

import httpx
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import alogin, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import include, path

from api.urls import api
from cams.models import Cam, Category
from surfline.urls import get_surfline_data


@login_required
async def get_full_detail(request, cam_id: str):
    try:
        cam = await Cam.objects.aget(slug=cam_id)
    except Cam.DoesNotExist:
        if cam_id.isdigit():
            try:
                cam = await Cam.objects.aget(id=cam_id)
            except Cam.DoesNotExist:
                return HttpResponse("Cam not found", status=404)
        else:
            return HttpResponse("Cam not found", status=404)
    related_cams = await cam.related_cams()

    return render(
        request,
        "fulldetail.html",
        {
            "cam": cam,
            "related_cams": related_cams,
        },
    )


@login_required
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


@login_required
async def proxy(request, url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{url}",
            headers={
                "Referer": settings.P_REFERER,
            },
        )
        return HttpResponse(response.content, content_type="application/x-mpegURL")


async def login_view(request):
    if request.method == "GET":
        return render(request, "login.html")
    elif request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            await alogin(request, user)
            return redirect(request.GET.get("next", "/"))
        else:
            return render(request, "login.html", {"error": "Invalid credentials"})


urlpatterns = [
    path("", cams, name="cams"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("cams/<str:cam_id>/", get_full_detail, name="cam_full_detail"),
    path("surfline/<int:cam_id>/", get_surfline_data, name="surfline_detail"),
    path("admin/", admin.site.urls),
    path("api/index", cams),  # TODO: remove soon
    path("api/cams/<int:cam_id>/full", get_full_detail),  # TODO: remove soon
    path("api/", api.urls),
    path("p/<path:url>", proxy, name="proxy"),
]
