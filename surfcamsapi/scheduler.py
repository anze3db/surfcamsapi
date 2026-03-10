import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 2 * 60 * 60  # 2 hours


async def check_cams():
    from django.conf import settings

    from cams.models import Cam

    cams = Cam.objects.all()

    async def check_cam_status(cam):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    cam.url,
                    headers={
                        "Referer": settings.P_REFERER,
                    }
                    if cam.proxy
                    else {},
                    timeout=10.0,
                )
                response.raise_for_status()
                if cam.offline_since is not None:
                    cam.offline_since = None
        except (httpx.RequestError, httpx.HTTPStatusError):
            from django.utils import timezone

            if cam.offline_since is None:
                cam.offline_since = timezone.now()
        return cam

    cam_list = [cam async for cam in cams]
    for i in range(0, len(cam_list), 10):
        batch = cam_list[i : i + 10]
        await asyncio.gather(*(check_cam_status(cam) for cam in batch))

    await Cam.objects.abulk_update(cam_list, ["offline_since"])


async def run_scheduler():
    """Run check_cams in a loop. Designed to be used as a background task."""
    while True:
        try:
            await check_cams()
        except Exception:
            logger.exception("Scheduled check_cams failed")
        await asyncio.sleep(INTERVAL_SECONDS)
