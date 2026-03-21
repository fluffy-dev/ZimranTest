from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", summary="Liveness probe")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe (checks DB + Redis)")
async def readiness() -> dict:
    from app.core.lifespan import redis_client

    results: dict[str, str] = {}

    # Check DB
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        results["database"] = "ok"
    except Exception as exc:
        results["database"] = f"error: {exc}"

    # Check Redis
    try:
        if redis_client:
            await redis_client.ping()
            results["redis"] = "ok"
        else:
            results["redis"] = "not initialized"
    except Exception as exc:
        results["redis"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in results.values())
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        {"status": "ready" if all_ok else "degraded", "checks": results},
        status_code=status_code,
    )
