from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ApiKey


api_key_header = APIKeyHeader(
    name="X-Api-Key",
    auto_error=False,
    scheme_name="X-Api-Key",
    description="API key created in the Settings page.",
)


def get_current_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": "/login"},
        )
    return user


def require_role(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if "roles" not in user or not user["roles"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No role assigned to this account.",
        )
    return user


def require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if "roles" not in user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No role assigned to this account.",
        )
    if settings.ADMIN_ROLE not in user["roles"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return user


def require_api_key(
    key_header: Annotated[str | None, Security(api_key_header)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    if not key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Api-Key header.",
        )

    now = datetime.now()
    valid_keys = (
        db.query(ApiKey)
        .filter(ApiKey.key_expiration > now)
        .all()
    )
    for k in valid_keys:
        if k.check_key(key_header):
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired API key.",
    )
