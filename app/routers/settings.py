import secrets
import re
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.models import ApiKey
from app.routers.pages import base_ctx, get_segment

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    new_key = request.session.pop("new_key", "")
    keys = db.query(ApiKey).all()
    now = datetime.now()
    keys_td = (
        [{"id": k.id, "expiration": (k.key_expiration - now).days} for k in keys]
        if keys
        else []
    )
    safe_db_url = re.sub(
        r"(?<=:\/\/)([^:]+):([^@]+)@", r"\1:***@", settings.DATABASE_URL
    )

    ctx = base_ctx(request, db, user)
    ctx.update(
        {
            "segment": get_segment(request),
            "settings": settings,
            "database_url": safe_db_url,
            "key": bool(keys),
            "keys_td": keys_td,
            "new_key": new_key,
        }
    )
    return templates.TemplateResponse("pages/settings.html", ctx)


@router.post("/settings/key/create", include_in_schema=False)
async def create_key(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    plain_key = secrets.token_urlsafe()
    expiration = datetime.now() + timedelta(days=90)
    key = ApiKey(key_expiration=expiration)
    key.set_key(plain_key)
    db.add(key)
    db.commit()
    request.session["new_key"] = plain_key
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/key/delete", include_in_schema=False)
async def delete_key(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[dict, Depends(require_admin)],
):
    form = await request.form()
    for key_id in form:
        try:
            key = db.get(ApiKey, int(key_id))
        except (ValueError, TypeError):
            continue
        if key:
            db.delete(key)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)
