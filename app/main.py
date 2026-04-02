from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.session import RedisSessionMiddleware
from app.routers import (
    auth,
    intunecd,
    pages,
    schedules,
    settings as settings_router,
    tenants,
)
from app.routers.api import assignments, changes
from app.routers.api import schedules as api_schedules
from app.routers.api import tenants as api_tenants


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="IntuneCD Monitor",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    RedisSessionMiddleware,
    redis_url=settings.REDIS_SESSION_URL,
    max_age=settings.SESSION_LIFETIME_HOURS * 3600,
    https_only=settings.HTTPS_ONLY,
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Page routes
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(tenants.router)
app.include_router(schedules.router)
app.include_router(settings_router.router)
app.include_router(intunecd.router)

# API routes
app.include_router(assignments.router, prefix="/api/v1")
app.include_router(changes.router, prefix="/api/v1")
app.include_router(api_tenants.router, prefix="/api/v1")
app.include_router(api_schedules.router, prefix="/api/v1")


_templates = Jinja2Templates(directory="app/templates")

_ERROR_MESSAGES = {
    403: "You don't have permission to access this page.",
    404: "The page you're looking for doesn't exist.",
    401: "Authentication required.",
}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code in (301, 302, 303, 307, 308):
        return RedirectResponse(
            url=exc.headers.get("Location", "/"), status_code=exc.status_code
        )

    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    detail = exc.detail or _ERROR_MESSAGES.get(
        exc.status_code, "An unexpected error occurred."
    )
    return _templates.TemplateResponse(
        "pages/error.html",
        {"request": request, "error": detail},
        status_code=exc.status_code,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Socket.IO ─────────────────────────────────────────────────────────────────
sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=socketio.AsyncRedisManager(settings.CELERY_BROKER_URL),
    cors_allowed_origins=(
        f"https://{settings.SERVER_NAME}"
        if settings.HTTPS_ONLY and settings.SERVER_NAME
        else "*"
    ),
)


@sio.on("connect")
async def on_connect(sid, environ, auth=None):
    # Reject connections without a session user
    cookies = environ.get("HTTP_COOKIE", "")
    if not cookies:
        return False


# Wrap FastAPI with Socket.IO ASGI app so Socket.IO requests are handled
# at the root and all other requests fall through to FastAPI.
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
