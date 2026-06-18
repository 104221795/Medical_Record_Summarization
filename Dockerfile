# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_PREFIX=/api/v1
ARG VITE_API_BASE_URL=
ENV VITE_API_PREFIX=${VITE_API_PREFIX}
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    RAG_EMBEDDING_PROVIDER=hashing \
    RAG_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY=false \
    RUN_REAL_BASELINES=0 \
    RAG_RUN_REAL_BASELINES=0 \
    LOCAL_OLLAMA_ENABLED=false \
    HF_HOME=/tmp/hf_cache \
    HF_HUB_CACHE=/tmp/hf_cache/hub \
    HF_DATASETS_CACHE=/tmp/hf_cache/datasets \
    TRANSFORMERS_CACHE=/tmp/hf_cache/hub

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-runtime.txt

RUN groupadd --system app \
    && useradd --system --gid app --create-home app \
    && mkdir -p /app/var /app/artifacts \
    && chown -R app:app /app/var /app/artifacts

COPY --chown=app:app alembic.ini ./
COPY --chown=app:app backend ./backend
COPY --chown=app:app src ./src
COPY --chown=app:app prompts ./prompts
COPY --chown=app:app scripts ./scripts
COPY --from=frontend-build --chown=app:app /app/frontend/dist ./frontend/dist

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl --fail --silent "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["sh", "-c", "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
