from uvicorn.workers import UvicornWorker


class DjangoUvicornWorker(UvicornWorker):
    # Django doesn't support the ASGI lifespan protocol. With uvicorn's default
    # "auto" it raises on every worker boot, which Sentry reports as an error.
    CONFIG_KWARGS = {**UvicornWorker.CONFIG_KWARGS, "lifespan": "off"}


proc_name = "surfcams"
bind = "unix:gunicorn.sock"
workers = 1
threads = 4
worker_class = DjangoUvicornWorker
