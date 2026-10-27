"""Raw media HTTP; no framework range, ETag or public file serving."""

import asyncio
import errno
import json
import os
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.sessions import verify
from opengym_platform.media.service import Refused


def create_router(*, secret, secure, media):
    router = APIRouter()

    @router.post("/media/missing")
    async def missing(request: Request):
        return await resource("missing", request)

    @router.api_route("/media/{digest}", methods=["GET", "PUT"])
    async def resource(digest: str, request: Request):
        headers = {"Cache-Control": "no-store"}
        is_missing = digest == "missing" and request.method == "POST"
        if not is_missing and not re.fullmatch(r"[0-9a-f]{64}", digest):
            return JSONResponse(
                {"error": "not found"}, status_code=404, headers=headers
            )
        if request.method != "GET" and not request.headers.get(
            "authorization", ""
        ).startswith("Bearer "):
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
            if is_missing:
                raw = bytearray()
                async with asyncio.timeout(30):
                    async for chunk in request.stream():
                        raw.extend(chunk)
                        if len(raw) > 5 * 1024 * 1024:
                            return JSONResponse(
                                {"error": "body too large"},
                                status_code=413,
                                headers=headers,
                            )
                try:

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
                except (ValueError, TypeError, RecursionError):
                    return JSONResponse(
                        {"error": "invalid json"}, status_code=400, headers=headers
                    )
                status, result = await media.missing(
                    request.app.state.database, session, body.get("hashes")
                )
                return JSONResponse(result, status_code=status, headers=headers)
            if request.method == "PUT":
                status, result = await media.receive(
                    request.app.state.database, session, digest, request
                )
                return JSONResponse(result, status_code=status, headers=headers)
            result = await media.download(request.app.state.database, session, digest)
            if result is None:
                return JSONResponse(
                    {"error": "not signed in"}, status_code=401, headers=headers
                )
            source, mime, extension = result

            async def chunks():
                try:
                    while chunk := await run_in_threadpool(source.read, 256 * 1024):
                        yield chunk
                finally:
                    source.close()

            return StreamingResponse(
                chunks(),
                media_type=mime,
                headers={
                    "Content-Length": str(os.fstat(source.fileno()).st_size),
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "default-src 'none'; sandbox",
                    "Cross-Origin-Resource-Policy": "same-origin",
                    "Content-Disposition": f'inline; filename="{digest}.{extension}"',
                    "X-Robots-Tag": "noindex",
                    "Access-Control-Expose-Headers": "Content-Length",
                },
                background=BackgroundTask(source.close),
            )
        except Refused as error:
            if error.status == 429:
                headers["Retry-After"] = str(error.body["retryAfter"])
            if error.status == 408:
                headers["Connection"] = "close"
            return JSONResponse(error.body, status_code=error.status, headers=headers)
        except TimeoutError:
            return JSONResponse(
                {"error": "request timeout"},
                status_code=408,
                headers=headers | {"Connection": "close"},
            )
        except OSError as error:
            if error.errno == errno.ENOSPC:
                return JSONResponse(
                    {
                        "error": "the server is running out of disk space",
                        "code": "storage-full",
                    },
                    status_code=507,
                    headers=headers,
                )
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )
        except DatabaseError:
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    return router
