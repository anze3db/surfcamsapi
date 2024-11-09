proc_name = "surfcams"
bind = "unix:gunicorn.sock"
workers = 1
threads = 4
worker_class = "uvicorn.workers.UvicornWorker"
