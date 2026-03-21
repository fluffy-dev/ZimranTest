from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.balance.router import router as balance_router
from src import lifespan as _lifespan
from src.config.project import settings as project_settings
from src.config.swagger import settings as swagger_settings
from src.config.cors import settings as cors_settings
from shared.exceptions import FineloBaseException, NotFoundException
from shared.logging import configure_logging

configure_logging(service_name="balance-service", log_level="INFO")
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _lifespan.startup()
    yield
    await _lifespan.shutdown()


app = FastAPI(
    title=swagger_settings.title,
    description=swagger_settings.description,
    summary=swagger_settings.summary,
    version=project_settings.version,
    terms_of_service=swagger_settings.terms_of_service,
    contact=swagger_settings.contact,
    license_info=swagger_settings.license,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    docs_url=swagger_settings.docs_url,
    redoc_url=swagger_settings.redoc_url,
    default_response_class=JSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.allow_origins,
    allow_credentials=cors_settings.allow_credentials,
    allow_methods=cors_settings.allow_methods,
    allow_headers=cors_settings.allow_headers,
    expose_headers=cors_settings.expose_headers,
    max_age=cors_settings.max_age,
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
    from src.config.database.session import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "checks": {"database": "ok"}}
    except Exception as exc:
        return JSONResponse(
            {"status": "degraded", "checks": {"database": str(exc)}},
            status_code=503,
        )


app.include_router(balance_router, prefix="/api/v1")
