import pytz
import os

from datetime import datetime


def emit_message(message, status, task, TENANT_ID, socket) -> None:
    """Emits a message to the frontend.

    Args:
        message (str): message to display
        status (str): status of the run
        task (str): task that is running
        TENANT_ID (int): ID of the tenant
    """
    date_now = get_now()
    socket.emit(
        "intunecdrun",
        {
            "status": status,
            "task": task,
            "message": message,
            "date": date_now,
            "tenant_id": TENANT_ID,
        },
    )


def update_tenant_status_data(TENANT, status, message) -> None:
    """Updates the status data for the tenant.

    Args:
        TENANT (object): tenant object
        status (str): status of the run
        message (str): message to display
    """
    TENANT.last_update = get_now()
    TENANT.last_update_status = status
    TENANT.last_update_message = message


def get_now() -> str:
    """Returns current date in the Timezone specified in
       ENV vars. If nothing is specifiec UTC is used.

    Returns:
        str: current date
    """
    tz = pytz.timezone(os.environ.get("TIMEZONE", "UTC"))
    now = datetime.now(tz)
    date_now = now.strftime("%Y-%m-%d %H:%M:%S")

    return date_now
