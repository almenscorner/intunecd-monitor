from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, intunecd, pages, schedules, settings as settings_router, tenants
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
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=settings.SESSION_LIFETIME_HOURS * 3600,
    https_only=False,  # set True in production behind HTTPS
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


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Socket.IO ─────────────────────────────────────────────────────────────────
sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=socketio.AsyncRedisManager(settings.CELERY_BROKER_URL),
    cors_allowed_origins="*",
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
