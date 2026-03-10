"""
ASGI config for surfcamsapi project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import asyncio
import os

from django.core.asgi import get_asgi_application

from .scheduler import run_scheduler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "surfcamsapi.settings")

django_application = get_asgi_application()


async def application(scope, receive, send):
    if scope["type"] == "lifespan":
        scheduler_task = None
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                scheduler_task = asyncio.create_task(run_scheduler())
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if scheduler_task is not None:
                    scheduler_task.cancel()
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await django_application(scope, receive, send)
