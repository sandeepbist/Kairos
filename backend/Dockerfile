# Kairos backend image: serves both the FastAPI API and the Temporal worker
# (same codebase, different entrypoints). Multi-stage for a slim runtime.
# Build context: ./backend  (docker build -f backend/Dockerfile backend/)
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/install -r requirements.txt

FROM python:3.12-slim AS runtime

# libpq5 for asyncpg; curl for healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local/lib/python3.12/site-packages
ENV PYTHONPATH=/app/backend

WORKDIR /app/backend
COPY . .

# Dedicated non-root user
RUN useradd --create-home --uid 10001 kairos && chown -R kairos:kairos /app
USER kairos

ENV PYTHONUNBUFFERED=1

# Default: API server. Worker overrides the entrypoint to
# python -m app.temporal.worker
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
