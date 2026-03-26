from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.balance.router import router as balance_router
from src.health.router import router as health_router
from src.lifespan import lifespan
from src.config.project import settings as project_settings
from src.config.swagger import settings as swagger_settings
from src.config.cors import settings as cors_settings
from shared.logging import configure_logging
from src.config.logging import settings as log_settings

from shared.exceptions import (
    AttemptAlreadyCompletedException,
    ConflictException,
    FineloBaseException,
    NotFoundException,
    ValidationException,
    ForbiddenException
)

configure_logging(service_name="balance-service", log_level=log_settings.logging_level)
logger = structlog.get_logger(__name__)


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


@app.exception_handler(AttemptAlreadyCompletedException)
async def attempt_completed_exception_handler(request, exc: AttemptAlreadyCompletedException):
    """Maps AttemptAlreadyCompletedException to an HTTP 409 Conflict response."""
    return JSONResponse(
        status_code=409,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request, exc: ForbiddenException):
    """Maps ForbiddenException to an HTTP 403 Forbidden response."""
    return JSONResponse(
        status_code=403,
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

router = APIRouter(prefix="/api/v1", tags=["API"])


router.include_router(balance_router)

app.include_router(router)
app.include_router(health_router)