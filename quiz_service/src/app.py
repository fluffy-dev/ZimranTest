from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.health.router import router as health_router
from src.quiz.router import router as quizzes_router
from src.attempt.router import router as attempts_router
from src import lifespan as _lifespan
from src.config.project import settings as project_settings
from src.config.swagger import settings as swagger_settings
from src.config.cors import settings as cors_settings
from shared.exceptions import (
    AttemptAlreadyCompletedException,
    ConflictException,
    FineloBaseException,
    NotFoundException,
    ValidationException,
)
from shared.logging import configure_logging

configure_logging(service_name="quiz-service", log_level="INFO")
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
    """Injects a correlation ID into every request for distributed tracing."""
    import uuid

    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    structlog.contextvars.unbind_contextvars("correlation_id")
    return response



@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    """Returns 404 for domain-level not-found errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ConflictException)
async def conflict_handler(request: Request, exc: ConflictException) -> JSONResponse:
    """Returns 409 for state conflict errors."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ValidationException)
async def validation_handler(request: Request, exc: ValidationException) -> JSONResponse:
    """Returns 422 for business validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(FineloBaseException)
async def domain_error_handler(request: Request, exc: FineloBaseException) -> JSONResponse:
    """Returns 500 for unhandled domain errors."""
    logger.error("Unhandled domain exception", code=exc.code, message=exc.message)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches all unexpected errors and returns a generic 500 response."""
    logger.exception("Unexpected error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "InternalServerError", "message": "An unexpected error occurred."}},
    )





api_v1 = APIRouter(prefix='/api/v1', tags=["API"])

api_v1.include_router(quizzes_router)
api_v1.include_router(attempts_router)

app.include_router(health_router)
app.include_router(api_v1)
