import json
import os
from datetime import datetime, timedelta
from typing import Annotated

import msal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_admin, require_role
from app.models import ApiKey, SummaryAssignment, SummaryChange, Tenant
from app.tenant_data import tenant_home_data

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_segment(request: Request) -> str:
    parts = request.url.path.strip("/").split("/")
    return parts[-1] if parts and parts[-1] else "home"


def get_icon_and_color(item: str, feed_type: str = "update"):
    if "No changes" in item or "Checking if" in item:
        return "check_circle", "text-emerald-500"
    elif "***" in item:
        return "info", "text-sky-500"
    elif "Removing" in item:
        return "delete", "text-rose-500"
    elif "[ERROR]" in item:
        return "cancel", "text-rose-500"
    elif "[WARNING]" in item:
        return "info", "text-amber-500"
    else:
        if feed_type == "update":
            return "published_with_changes", "text-zinc-600"
        else:
            return "cloud_download", "text-zinc-600"


templates.env.globals["get_icon_and_color"] = get_icon_and_color


def base_ctx(request: Request, db: Session, user: dict = None) -> dict:
    tenant_list = db.query(Tenant).all()
    return {
        "request": request,
        "company_name": settings.COMPANY_NAME,
        "app_version": settings.APP_VERSION,
        "tenant_data": tenant_list,
        "user": user,
        "now": datetime.utcnow(),
    }


# ── Home ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
@router.get("/home", response_class=HTMLResponse)
async def home(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_role)],
):
    data = tenant_home_data(db)
    keys = db.query(ApiKey).all()
    now = datetime.now()
    is_admin = settings.ADMIN_ROLE in user.get("roles", [])

    alert_expiring = is_admin and any(
        k.key_expiration and k.key_expiration < now + timedelta(days=30)
        for k in keys
    )
    alert_expired = is_admin and any(
        k.key_expiration and k.key_expiration < now for k in keys
    )

    ctx = base_ctx(request, db, user)
    ctx.update({
        "segment": get_segment(request),
        "data": data,
        "alert_expiring_api_keys": alert_expiring,
        "alert_expired_api_keys": alert_expired,
    })
    return templates.TemplateResponse("pages/home.html", ctx)


@router.get("/home/tenant/{tenant_id}")
async def home_tenant(
    tenant_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_role)],
):
    data = tenant_home_data(db, tenant_id)
    return JSONResponse({
        "matchCount": data["matchCount"],
        "trackedCount": data["trackedCount"],
        "diffCount": data["diffCount"],
        "labelsConfig": data["labelsConfig"],
        "configCounts": data["config_counts"],
        "labelsAverage": data["labelsAverage"],
        "averageDiffs": data["average_diffs"],
        "labelsDiff": data["labelsDiff"],
        "diffs": data["diffs"],
        "diff_len": data["diff_len"],
        "diff_data_last_update": str(data["diff_data_last_update"]),
        "config_data_last_update": str(data["config_data_last_update"]),
        "selectedTenantName": data["selected_tenant_name"],
        "feeds": {
            "backup_feed": data["backup_feed"],
            "update_feed": data["update_feed"],
        },
    })


@router.post("/home/tenant/{tenant_id}/feeds", response_class=HTMLResponse)
async def home_tenant_feeds(
    tenant_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_role)],
):
    body = await request.json()
    feeds = body.get("feeds", {})
    return templates.TemplateResponse(
        "views/home_feeds.html",
        {"request": request, "data": feeds},
    )


# ── Changes ───────────────────────────────────────────────────────────────────

@router.get("/changes", response_class=HTMLResponse)
async def changes(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_role)],
):
    db_tenants = db.query(Tenant).all()
    tenant_changes = []
    for tenant in db_tenants:
        change_data = db.query(SummaryChange).filter_by(tenant=tenant.id).all()[-180:]
        tenant_entry = {
            "name": tenant.display_name,
            "id": tenant.id,
            "data": {"changes": []},
        }
        for change in change_data:
            diffs = change.diffs.replace("'", '"').replace("None", "null") if change.diffs else "[]"
            tenant_entry["data"]["changes"].append({
                "id": change.id,
                "name": change.name,
                "type": change.type,
                "diffs": json.loads(diffs),
            })
        tenant_entry["data"]["changes"].reverse()
        tenant_changes.append(tenant_entry)

    ctx = base_ctx(request, db, user)
    ctx.update({"segment": get_segment(request), "tenant_changes": tenant_changes})
    return templates.TemplateResponse("pages/changes.html", ctx)


# ── Assignments ───────────────────────────────────────────────────────────────

@router.get("/assignments", response_class=HTMLResponse)
async def assignments(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_role)],
):
    db_tenants = db.query(Tenant).all()
    tenant_assignments = []
    for tenant in db_tenants:
        assignment_data = db.query(SummaryAssignment).filter_by(tenant=tenant.id).all()
        tenant_entry = {
            "name": tenant.display_name,
            "id": tenant.id,
            "data": {"assignments": []},
        }
        for a in assignment_data:
            assigned_to = a.assigned_to.replace("'", '"').replace("\\", "\\\\") if a.assigned_to else "[]"
            tenant_entry["data"]["assignments"].append({
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "membership_rule": a.membership_rule,
                "assigned_to": json.loads(assigned_to),
            })
        tenant_entry["data"]["assignments"].sort(key=lambda x: (x["name"] or "").lower())
        tenant_assignments.append(tenant_entry)

    ctx = base_ctx(request, db, user)
    ctx.update({"segment": get_segment(request), "tenant_assignments": tenant_assignments})
    return templates.TemplateResponse("pages/assignments.html", ctx)


# ── Documentation ─────────────────────────────────────────────────────────────

@router.get("/documentation", response_class=HTMLResponse)
async def documentation(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    html = ""
    htmldoc = False
    active = False
    baseline_tenant = db.query(Tenant).filter_by(baseline="true").first()

    if baseline_tenant and baseline_tenant.create_documentation == "true":
        if os.path.exists("/documentation/documentation.html"):
            htmldoc = True
            with open("/documentation/documentation.html", "r") as f:
                html = f.read()
    elif settings.DOCUMENTATION_ACTIVE:
        from azure.storage.blob import BlobServiceClient
        try:
            client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
            blob = client.get_blob_client(
                container=settings.AZURE_CONTAINER_NAME,
                blob=settings.DOCUMENTATION_FILE_NAME,
            )
            local_path = "/intunecd/app/templates/include/documentation.html"
            with open(local_path, "wb") as f:
                f.write(blob.download_blob().readall())
            active = True
        except Exception:
            pass

    ctx = base_ctx(request, db, user)
    ctx.update({
        "segment": get_segment(request),
        "active": active,
        "htmldoc": htmldoc,
        "html": html,
    })
    return templates.TemplateResponse("pages/documentation.html", ctx)


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(get_current_user)],
):
    ctx = base_ctx(request, db, user)
    ctx["segment"] = get_segment(request)
    return templates.TemplateResponse("pages/profile.html", ctx)
