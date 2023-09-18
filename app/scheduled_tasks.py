import json

from sqlalchemy_celery_beat.models import PeriodicTask, CrontabSchedule
from sqlalchemy_celery_beat.session import SessionManager
from app import app_config

session_manager = SessionManager()
engine, Session = session_manager.create_session(app_config.BEAT_DB_URI)
schedule_session = Session()


def add_scheduled_task(CRON, NAME, TASK, ARGS):
    schedule = CrontabSchedule(
        minute=CRON["minute"],
        hour=CRON["hour"],
        day_of_week=CRON.get("day_of_week", "*"),
        day_of_month="*",
        month_of_year="*",
        timezone=app_config.TIMEZONE,
    )

    schedule_session.add(schedule)
    schedule_session.commit()

    task = PeriodicTask(
        schedule_model=schedule,
        name=NAME,
        task=TASK,
        args=json.dumps(ARGS),
    )

    schedule_session.add(task)
    schedule_session.commit()


def remove_scheduled_task(NAME):
    task = schedule_session.query(PeriodicTask).filter_by(name=NAME).first()
    schedule_session.delete(task)

    # Remove schedule if no other tasks are using it
    schedule = schedule_session.query(CrontabSchedule).filter_by(id=task.schedule_id).first()
    if not schedule_session.query(PeriodicTask).filter_by(schedule_id=schedule.id).first():
        schedule_session.delete(schedule)

    schedule_session.commit()


def get_scheduled_tasks():
    tasks = schedule_session.query(PeriodicTask).all()
    return tasks


def get_scheduled_task_crontab(id):
    schedule = schedule_session.query(CrontabSchedule).filter_by(id=id).first()
    return schedule
