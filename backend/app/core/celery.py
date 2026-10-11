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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=30 * 60,
    broker_transport_options={"visibility_timeout": 60 * 60},
    beat_schedule={
        "hourly-refresh-fixtures-and-quotes": {
            "task": "app.tasks.pipeline.hourly_pipeline_task",
            "schedule": crontab(minute=0),  # every hour
        },
        "daily-league-gate-refresh": {
            "task": "app.tasks.pipeline.refresh_league_eligibility_task",
            # PRD §2.1 eligibility snapshot, off the hourly :00 slot
            "schedule": crontab(minute=15, hour=3),
        },
    },
)
