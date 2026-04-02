import os
from datetime import datetime

import pytz
import socketio

# Redis manager for emitting from external processes (Celery workers).
# The FastAPI server connects to the same Redis channel to relay messages to browsers.
_broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
_mgr = socketio.RedisManager(_broker_url, write_only=True)


def get_now_dt() -> datetime:
    tz = pytz.timezone(os.environ.get("TIMEZONE", "UTC"))
    return datetime.now(tz)


def get_now() -> str:
    return get_now_dt().strftime("%Y-%m-%d %H:%M:%S")


def emit_message(message: str, status: str, task: str, tenant_id: int) -> None:
    _mgr.emit(
        "intunecdrun",
        {
            "status": status,
            "task": task,
            "message": message,
            "date": get_now(),
            "tenant_id": tenant_id,
        },
    )


def update_tenant_status_data(tenant, status: str, message: str) -> None:
    tenant.last_update = datetime.now()
    tenant.last_update_status = status
    tenant.last_update_message = message
