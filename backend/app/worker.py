"""Celery application for durable background work."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "expertise_insight",
    broker=settings.redis_url,
    include=["app.tasks.sync"],
)
celery_app.conf.update(
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    timezone="Asia/Singapore",
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=5,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "visibility_timeout": 3600,
        "socket_connect_timeout": 5,
    },
    task_publish_retry_policy={
        "max_retries": 2,
        "interval_start": 0,
        "interval_step": 0.5,
        "interval_max": 1,
    },
    beat_schedule={
        "quarterly-expertise-sync": {
            "task": "sync.enqueue_quarterly",
            "schedule": crontab(
                minute=0,
                hour=2,
                day_of_month=1,
                month_of_year="1,4,7,10",
            ),
        }
    },
)
