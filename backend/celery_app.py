"""
Celery Application Configuration
Location: backend/celery_app.py

Configures Celery with Redis as both broker and result backend.
Import tasks from this module to ensure they're registered.

Start worker:
    celery -A celery_app worker --loglevel=info --pool=solo

Note: --pool=solo is required because our agents use asyncio internally.
For production, use --pool=gevent or --concurrency=N with proper async handling.
"""
from celery import Celery
from config.settings import settings

# Redis URL — default to localhost for dev
REDIS_URL = getattr(settings, 'redis_url', 'redis://localhost:6379/0')

celery_app = Celery(
    "travelq",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.celery_trip_task"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timeouts
    task_soft_time_limit=180,   # 3 minutes soft limit (raises SoftTimeLimitExceeded)
    task_time_limit=210,        # 3.5 minutes hard kill

    # Reliability
    task_acks_late=True,        # Ack after task completes (not on receive)
    worker_prefetch_multiplier=1,  # One task at a time per worker

    # Result expiry
    result_expires=3600,        # 1 hour

    # Timezone
    timezone="UTC",
    enable_utc=True,
)