import asyncio
import datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = None


async def daily_job():
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
                # Check if the response was successful
                response.raise_for_status()
                # If cam was offline before, update it
                if cam.offline_since is not None:
                    cam.offline_since = None
        except (httpx.RequestError, httpx.HTTPStatusError):
            from django.utils import timezone

            # Only set offline_since if it's not already set
            if cam.offline_since is None:
                cam.offline_since = timezone.now()
        return cam

    # Process cams in batches of 10
    cam_list = [cam async for cam in cams]
    for i in range(0, len(cam_list), 10):
        batch = cam_list[i : i + 10]
        await asyncio.gather(*(check_cam_status(cam) for cam in batch))

    # Save all cams at once
    await Cam.objects.abulk_update(cam_list, ["offline_since"])


async def start_scheduler():
    global scheduler
    if scheduler is not None:
        return scheduler

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        daily_job,
        "interval",
        hours=2,
        next_run_time=datetime.datetime.now(),
        id="daily_job",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler
