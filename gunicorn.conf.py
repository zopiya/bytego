# Gunicorn Configuration for ByteGo
import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000  # Restart workers after N requests (prevents memory leaks)
max_requests_jitter = 50
timeout = 120  # 2 minutes for large file uploads
keepalive = 5

# Logging
accesslog = "-"  # stdout
errorlog = "-"  # stderr
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "bytego"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None

# Preload app for better performance
preload_app = True

# Graceful timeout
graceful_timeout = 30


def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting ByteGo server...")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading ByteGo...")


def when_ready(server):
    """Called just after the server is started."""
    server.log.info(f"ByteGo is ready. Workers: {workers}")


def on_exit(server):
    """Called just before exiting Gunicorn."""
    server.log.info("ByteGo server shutting down...")
