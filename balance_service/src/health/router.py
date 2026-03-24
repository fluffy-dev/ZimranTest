from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.config.database.engine import db_helper
from src.lifespan import is_consumer_connected

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", summary="Liveness probe")
async def liveness() -> dict:
    """Returns a simple OK response to indicate the service is alive."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe (checks DB)")
async def readiness() -> JSONResponse:
    """Validates database connectivity by executing a lightweight SQL query."""
    results: dict[str, str] = {}

    try:
        async with db_helper.get_db_session() as session:
            await session.execute(text("SELECT 1"))
        results["database"] = "ok"
    except Exception as exc:
        results["database"] = f"error: {exc}"

    results["messaging"] = "ok" if is_consumer_connected() else "disconnected"

    all_ok = all(v == "ok" for v in results.values())

    return JSONResponse(
        {"status": "ready" if all_ok else "degraded", "checks": results},
        status_code=200 if all_ok else 503,
    )
