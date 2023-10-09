import json

from sqlalchemy_celery_beat.models import PeriodicTask, CrontabSchedule
from sqlalchemy_celery_beat.session import SessionManager
from app import app_config

session_manager = SessionManager()
engine, Session = session_manager.create_session(app_config.BEAT_DB_URI)
schedule_session = Session()


def add_scheduled_task(CRON, NAME, TASK, ARGS) -> None:
    """Add a scheduled task to the database

    Args:
        CRON (dict): a dict containing the CRON information
        NAME (str): name of the task to create
        TASK (str): the type of task to create
        ARGS (list): list of arguments to pass to the task
    """
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
    """Remove a scheduled task from the database.

    Args:
        NAME (str): name of the task to remove.
    """
    task = schedule_session.query(PeriodicTask).filter_by(name=NAME).first()
    schedule_session.delete(task)

    # Remove schedule if no other tasks are using it
    schedule = schedule_session.query(CrontabSchedule).filter_by(id=task.schedule_id).first()
    if not schedule_session.query(PeriodicTask).filter_by(schedule_id=schedule.id).first():
        schedule_session.delete(schedule)

    schedule_session.commit()


def get_scheduled_tasks():
    """Get all scheduled tasks from the database.

    Returns:
        list: the tasks from the database.
    """
    tasks = schedule_session.query(PeriodicTask).all()
    return tasks


def get_scheduled_task_crontab(id):
    """Gets a CRON schedule from the database by ID.

    Args:
        id (int): ID of the CRON schedule to get.

    Returns:
        dict: the CRON shedule from the database.
    """
    schedule = schedule_session.query(CrontabSchedule).filter_by(id=id).first()
    return schedule
