# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Backend image — FastAPI + asyncpg + pgvector + local fastembed embeddings.
# Build context is the REPOSITORY ROOT (see docker-compose.yml / render.yaml),
# hence every COPY path is prefixed with `backend/`.
# ---------------------------------------------------------------------------

FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Compilers + libpq headers are only needed to build wheels that don't ship a
# manylinux binary (e.g. lxml). None of this ends up in the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install into an isolated venv so the runtime stage can copy a clean tree.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt


FROM python:3.13-slim AS runtime

# fastembed honours FASTEMBED_CACHE_PATH; mounting /app/data persists the model.
# Render injects PORT (default 10000); locally we fall back to 8000.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    FASTEMBED_CACHE_PATH=/app/data/fastembed \
    PORT=8000

# libpq5: libpq client library. libgomp1: required by onnxruntime (fastembed).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /app app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app backend/ /app/
# Committed raw snapshots are required for the first ingestion on Render.
COPY --chown=app:app data/ /app/data/

# The fastembed cache lives under /app/data, which is a volume in compose.
RUN mkdir -p /app/data/fastembed && chown -R app:app /app/data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os,sys,urllib.request; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+p+'/health', timeout=4).status == 200 else 1)"

# `exec` keeps uvicorn as PID 1 so SIGTERM is handled for graceful shutdown.
# --forwarded-allow-ips '*' is appropriate behind Render's TLS-terminating proxy
# (rate limiting needs the real client IP from X-Forwarded-For).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips '*'"]
