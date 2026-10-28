"""Compatibility refusals for old clients before any Coach execution exists."""

import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import authorize, verify


def create_router(*, secret, secure):
    router = APIRouter(prefix="/coach")

    @router.get("/status")
    @router.post("/plan")
    @router.post("/review")
    @router.post("/debrief")
    async def unavailable(request: Request):
        headers = {"Cache-Control": "no-store"}
        if request.method == "POST" and not request.headers.get(
            "authorization", ""
        ).startswith("Bearer "):
            site = request.headers.get("sec-fetch-site")
            origin = request.headers.get("origin")
            allowed = (
                site in {"same-origin", "none"}
                if site
                else (
                    not origin
                    or origin.rstrip("/")
                    == os.environ.get("ORIGIN", "http://localhost:8080").rstrip("/")
                )
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
        try:
            if session:
                async with request.app.state.database.transaction() as handle:
                    if not await authorize(handle, session):
                        session = None
            if not session:
                return JSONResponse(
                    {"error": "not signed in"}, status_code=401, headers=headers
                )
            # shortcut: no execution before slices 5.2/5.3, replace only when enqueue is delivered.
            return JSONResponse(
                {"error": "the Coach is not set up on this instance", "code": "off"},
                status_code=503,
                headers=headers,
            )
        except DatabaseError:
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    return router
