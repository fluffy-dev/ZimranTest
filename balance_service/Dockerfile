# ── Stage 1: Build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY shared/ /shared
RUN uv pip install --system --no-cache /shared

COPY balance_service/pyproject.toml .
RUN uv pip install --system --no-cache .

# ── Stage 2: Production image ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN useradd --create-home --shell /bin/bash finelo
WORKDIR /home/finelo/app
USER finelo

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY balance_service/app ./app
COPY balance_service/alembic.ini .
COPY balance_service/alembic ./alembic

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/home/finelo/app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health/live')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
