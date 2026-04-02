import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Tenant
from app.routers.pages import base_ctx, get_segment
from app.scheduled_tasks import (
    add_scheduled_task,
    get_scheduled_task_crontab,
    get_scheduled_tasks,
    remove_scheduled_task,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


@router.get("/schedules", response_class=HTMLResponse, include_in_schema=False)
async def schedules_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    db_tenants = db.query(Tenant).all()
    tenants_toggle = [{"id": t.id, "repo": t.repo} for t in db_tenants]

    db_schedules = get_scheduled_tasks()
    schedule_list = []
    for schedule in db_schedules:
        if schedule.name in ("celery.backend_cleanup", "intunecd.status_check"):
            continue

        tenant_name = ""
        args = json.loads(schedule.args) if schedule.args else []
        if args:
            t = db.get(Tenant, args[0])
            tenant_name = t.display_name if t else ""

        task_label = "Backup" if "backup" in schedule.task else "Update"
        crontab = get_scheduled_task_crontab(schedule.schedule_id)

        if crontab.hour == "*" and crontab.minute != "*":
            run_when = f"Run every hour at {crontab.minute} minutes past the hour"
        elif (
            crontab.hour != "*" and crontab.minute != "*" and crontab.day_of_week == "*"
        ):
            run_when = f"Run every day at {crontab.hour}:{crontab.minute}"
        elif (
            crontab.day_of_week != "*" and crontab.minute != "*" and crontab.hour != "*"
        ):
            run_when = f"Run every week on {DAYS[int(crontab.day_of_week)]} at {crontab.hour}:{crontab.minute}"
        else:
            run_when = "Custom schedule"

        schedule_list.append(
            {
                "name": schedule.name,
                "task": task_label,
                "tenant": tenant_name,
                "run_when": run_when,
                "run_count": schedule.total_run_count,
            }
        )

    ctx = base_ctx(request, db, user)
    ctx.update(
        {
            "segment": get_segment(request),
            "schedules": schedule_list,
            "tenants": db_tenants,
            "tenants_toggle": tenants_toggle,
        }
    )
    return templates.TemplateResponse("pages/schedules.html", ctx)


@router.post("/schedules/add", include_in_schema=False)
async def add_schedule(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    form = await request.form()
    schedule_name = form.get("display_name", "").strip()
    schedule_tenant_id = form.get("schedule_tenant", "").strip()
    schedule_type = form.get("schedule_type")
    schedule_hourly = form.get("schedule_hourly")
    schedule_daily = form.get("schedule_daily")
    schedule_weekly = form.get("schedule_weekly")
    time_of_day = form.get("timeOfDay", "00:00")
    day_of_week = form.get("dayOfWeek", "0")
    time_of_day_hourly = form.get("timeOfDayHourly", "0")

    if not schedule_name:
        return RedirectResponse(url="/schedules", status_code=303)

    try:
        tenant_id_int = int(schedule_tenant_id)
    except (ValueError, TypeError):
        return RedirectResponse(url="/schedules", status_code=303)

    time_parts = time_of_day.split(":")
    if len(time_parts) != 2 or not time_parts[0].isdigit() or not time_parts[1].isdigit():
        time_parts = ["0", "0"]

    task_path = (
        "app.run_intunecd.run_intunecd_backup"
        if schedule_type == "backup"
        else "app.run_intunecd.run_intunecd_update"
    )

    if schedule_hourly == "true":
        cron = {"minute": time_of_day_hourly, "hour": "*"}
    elif schedule_weekly == "true":
        cron = {
            "minute": time_parts[1],
            "hour": time_parts[0],
            "day_of_week": day_of_week,
        }
    else:
        cron = {"minute": time_parts[1], "hour": time_parts[0]}

    tenant = db.get(Tenant, tenant_id_int)
    if tenant and tenant.new_branch == "true":
        args = [schedule_tenant_id, tenant.new_branch]
    elif schedule_type == "update":
        args = [schedule_tenant_id]
    else:
        args = [schedule_tenant_id, ""]

    add_scheduled_task(cron, schedule_name, task_path, args)
    return RedirectResponse(url="/schedules", status_code=303)


@router.get("/schedules/delete/{name}", include_in_schema=False)
async def delete_schedule(
    name: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    remove_scheduled_task(name)
    return RedirectResponse(url="/schedules", status_code=303)
