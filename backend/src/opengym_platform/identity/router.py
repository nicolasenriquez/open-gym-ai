"""Identity HTTP transport; application composition supplies its collaborators."""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.core.database import DatabaseError
from opengym_platform.identity.account import Accounts
from opengym_platform.identity.links import Links
from opengym_platform.identity.passkeys import Passkeys
from opengym_platform.identity.passwords import BusyError
from opengym_platform.identity.reset import redeem as redeem_reset
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

        @router.post("/login/password-reset")
        async def password_reset(request: Request):
            return await identity_request(request, redeem_reset)

        @router.post("/login/password")
        async def password_login(request: Request):
            return await identity_request(request, login_password)

        @router.post("/register/password")
        async def password_register(request: Request):
            return await identity_request(request, register_password)

    passkeys = Passkeys()
    accounts = Accounts(passkeys, password_login_enabled)
    links = Links(accounts)

    @router.post("/account/device-link")
    async def device_link_create(request: Request):
        return await identity_request(request, links.create, protected=True)

    @router.post("/device-link/options")
    async def device_link_options(request: Request):
        return await identity_request(request, links.options)

    @router.post("/device-link/verify")
    async def device_link_verify(request: Request):
        return await identity_request(request, links.verify)

    @router.post("/pair/create")
    async def pair_create(request: Request):
        return await identity_request(request, links.pair_create, protected=True)

    @router.post("/pair/redeem")
    async def pair_redeem(request: Request):
        return await identity_request(request, links.pair_redeem, exempt=True)

    @router.get("/account/passkeys")
    async def list_passkeys(request: Request):
        return await identity_request(request, accounts.list_passkeys, protected=True)

    @router.post("/account/passkeys/options")
    async def add_passkey_options(request: Request):
        return await identity_request(
            request, accounts.add_passkey_options, protected=True
        )

    @router.post("/account/passkeys/verify")
    async def add_passkey_verify(request: Request):
        return await identity_request(
            request, accounts.add_passkey_verify, protected=True
        )

    @router.post("/account/passkeys/rename")
    async def rename_passkey(request: Request):
        return await identity_request(request, accounts.rename_passkey, protected=True)

    @router.delete("/account/passkeys")
    async def remove_passkey(request: Request):
        return await identity_request(request, accounts.remove_passkey, protected=True)

    if password_login_enabled:

        @router.post("/account/password")
        async def set_password(request: Request):
            return await identity_request(
                request, accounts.set_password, protected=True
            )

        @router.delete("/account/password")
        async def remove_password(request: Request):
            return await identity_request(
                request, accounts.remove_password, protected=True
            )

        @router.post("/account/email")
        async def set_email(request: Request):
            return await identity_request(request, accounts.set_email, protected=True)

        @router.delete("/account/email")
        async def remove_email(request: Request):
            return await identity_request(
                request, accounts.remove_email, protected=True
            )

        @router.get("/account/password")
        async def password_status(request: Request):
            return await identity_request(
                request, accounts.password_status, protected=True
            )

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

    @router.post("/logout/all")
    async def logout_all(request: Request):
        return await identity_request(request, accounts.logout_all, protected=True)

    async def identity_request(request, operation, *, exempt=False, protected=False):
        headers = {"Cache-Control": "no-store"}
        site = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")
        if (
            not exempt
            and request.method != "GET"
            and not request.headers.get("authorization", "").startswith("Bearer ")
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
            if (
                not exempt
                and request.method != "GET"
                and operation
                not in (
                    accounts.logout_all,
                    accounts.rename_passkey,
                    accounts.add_passkey_verify,
                    links.pair_create,
                )
            ):
                throttle.entry(
                    (
                        "signup|"
                        if operation is register_password
                        else "email|"
                        if operation == accounts.set_email
                        else "link|"
                        if operation in (links.options, links.verify)
                        else ""
                    )
                    + address,
                    check_address=request.method != "DELETE"
                    and operation not in (accounts.add_passkey_options, links.create),
                )
        except LockedError as error:
            return locked_response(error)
        session = None
        if protected:
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
            raw = bytearray()
            if request.method != "GET" and operation not in (
                accounts.logout_all,
                links.pair_create,
            ):
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
        except ValueError, TypeError, RecursionError:
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
                **({"session": session} if protected else {}),
                **(
                    {
                        "credential_id": next(
                            iter(request.query_params.getlist("id")), ""
                        )
                    }
                    if operation == accounts.remove_passkey
                    else {}
                ),
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
            if operation == accounts.logout_all and status == 200:
                for name in ["__Host-gymsid", "gymsid"] if secure else ["gymsid"]:
                    response.headers.append(
                        "Set-Cookie",
                        f"{name}=; Path=/; Max-Age=0; HttpOnly;{' Secure;' if secure else ''} SameSite=Lax",
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
        except DatabaseError, ValueError, OverflowError:
            return JSONResponse(
                {"error": "server error"}, status_code=500, headers=headers
            )

    return router
