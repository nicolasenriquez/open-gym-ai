"""Compose the isolated Foundation app; no migrations or business routes."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from opengym_platform.core.database import Database
from opengym_platform.health import router


def create_app(settings):
    @asynccontextmanager
    async def lifespan(app):
        database = await Database.open(settings)
        app.state.database = database
        try:
            yield
        finally:
            await database.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    app.include_router(router)

    return app
