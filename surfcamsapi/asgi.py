"""
ASGI config for surfcamsapi project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

from .scheduler import start_scheduler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "surfcamsapi.settings")

# Get the ASGI application
django_application = get_asgi_application()

# Start the scheduler
scheduler = None


async def application(scope, receive, send):
    global scheduler
    if scheduler is None:
        scheduler = await start_scheduler()

    await django_application(scope, receive, send)
