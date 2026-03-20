from celery import Celery, schedules

from app.config import settings

celery = Celery(
    "intunecd",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.run_intunecd"],
)

celery.conf.update(
    task_ignore_result=False,
    task_track_started=True,
    result_extended=True,
    beat_dburi=settings.BEAT_DB_URI or settings.DATABASE_URL,
    beat_schedule={
        "intunecd.status_check": {
            "task": "app.run_intunecd.status_check",
            "schedule": schedules.crontab("45", "*", "*"),
            "args": (),
        },
    },
    timezone=settings.TIMEZONE,
)
