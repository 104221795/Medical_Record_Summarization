# syntax=docker/dockerfile:1.7
# CPU image by default; build with --build-arg ORT_FLAVOR=intel for OpenVINO acceleration.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG ORT_FLAVOR=cpu
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    RAG_ENVIRONMENT=production

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt requirements-rag.txt requirements-rag-onnx.txt requirements-multimodal.txt requirements-mlops.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-mlops.txt \
    && if [ "${ORT_FLAVOR}" = "intel" ]; then \
         python -m pip uninstall -y onnxruntime \
         && python -m pip install "onnxruntime-openvino>=1.21,<2"; \
       elif [ "${ORT_FLAVOR}" != "cpu" ]; then \
         echo "Unsupported ORT_FLAVOR=${ORT_FLAVOR}; use cpu or intel." >&2; exit 1; \
       fi

RUN groupadd --system app && useradd --system --gid app --create-home app
COPY --chown=app:app backend ./backend

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:8080/healthz || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
