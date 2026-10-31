"""Compatible admin list, drill-down and account lock routes."""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.administration.service import handle
from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import verify


def create_router(*, secret, secure, config):
    router = APIRouter()

    @router.get("/admin/users")
    @router.get("/admin/user")
    @router.post("/admin/user/disable")
    async def users(request: Request):
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
        database = request.app.state.database
        try:
            if request.method == "POST":
                # Match requireAdmin before parsing a mutation body; never keep a lease while streaming.
                async with database.transaction() as tx:
                    rows = await tx.fetch(
                        "SELECT administration.inspect_user($1,$2,$3,$1) AS view",
                        session.owner,
                        session.version,
                        session.expires_at,
                    )
                    access = json.loads(rows[0]["view"]) if rows[0]["view"] else None
                    if access is None:
                        return response({"error": "not signed in"}, 401)
                    if not access:
                        return response({"error": "forbidden"}, 403)
                raw = bytearray()
                async for chunk in request.stream():
                    if len(raw) + len(chunk) > 5 * 1024 * 1024:
                        return response({"error": "body too large"}, 413)
                    raw.extend(chunk)

                def invalid_constant(value):
                    raise ValueError("invalid json")

                try:
                    body = json.loads(
                        raw.decode("utf-8", errors="replace") or "{}",
                        parse_constant=invalid_constant,
                    )
                    if not isinstance(body, dict):
                        raise TypeError
                except (ValueError, TypeError, RecursionError):
                    return response({"error": "invalid json"}, 400)
            else:
                body = {"id": request.query_params.get("id")}
            status, result = await handle(
                database, session, request.url.path.rsplit("/", 1)[-1], body, config
            )
            if status == 200:
                notifications = request.app.state.notifications
                if "users" in result:
                    for user in result["users"]:
                        user["live"] = (
                            None
                            if user["disabled"]
                            else notifications.active.live(user["id"])
                        )
                elif result.get("disabled"):
                    notifications.active.update(result["id"], {"active": False})
                    notifications.cancel(result["id"])
            return response(result, status)
        except PermissionError:
            return response({"error": "not signed in"}, 401)
        except DatabaseError:
            return response({"error": "server error"}, 500)

    return router
