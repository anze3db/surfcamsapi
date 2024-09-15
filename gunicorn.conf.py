bind = "unix:gunicorn.sock"
workers = 1
threads = 4
proc_name = "surfcams"
worker_class = "uvicorn.workers.UvicornWorker"
pidfile = "gunicorn.pid"
