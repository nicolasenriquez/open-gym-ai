"""Platform HTTP composition and lifecycle."""

import math
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from opengym_platform.core.database import Database, DatabaseError
from opengym_platform.core.platform_settings import (
    load_public_config,
    load_session_secret,
)
from opengym_platform.identity.passwords import Passwords
from opengym_platform.identity.router import create_router
from opengym_platform.identity.throttle import Throttle
from opengym_platform.training.router import create_router as training_router


def create_app(*, training_note_state=None):
    public_config = load_public_config()
    secret = load_session_secret()
    secure = os.environ.get("ORIGIN", "http://localhost:8080").startswith("https://")
    try:
        session_days = max(1.0, float(os.environ.get("SESSION_DAYS", "90")) or 90)
        if not math.isfinite(session_days):
            session_days = 90.0
    except ValueError:
        session_days = 90.0

    passwords = Passwords()
    throttle = Throttle()

    @asynccontextmanager
    async def lifespan(app):
        if public_config.get("password_login"):
            await passwords.warm_up()
        database = await Database.open_platform()
        app.state.database = database
        try:
            yield
        finally:
            await database.close()

    app = FastAPI(
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )

    public_api = APIRouter(prefix="/api/v1")

    @app.exception_handler(404)
    @app.exception_handler(405)
    async def not_found(request: Request, error: HTTPException):
        return JSONResponse(
            {"error": "not found"},
            status_code=404,
            headers={"Cache-Control": "no-store"},
        )

    @app.middleware("http")
    async def public_headers(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method == "OPTIONS" and request.url.path.startswith("/api/v1/"):
            response = Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, CF-Access-Client-Id, CF-Access-Client-Secret",
                    "Access-Control-Max-Age": "86400",
                },
            )
            if (
                origin
                in {"https://localhost", "capacitor://localhost", "http://localhost"}
                and request.headers.get(
                    "access-control-request-private-network", ""
                ).lower()
                == "true"
            ):
                response.headers["Access-Control-Allow-Private-Network"] = "true"
        else:
            response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @public_api.get("/health/live")
    async def live():
        return {"code": "PLATFORM_LIVE_OK"}

    @public_api.get("/health/ready")
    async def ready(request: Request):
        try:
            revisions = await request.app.state.database.fetch(
                "SELECT version_num, current_setting('transaction_read_only') = 'off' "
                "AND NOT pg_is_in_recovery() AS writable "
                "FROM public.alembic_version LIMIT 2"
            )
        except DatabaseError:
            return JSONResponse(
                {"code": "PLATFORM_DATABASE_UNAVAILABLE"}, status_code=503
            )
        if [row["version_num"] for row in revisions] != ["p001_password_register"]:
            return JSONResponse(
                {"code": "PLATFORM_SCHEMA_INCOMPATIBLE"}, status_code=503
            )
        if not revisions[0]["writable"]:
            return JSONResponse(
                {"code": "PLATFORM_DATABASE_READ_ONLY"}, status_code=503
            )
        return JSONResponse({"code": "PLATFORM_READY_OK"})

    @public_api.get("/health")
    async def health(request: Request):
        status = await ready(request)
        if status.status_code != 200:
            return JSONResponse(
                {"ok": False, "writable": False},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            rows = await request.app.state.database.fetch(
                "SELECT identity.public_user_count() AS count"
            )
        except DatabaseError:
            return JSONResponse(
                {"ok": False, "writable": False},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        return JSONResponse(
            {"ok": True, "users": rows[0]["count"], "writable": True},
            headers={"Cache-Control": "no-store"},
        )

    public_api.include_router(
        create_router(
            secret=secret,
            secure=secure,
            session_days=session_days,
            passwords=passwords,
            throttle=throttle,
            password_login_enabled=bool(public_config.get("password_login")),
        )
    )
    public_api.include_router(
        training_router(secret=secret, secure=secure, note_state=training_note_state)
    )

    @public_api.get("/config")
    async def config():
        return JSONResponse(public_config, headers={"Cache-Control": "no-store"})

    app.include_router(public_api)
    return app
