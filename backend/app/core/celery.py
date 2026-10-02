from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "matchlambda",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "hourly-refresh-fixtures-and-quotes": {
            "task": "app.tasks.pipeline.hourly_pipeline_task",
            "schedule": crontab(minute=0),  # every hour
        },
    },
)
