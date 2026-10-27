"""Identity HTTP transport; application composition supplies its collaborators."""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.passkeys import Passkeys
from opengym_platform.identity.passwords import BusyError
from opengym_platform.identity.service import password_login as login_password
from opengym_platform.identity.service import password_register as register_password
from opengym_platform.identity.service import profile
from opengym_platform.identity.sessions import verify
from opengym_platform.identity.throttle import LockedError, limit_address


def invalid_json_constant(value):
    raise ValueError("invalid json")


def locked_response(error):
    return JSONResponse(
        {
            "error": "too many attempts, try again later",
            "code": "locked",
            "retryAfter": error.seconds,
        },
        status_code=429,
        headers={"Cache-Control": "no-store", "Retry-After": str(error.seconds)},
    )


def create_router(
    *,
    secret,
    secure,
    session_days,
    passwords,
    throttle,
    password_login_enabled,
):
    router = APIRouter()

    @router.get("/me")
    async def me(request: Request):
        headers = {"Cache-Control": "no-store"}
        session = verify(
            ";".join(request.headers.getlist("cookie")),
            request.headers.get("authorization", ""),
            secure,
            secret,
        )
        if session is None:
            return JSONResponse(
                {"error": "not signed in"}, status_code=401, headers=headers
            )
        try:
            result = await profile(
                request.app.state.database, session, secret, session_days
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

    if password_login_enabled:

        @router.post("/login/password")
        async def password_login(request: Request):
            return await identity_request(request, login_password)

        @router.post("/register/password")
        async def password_register(request: Request):
            return await identity_request(request, register_password)

    passkeys = Passkeys()

    @router.post("/login/options")
    async def login_options():
        status, result, _ = passkeys.login_options()
        return JSONResponse(
            result, status_code=status, headers={"Cache-Control": "no-store"}
        )

    @router.post("/register/options")
    async def register_options(request: Request):
        return await identity_request(request, passkeys.register_options, exempt=True)

    @router.post("/register/verify")
    async def register_verify(request: Request):
        return await identity_request(request, passkeys.register_verify, exempt=True)

    @router.post("/login/verify")
    async def login_verify(request: Request):
        return await identity_request(request, passkeys.login_verify, exempt=True)

    async def identity_request(request, operation, *, exempt=False):
        headers = {"Cache-Control": "no-store"}
        site = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")
        if not exempt and not request.headers.get("authorization", "").startswith(
            "Bearer "
        ):
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
        address = limit_address(
            request,
            os.environ.get("TRUST_PROXY", "").lower() in {"1", "true", "yes", "on"},
        )
        try:
            if not exempt:
                throttle.entry(
                    ("signup|" if operation is register_password else "") + address
                )
        except LockedError as error:
            return locked_response(error)
        try:
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 5 * 1024 * 1024:
                    return JSONResponse(
                        {"error": "body too large"},
                        status_code=413,
                        headers=headers,
                    )
            body = (
                json.loads(
                    raw.decode("utf-8", errors="replace"),
                    parse_constant=invalid_json_constant,
                )
                if raw
                else {}
            )
            if not isinstance(body, dict):
                raise TypeError
        except (ValueError, TypeError, RecursionError):
            return JSONResponse(
                {"error": "invalid json"}, status_code=400, headers=headers
            )
        try:
            status, result, token = await operation(
                request.app.state.database,
                passwords,
                throttle,
                address,
                body,
                secret,
                session_days,
            )
            response = JSONResponse(result, status_code=status, headers=headers)
            if token:
                name = "__Host-gymsid" if secure else "gymsid"
                flags = f"; Path=/; Max-Age={format(session_days * 86400, '.15f').rstrip('0').rstrip('.')}; HttpOnly;{' Secure;' if secure else ''} SameSite=Lax"
                response.headers.append("Set-Cookie", f"{name}={token}{flags}")
                if secure:
                    response.headers.append(
                        "Set-Cookie",
                        "gymsid=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax",
                    )
            return response
        except LockedError as error:
            return locked_response(error)
        except BusyError:
            return JSONResponse(
                {
                    "error": "the server is busy, try again in a moment",
                    "code": "busy",
                },
                status_code=503,
                headers={**headers, "Retry-After": "2"},
            )
        except (DatabaseError, ValueError, OverflowError):
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    return router
