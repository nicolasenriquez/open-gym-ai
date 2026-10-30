"""Compatible Coach HTTP surface; operations own authorization and transactions."""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.coach.jobs import Refused
from opengym_platform.coach.pipeline import invalid_constant
from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import verify


def create_router(*, secret, secure):
    router = APIRouter(prefix="/coach")

    @router.get("/status")
    @router.post("/plan")
    @router.post("/review")
    @router.post("/debrief")
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
            if request.method == "GET":
                return JSONResponse(await jobs.status(session), headers=headers)
            await jobs.preflight(session)
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
            kind = {"plan": "create", "review": "review", "debrief": "debrief"}[
                request.url.path.rsplit("/", 1)[-1]
            ]
            job = await jobs.enqueue(session, kind=kind, opts=body)
            return JSONResponse(
                {"job": {"id": job["id"]}}, status_code=202, headers=headers
            )
        except Refused as error:
            return JSONResponse(error.body, status_code=error.status, headers=headers)
        except DatabaseError:
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    return router
