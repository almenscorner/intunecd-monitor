"""Server-side session middleware backed by Redis.

Stores session data in Redis and only puts a session ID cookie in the
browser.  This removes the 4 KB cookie size limit that plagues
Starlette's built-in SessionMiddleware.
"""

import json
import secrets
from typing import Optional

import redis
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RedisSessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        redis_url: str,
        *,
        session_cookie: str = "session",
        max_age: int = 14400,
        https_only: bool = False,
        same_site: str = "lax",
    ):
        self.app = app
        self.pool = redis.ConnectionPool.from_url(redis_url)
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.https_only = https_only
        self.same_site = same_site

    def _redis(self) -> redis.Redis:
        return redis.Redis(connection_pool=self.pool)

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        session_id: Optional[str] = connection.cookies.get(self.session_cookie)
        initial_data: dict = {}
        r = self._redis()

        if session_id:
            raw = r.get(self._key(session_id))
            if raw:
                initial_data = json.loads(raw)
            else:
                session_id = None  # expired / invalid

        scope["session"] = dict(initial_data)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                session_data = scope.get("session", {})
                headers = MutableHeaders(scope=message)

                if session_data:
                    if not session_id:
                        new_id = secrets.token_urlsafe(32)
                    else:
                        new_id = session_id

                    r.setex(
                        self._key(new_id),
                        self.max_age,
                        json.dumps(session_data),
                    )

                    cookie = (
                        f"{self.session_cookie}={new_id}; path=/; "
                        f"Max-Age={self.max_age}; HttpOnly; SameSite={self.same_site}"
                    )
                    if self.https_only:
                        cookie += "; Secure"
                    headers.append("set-cookie", cookie)

                elif session_id and not session_data:
                    # Session was cleared — delete from Redis and expire cookie
                    r.delete(self._key(session_id))
                    cookie = (
                        f"{self.session_cookie}=; path=/; "
                        f"Max-Age=0; HttpOnly; SameSite={self.same_site}"
                    )
                    headers.append("set-cookie", cookie)

            await send(message)

        await self.app(scope, receive, send_wrapper)
