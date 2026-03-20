from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_api_key
from app.scheduled_tasks import get_scheduled_tasks, remove_scheduled_task
from app.schemas import ScheduleResponse

router = APIRouter(tags=["schedules"])


@router.get("/schedules", dependencies=[Depends(require_api_key)])
def get_schedules(db: Annotated[Session, Depends(get_db)]):
    tasks = get_scheduled_tasks()
    return [
        {
            "id": t.id,
            "name": t.name,
            "task": t.task,
            "args": t.args,
            "schedule_id": t.schedule_id,
            "last_run_at": t.last_run_at,
            "total_run_count": t.total_run_count,
            "date_changed": t.date_changed,
        }
        for t in tasks
    ]


@router.delete("/schedules/{name}", dependencies=[Depends(require_api_key)])
def delete_schedule(name: str, db: Annotated[Session, Depends(get_db)]):
    remove_scheduled_task(name)
    return {"success": True, "message": f"Schedule '{name}' deleted"}
