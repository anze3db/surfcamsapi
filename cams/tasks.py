import asyncio

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from potatoq import shared_task

from cams.models import Cam


async def check_cam_status(cam):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cam.url,
                headers={"Referer": settings.P_REFERER} if cam.proxy else {},
                timeout=10.0,
            )
            response.raise_for_status()
            cam.offline_since = None
    except (httpx.RequestError, httpx.HTTPStatusError):
        if cam.offline_since is None:
            cam.offline_since = timezone.now()
    return cam


@shared_task
async def check_cams():
    """Scheduled by POTATOQ["beat_schedule"] in surfcamsapi/settings.py."""
    # The async ORM runs queries on asgiref's executor thread, out of reach of the
    # close_old_connections() potatoq runs around each task, so do it on that thread.
    await sync_to_async(close_old_connections)()
    try:
        cam_list = [cam async for cam in Cam.objects.all()]
        for i in range(0, len(cam_list), 10):
            batch = cam_list[i : i + 10]
            await asyncio.gather(*(check_cam_status(cam) for cam in batch))
        await Cam.objects.abulk_update(cam_list, ["offline_since"])
    finally:
        await sync_to_async(close_old_connections)()
