"""Subscription operations authorize at the transaction boundary."""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import verify
from opengym_platform.notifications.service import handle as handle_operation
from opengym_platform.notifications.service import preflight
from opengym_platform.notifications.vapid import public_key


def create_router(*, secret, secure):
    router = APIRouter()

    @router.get("/push/public-key")
    async def key():
        try:
            return JSONResponse(
                {"key": await run_in_threadpool(public_key)},
                headers={"Cache-Control": "no-store"},
            )
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            return JSONResponse(
                {"error": "server error"},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )

    @router.get("/push/status")
    @router.post("/push/subscribe")
    @router.post("/push/unsubscribe")
    async def subscription(request: Request):
        def response(body, status=200):
            return JSONResponse(
                body, status_code=status, headers={"Cache-Control": "no-store"}
            )

        if request.method == "POST" and not request.headers.get(
            "authorization", ""
        ).startswith("Bearer "):
            site, origin = (
                request.headers.get("sec-fetch-site"),
                request.headers.get("origin"),
            )
            allowed = (
                site in {"same-origin", "none"}
                if site
                else not origin
                or origin.rstrip("/")
                == os.environ.get("ORIGIN", "http://localhost:8080").rstrip("/")
            )
            if not allowed:
                return response({"error": "cross-origin request refused"}, 403)
        session = verify(
            ";".join(request.headers.getlist("cookie")),
            request.headers.get("authorization", ""),
            secure,
            secret,
        )
        if not session:
            return response({"error": "not signed in"}, 401)
        body = {}
        try:
            database = request.app.state.database
            # Body validation does not grant access, including on a revoked session.
            if not await preflight(database, session):
                return response({"error": "not signed in"}, 401)
            if request.method == "POST":
                raw = bytearray()
                async for chunk in request.stream():
                    if len(raw) + len(chunk) > 5 * 1024 * 1024:
                        return response({"error": "body too large"}, 413)
                    raw.extend(chunk)
                try:
                    body = json.loads(raw or b"{}")
                    if not isinstance(body, dict):
                        raise TypeError
                except (ValueError, TypeError, UnicodeError):
                    return response({"error": "invalid JSON"}, 400)
            operation = request.url.path.rsplit("/", 1)[-1]
            status, result = await handle_operation(
                database,
                session,
                operation,
                {"endpoint": request.query_params.get("endpoint", "")}
                if request.method == "GET"
                else body,
            )
            return response(result, status)
        except DatabaseError:
            return response({"error": "server error"}, 500)

    return router
