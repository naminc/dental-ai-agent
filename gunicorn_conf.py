"""Gunicorn configuration for the aaPanel production process.

This file must stay side-effect free: it only reads process environment values
and never imports the FastAPI application or contacts external services.
"""

import os


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw_value!r}") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be greater than zero, got {value}")
    return value


APP_DIR = os.getenv("APP_DIR", "/www/wwwroot/dental-ai").rstrip("/")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = _positive_int("PORT", 8001)
WEB_CONCURRENCY = _positive_int("WEB_CONCURRENCY", 1)
GUNICORN_TIMEOUT = _positive_int("GUNICORN_TIMEOUT", 300)
GUNICORN_GRACEFUL_TIMEOUT = _positive_int("GUNICORN_GRACEFUL_TIMEOUT", 300)
LOG_DIR = os.getenv("LOG_DIR", "/www/wwwlogs/python/dental-ai").rstrip("/")

if PORT > 65535:
    raise RuntimeError(f"PORT must be between 1 and 65535, got {PORT}")

# Process and application settings
chdir = APP_DIR
bind = f"{HOST}:{PORT}"
workers = WEB_CONCURRENCY
threads = 1
user = "www"
worker_class = "uvicorn.workers.UvicornWorker"
preload_app = False

# Lifecycle and connection settings
timeout = GUNICORN_TIMEOUT
graceful_timeout = GUNICORN_GRACEFUL_TIMEOUT
keepalive = 75
max_requests = 1000
max_requests_jitter = 100

# Files and logging. The deploy runbook creates LOG_DIR before startup.
pidfile = f"{APP_DIR}/gunicorn.pid"
accesslog = f"{LOG_DIR}/gunicorn_access.log"
errorlog = f"{LOG_DIR}/gunicorn_error.log"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
capture_output = True
