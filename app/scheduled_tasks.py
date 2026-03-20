import json
import os

from sqlalchemy_celery_beat.models import CrontabSchedule, PeriodicTask
from sqlalchemy_celery_beat.session import SessionManager

from app.config import settings

_beat_db_uri = settings.BEAT_DB_URI or settings.DATABASE_URL

session_manager = SessionManager()
engine, Session = session_manager.create_session(_beat_db_uri)
schedule_session = Session()


def add_scheduled_task(cron: dict, name: str, task: str, args: list) -> None:
    schedule = CrontabSchedule(
        minute=cron["minute"],
        hour=cron["hour"],
        day_of_week=cron.get("day_of_week", "*"),
        day_of_month="*",
        month_of_year="*",
        timezone=settings.TIMEZONE,
    )
    schedule_session.add(schedule)
    schedule_session.commit()

    periodic = PeriodicTask(
        schedule_model=schedule,
        name=name,
        task=task,
        args=json.dumps(args),
    )
    schedule_session.add(periodic)
    schedule_session.commit()


def remove_scheduled_task(name: str) -> None:
    task = schedule_session.query(PeriodicTask).filter_by(name=name).first()
    if not task:
        return
    schedule_id = task.schedule_id
    schedule_session.delete(task)

    schedule = schedule_session.query(CrontabSchedule).filter_by(id=schedule_id).first()
    if schedule and not schedule_session.query(PeriodicTask).filter_by(schedule_id=schedule.id).first():
        schedule_session.delete(schedule)

    schedule_session.commit()


def get_scheduled_tasks():
    return schedule_session.query(PeriodicTask).all()


def get_scheduled_task_crontab(schedule_id: int):
    return schedule_session.query(CrontabSchedule).filter_by(id=schedule_id).first()
