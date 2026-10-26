"""Platform HTTP composition, separate from the synthetic Foundation factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from opengym_platform.core.database import Database, DatabaseError
from opengym_platform.core.platform_settings import load_public_config


def create_app():
    public_config = load_public_config()

    @asynccontextmanager
    async def lifespan(app):
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
        if request.method == "OPTIONS":
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

    @app.get("/health/live")
    async def live():
        return {"code": "PLATFORM_LIVE_OK"}

    @app.get("/health/ready")
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
        if [row["version_num"] for row in revisions] != ["p000_bootstrap"]:
            return JSONResponse(
                {"code": "PLATFORM_SCHEMA_INCOMPATIBLE"}, status_code=503
            )
        if not revisions[0]["writable"]:
            return JSONResponse(
                {"code": "PLATFORM_DATABASE_READ_ONLY"}, status_code=503
            )
        return JSONResponse({"code": "PLATFORM_READY_OK"})

    @app.get("/api/health")
    async def health(request: Request):
        status = await ready(request)
        if status.status_code != 200:
            return JSONResponse(
                {"ok": False, "writable": False},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        # shortcut: p000 has no identities; replace with Identity's public count in S2.
        return JSONResponse(
            {"ok": True, "users": 0, "writable": True},
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/config")
    async def config():
        return JSONResponse(public_config, headers={"Cache-Control": "no-store"})

    return app
