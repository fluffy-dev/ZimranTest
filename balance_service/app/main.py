from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routers import balance
from app.core import lifespan as _lifespan
from app.core.config import settings
from shared.exceptions import FineloBaseException, NotFoundException
from shared.logging import configure_logging

configure_logging(service_name=settings.APP_NAME, log_level=settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _lifespan.startup()
    yield
    await _lifespan.shutdown()


app = FastAPI(
    title="Finelo — Balance Service",
    description="Manages user virtual currency balances for the Finelo platform.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    import uuid
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    structlog.contextvars.unbind_contextvars("correlation_id")
    return response


@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(FineloBaseException)
async def domain_error_handler(request: Request, exc: FineloBaseException) -> JSONResponse:
    logger.error("Domain exception", code=exc.code, message=exc.message)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unexpected error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "InternalServerError", "message": "An unexpected error occurred."}},
    )


@app.get("/health/live")
async def liveness() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness() -> dict:
    from sqlalchemy import text
    from app.db.session import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "checks": {"database": "ok"}}
    except Exception as exc:
        return JSONResponse(
            {"status": "degraded", "checks": {"database": str(exc)}},
            status_code=503,
        )


app.include_router(balance.router, prefix="/api/v1")
