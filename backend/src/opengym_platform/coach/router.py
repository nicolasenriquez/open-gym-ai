"""Compatible Coach HTTP surface; operations own authorization and transactions."""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.coach.admin import Invalid
from opengym_platform.coach.jobs import Refused
from opengym_platform.coach.pipeline import invalid_constant
from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import verify


def create_router(*, secret, secure):
    router = APIRouter()

    @router.get("/coach/status")
    @router.post("/coach/plan")
    @router.post("/coach/review")
    @router.post("/coach/debrief")
    @router.post("/coach/pending/resolve")
    @router.post("/coach/forget")
    @router.get("/coach/account")
    @router.post("/admin/coach/connect")
    @router.post("/admin/coach/disconnect")
    @router.get("/admin/coach")
    @router.post("/admin/coach/config")
    @router.post("/admin/coach/test")
    @router.post("/admin/coach/models")
    async def coach(request: Request):
        headers = {"Cache-Control": "no-store"}
        if request.method == "POST" and not request.headers.get(
            "authorization", ""
        ).startswith("Bearer "):
            site = request.headers.get("sec-fetch-site")
            origin = request.headers.get("origin")
            allowed = (
                site in {"same-origin", "none"}
                if site
                else not origin
                or origin.rstrip("/")
                == os.environ.get("ORIGIN", "http://localhost:8080").rstrip("/")
            )
            if not allowed:
                return JSONResponse(
                    {"error": "cross-origin request refused"},
                    status_code=403,
                    headers=headers,
                )
        session = verify(
            ";".join(request.headers.getlist("cookie")),
            request.headers.get("authorization", ""),
            secure,
            secret,
        )
        if not session:
            return JSONResponse(
                {"error": "not signed in"}, status_code=401, headers=headers
            )
        try:
            jobs = request.app.state.coach_jobs
            if request.url.path.endswith("/account"):
                return JSONResponse(
                    await request.app.state.coach_admin.handle(session, "account", {}),
                    headers=headers,
                )
            admin_route = "/admin/coach" in request.url.path
            if admin_route and request.method == "GET":
                return JSONResponse(
                    await request.app.state.coach_admin.handle(session, "view", {}),
                    headers=headers,
                )
            if request.url.path.endswith("/coach/forget"):
                return JSONResponse(await jobs.forget(session), headers=headers)
            if request.method == "GET":
                return JSONResponse(await jobs.status(session), headers=headers)
            if not admin_route:
                await jobs.preflight(session)
            else:
                await request.app.state.coach_admin.preflight(session)
            try:
                raw = bytearray()
                async for chunk in request.stream():
                    if len(raw) + len(chunk) > 5 * 1024 * 1024:
                        return JSONResponse(
                            {"error": "body too large"},
                            status_code=413,
                            headers=headers,
                        )
                    raw.extend(chunk)
                body = json.loads(raw, parse_constant=invalid_constant) if raw else {}
            except (ValueError, UnicodeError):
                return JSONResponse(
                    {"error": "invalid json"}, status_code=400, headers=headers
                )
            body = body if isinstance(body, dict) else {}
            if admin_route:
                return JSONResponse(
                    await request.app.state.coach_admin.handle(
                        session, request.url.path.rsplit("/", 1)[-1], body
                    ),
                    headers=headers,
                )
            if request.url.path.endswith("/coach/pending/resolve"):
                return JSONResponse(await jobs.resolve(session, body), headers=headers)
            kind = {"plan": "create", "review": "review", "debrief": "debrief"}[
                request.url.path.rsplit("/", 1)[-1]
            ]
            job = await jobs.enqueue(session, kind=kind, opts=body)
            return JSONResponse(
                {"job": {"id": job["id"]}}, status_code=202, headers=headers
            )
        except (Refused, Invalid) as error:
            return JSONResponse(error.body, status_code=error.status, headers=headers)
        except (DatabaseError, OSError, ValueError):
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    return router
