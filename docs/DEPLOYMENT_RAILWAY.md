# Railway Staging Deployment

Target:

> Railway-ready staging deployment for a de-identified, clinician-review-only Medical Record Summarization PoC.

This is not a production clinical system, a clinical decision system, or evidence of clinical safety/effectiveness. AI output remains a draft until clinician review.

## Dependency and Image Boundary

The Dockerfile installs `requirements-runtime.txt` only. That file contains the
FastAPI web/worker, database, Redis/RQ, provider API, readiness, and lightweight
retrieval dependencies needed by Railway.

The root `requirements.txt` is the full local research/development install. It
also includes `requirements-ml.txt` and `requirements-test.txt`, so it is not
used by the Railway image. Local ML and benchmark packages—including Torch,
Transformers, sentence-transformers, BERTScore, datasets, evaluate, MLflow, and
sentencepiece—remain outside the Railway runtime.

```bash
# Railway-equivalent runtime
python -m pip install -r requirements-runtime.txt

# Full local research/development environment
python -m pip install -r requirements.txt
```

## Required Railway Topology

- Web service: Dockerfile, FastAPI, compiled React SPA.
- Worker service: same Docker image, separate start command.
- PostgreSQL service.
- Redis service.
- Optional persistent volume mounted at `/app/artifacts` for a prepared benchmark snapshot.

Web start command:

```bash
python -m alembic -c alembic.ini upgrade head && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

Worker start command:

```bash
python -m scripts.run_rq_worker --worker-class default
```

Do not use the Windows worker class on Railway.

## Required Variables

Configure the same runtime variables on web and worker services unless noted:

```text
RAG_ENVIRONMENT=staging
DEPLOYMENT_MODE=railway
PRIMARY_PROVIDER=gemini2.5_flash_lite
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
RAG_JOB_BACKEND=rq
RAG_JOB_FALLBACK_TO_IN_PROCESS=false
RAG_RQ_REQUIRE_LIVE_WORKER=true
BACKGROUND_JOBS_ENABLED=true
REDIS_REQUIRED=true
RAG_ALLOW_DEMO_HEADER_AUTH=false
RAG_AUTH_SECRET_KEY=<long random Railway secret>
CORS_ORIGINS=https://<your-web-service-domain>
RAG_EMBEDDING_PROVIDER=hashing
LOCAL_OLLAMA_ENABLED=false
OLLAMA_BASE_URL=
GEMINI_API_KEY=<Railway secret>
HF_HOME=/tmp/hf_cache
HF_HUB_CACHE=/tmp/hf_cache/hub
HF_DATASETS_CACHE=/tmp/hf_cache/datasets
TRANSFORMERS_CACHE=/tmp/hf_cache/hub
RAG_EVALUATION_ARTIFACT_ROOT=/app/artifacts
BENCHMARK_SNAPSHOT_DIR=/app/artifacts
```

Railway injects `PORT` into the web service. The worker does not need a public port.

## Provider Strategy

- Gemini 2.5 Flash Lite: deployment primary; selectable only when its API key is configured.
- Deterministic: lightweight deployment smoke fallback.
- Qwen2.5/Llama3.2: disabled on Railway unless `LOCAL_OLLAMA_ENABLED=true`, `OLLAMA_BASE_URL` points to a reachable Ollama service, and the requested model is present.
- BART/Pegasus: local/offline benchmark providers; not required for Railway startup.

The deployment image intentionally uses hashing-based retrieval so the Railway
staging runtime does not require sentence-transformers, Torch, local model
caches, or Hugging Face downloads. This validates deployment feasibility and
the clinician-review workflow only; it is not a clinical-performance,
effectiveness, or safety claim.

The application must start when optional providers are unavailable. Provider unavailability is surfaced through `/api/v1/providers`, `/ready`, and the doctor selector.

## Authentication and CORS

- Staging protected routes require a signed bearer token.
- Client-controlled role headers are ignored in staging.
- Public admin self-registration is disabled.
- `RAG_AUTH_SECRET_KEY` must not use the development default.
- Wildcard CORS is rejected in staging.
- Configure only the deployed HTTPS frontend origin.

## Health and Readiness

```text
GET /health
GET /ready
```

`/health` proves the web process is alive.

`/ready` reports:

- database connectivity;
- Redis reachability;
- queue depth;
- active persisted jobs;
- live RQ/Windows worker count and Windows heartbeat age where applicable;
- provider selectability and primary-provider status;
- vector-store mode;
- benchmark artifact availability;
- staging configuration warnings.

In Railway mode, missing database, Redis, or worker readiness returns HTTP 503. Optional local providers do not make the service unavailable.

## Deployment Sequence

1. Provision PostgreSQL and Redis.
2. Create the web service from this repository.
3. Create a second service from the same repository for the worker.
4. Apply the variables above to both services.
5. Override the worker start command.
6. Deploy web; migrations run before Uvicorn starts.
7. Deploy worker.
8. Confirm `/health` returns 200.
9. Confirm `/ready` returns 200 and reports at least one worker.
10. Run a deterministic draft smoke.
11. Run a Gemini draft smoke with de-identified/demo data.

## Post-Deploy QA

- Log in with a seeded/approved account.
- Confirm changing `X-Role-Code` cannot elevate privileges.
- Select a de-identified patient and encounter.
- Confirm unavailable providers are disabled with a reason.
- Generate a draft through the background worker.
- Refresh during generation and verify persisted job state remains queryable.
- Open Review & Evidence.
- Verify citations, unsupported claims, conflicts, and missing evidence remain visible.
- Verify approval remains blocked for safety-critical unsupported claims.
- Confirm audit export is PHI-safe.
- Confirm Admin Evaluation loads a prepared snapshot or shows a graceful empty state.

## Rollback

Use Railway deployment history to roll back web and worker to the previous successful image. Database migrations in this PoC are forward-oriented; verify schema compatibility before rolling application code back.

## Local Compose

```powershell
docker compose up --build
```

Compose starts web, worker, PostgreSQL, and Redis with deterministic/hash-based smoke settings. It does not validate Gemini or Ollama.
