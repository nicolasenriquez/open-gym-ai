"""Internal Foundation health probes; no business or authentication contract."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from opengym_platform.core.database import DatabaseError

router = APIRouter(prefix="/health")


@router.get("/live")
async def live() -> dict[str, str]:
    return {"code": "FOUNDATION_LIVE_OK"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    try:
        revisions = await request.app.state.database.fetch(
            "SELECT version_num FROM public.alembic_version LIMIT 2"
        )
    except DatabaseError:
        return JSONResponse(
            {"code": "FOUNDATION_DATABASE_UNAVAILABLE"}, status_code=503
        )
    if [row["version_num"] for row in revisions] != ["0002_health_readiness"]:
        return JSONResponse({"code": "FOUNDATION_SCHEMA_INCOMPATIBLE"}, status_code=503)
    return JSONResponse({"code": "FOUNDATION_READY_OK"})
