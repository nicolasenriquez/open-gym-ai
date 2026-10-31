"""Subscription operations authorize at the transaction boundary."""

import json
import math
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import authorize, verify
from opengym_platform.notifications.activity import number
from opengym_platform.notifications.planner import COPY, obj
from opengym_platform.notifications.service import device_id, preflight
from opengym_platform.notifications.service import handle as handle_operation
from opengym_platform.notifications.vapid import public_key
from opengym_platform.training.service import notification_document


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

    @router.post("/activity")
    @router.post("/push/rest-timer")
    @router.post("/push/rest-timer/cancel")
    @router.post("/push/test")
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
            operation = request.url.path.rsplit("/", 1)[-1]
            if request.method == "POST" and operation != "test":
                raw = bytearray()
                async for chunk in request.stream():
                    if len(raw) + len(chunk) > 5 * 1024 * 1024:
                        return response({"error": "body too large"}, 413)
                    raw.extend(chunk)
                try:

                    def invalid_constant(value):
                        raise ValueError("invalid JSON")

                    body = json.loads(raw or b"{}", parse_constant=invalid_constant)
                    if not isinstance(body, dict):
                        raise TypeError
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    return response({"error": "invalid JSON"}, 400)
            if operation in {"test", "rest-timer", "cancel", "activity"}:
                seconds = None
                if operation == "rest-timer":
                    value = body.get("seconds")
                    n = number(value) if type(value) in (int, float, str) else 0
                    if not n >= 1:
                        return response({"error": "seconds required"}, 400)
                    seconds = math.floor(min(3600, n) + 0.5)
                async with database.transaction() as handle:
                    if not await authorize(handle, session):
                        return response({"error": "not signed in"}, 401)
                    state = (
                        obj(await notification_document(handle))
                        if operation in {"test", "rest-timer"}
                        else {}
                    )
                    lang = state.get("lang")
                alerts = (
                    COPY["alerts"].get(lang, COPY["alerts"]["en"])
                    if isinstance(lang, str)
                    else COPY["alerts"]["en"]
                )
                notifications = request.app.state.notifications
                device = device_id(body.get("deviceId"))
                if operation == "activity":
                    notifications.active.update(session.owner, body)
                elif operation == "test":
                    await notifications.push(session, alerts["test"])
                elif operation == "cancel":
                    notifications.cancel(session.owner, device)
                else:
                    notifications.schedule(session, device, seconds, alerts["rest"])
                return response({"ok": True})
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
