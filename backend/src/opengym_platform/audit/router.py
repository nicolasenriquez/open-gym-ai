"""Existing Admin activity-log transport; no public diagnostic endpoint."""

import math
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import verify


def number(value, default):
    try:
        result = float(value or 0)
        return result if result and not math.isnan(result) else default
    except ValueError:
        return default


def create_router(*, secret, secure):
    router = APIRouter()

    @router.get("/admin/audit")
    @router.post("/admin/audit/clear")
    async def audit(request: Request):
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
        service = request.app.state.audit
        try:
            if request.method == "POST":
                status, result = await service.clear(session, request)
            else:
                query = request.query_params

                def first(key, default=None):
                    return next(iter(query.getlist(key)), default)

                requested = max(1, min(200, number(first("limit"), 100)))
                limit = math.floor(requested)
                before = number(first("before"), float("inf"))
                before = (
                    -9223372036854775808
                    if before < -9223372036854775808
                    else math.ceil(before)
                    if before <= 9223372036854775807
                    else None
                )
                category = first("cat", "")
                if "\x00" in category or any(
                    0xD800 <= ord(c) <= 0xDFFF for c in category
                ):
                    category = "__invalid__"
                status, result = await service.read(
                    session, before=before, limit=limit, category=category
                )
                if status == 200 and requested != limit:
                    result["nextBefore"] = None
            if status == 403:
                await service.append(
                    "admin.denied", actor=session.owner, ok=False, request=request
                )
            return response(result, status)
        except DatabaseError:
            return response({"error": "server error"}, 500)

    return router
