import os
import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.models import Tenant
from app.run_intunecd import run_intunecd_backup, run_intunecd_update
from app.socket_tasks import emit_message, update_tenant_status_data

router = APIRouter()


@router.post("/intunecd/run")
async def run_intunecd(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    body = await request.json()
    tenant_id = body["tenant_id"]
    task_type = body["task_type"]

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return JSONResponse({"error": "Tenant not found"}, status_code=404)

    if task_type == "backup":
        result = run_intunecd_backup.delay(tenant_id, tenant.new_branch)
    else:
        result = run_intunecd_update.delay(tenant_id)

    emit_message(f"Waiting for {task_type} to start", "pending", result.id, tenant_id)
    update_tenant_status_data(tenant, "pending", f"Waiting for {task_type} to start")
    db.commit()

    return JSONResponse({"task_id": result.id}, status_code=202)


@router.post("/intunecd/cancel")
async def cancel_intunecd(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    body = await request.json()
    tenant_id = body["tenant_id"]
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return JSONResponse({"error": "Tenant not found"}, status_code=404)

    try:
        from celery import Celery
        celery_app = Celery(broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
        celery_app.control.revoke(tenant.last_task_id, terminate=True)
        emit_message("Task cancelled", "cancelled", tenant.last_task_id, tenant_id)
        update_tenant_status_data(tenant, "cancelled", "Task cancelled")
        db.commit()
        return JSONResponse({"status": "success"}, status_code=202)
    except Exception as e:
        emit_message("Error cancelling task", "error", tenant.last_task_id, tenant_id)
        update_tenant_status_data(tenant, "error", "Error cancelling task")
        db.commit()
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/intunecd/purge")
async def purge_intunecd(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    try:
        from celery import Celery
        celery_app = Celery(broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
        celery_app.control.purge()

        db_tenants = db.query(Tenant).all()
        task_ids = [t.last_task_id for t in db_tenants if t.last_task_id]
        if task_ids:
            celery_app.control.revoke(task_ids, terminate=True)

        for tenant in db_tenants:
            tenant.last_task_id = None
            tenant.last_update_status = "unknown"
            tenant.last_update_message = None

        db.commit()

        if os.path.exists("/intunecd/tmp"):
            shutil.rmtree("/intunecd/tmp")

        return JSONResponse({"status": "success"}, status_code=202)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
