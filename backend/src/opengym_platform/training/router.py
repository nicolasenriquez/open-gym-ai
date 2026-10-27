"""Training HTTP routes; unconditional legacy writes arrive in 3.3."""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import verify
from opengym_platform.training.service import read, write


def create_router(*, secret, secure, note_state=None):
    router = APIRouter()

    @router.put("/api/data")
    async def save(request: Request):
        headers = {"Cache-Control": "no-store"}
        if not request.headers.get("authorization", "").startswith("Bearer "):
            site, origin = (
                request.headers.get("sec-fetch-site"),
                request.headers.get("origin"),
            )
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
        if not session:
            return JSONResponse(
                {"error": "not signed in"}, status_code=401, headers=headers
            )
        try:
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 5 * 1024 * 1024:
                    return JSONResponse(
                        {"error": "body too large"}, status_code=413, headers=headers
                    )

            def invalid_constant(value):
                raise ValueError("invalid json")

            body = (
                json.loads(
                    raw.decode("utf-8", errors="replace"),
                    parse_constant=invalid_constant,
                )
                if raw
                else {}
            )
            if not isinstance(body, dict):
                raise TypeError("invalid json")
        except ValueError, TypeError, RecursionError:
            return JSONResponse(
                {"error": "invalid json"}, status_code=400, headers=headers
            )
        try:
            status, result = await write(
                request.app.state.database, session, body, note_state
            )
            return JSONResponse(result, status_code=status, headers=headers)
        except DatabaseError:
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    @router.get("/api/data")
    @router.get("/api/data/rev")
    async def data(request: Request):
        headers = {"Cache-Control": "no-store"}
        session = verify(
            ";".join(request.headers.getlist("cookie")),
            request.headers.get("authorization", ""),
            secure,
            secret,
        )
        try:
            result = (
                await read(
                    request.app.state.database,
                    session,
                    revision_only=request.url.path.endswith("/rev"),
                )
                if session
                else None
            )
            if result is None:
                return JSONResponse(
                    {"error": "not signed in"}, status_code=401, headers=headers
                )
            return JSONResponse(result, headers=headers)
        except DatabaseError:
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    return router
