# Railway Deployment Guide

Target state:

> Railway-ready staging deployment for a de-identified, clinician-review-only Medical Record Summarization PoC.

This guide does not cover production clinical deployment or real EHR integration.

## Recommended Railway Topology

Use a single Railway web service from this repository:

- Dockerfile builds the React frontend.
- FastAPI serves `/api/v1/*` and the React SPA.
- Railway PostgreSQL provides persistence.
- Redis is optional for RQ jobs. The default staging mode can use `in_process`.

Local Ollama providers such as Qwen2.5 and Llama3.2 are not assumed to run on Railway. Keep them as local benchmark/testing providers unless you attach a separate model service.

## Railway Project Setup

1. Create a Railway project.
2. Connect the GitHub repository.
3. Add a PostgreSQL service.
4. Optional: add Redis if testing RQ background jobs.
5. Set the web service builder to Dockerfile or allow Railway to detect `railway.json`.
6. Deploy from `main` after CI passes.

## Required Variables

Set these in the Railway web service:

```text
RAG_ENVIRONMENT=staging
RAG_DATABASE_URL=${{Postgres.DATABASE_URL}}
RAG_AUTH_SECRET_KEY=<long-random-secret>
RAG_CORS_ORIGINS=https://<your-railway-domain>
RAG_JOB_BACKEND=in_process
RAG_RQ_REQUIRE_LIVE_WORKER=false
RAG_EVALUATION_ARTIFACT_ROOT=/app/artifacts
PORT=<provided by Railway>
```

Optional provider/model variables:

```text
RAG_EMBEDDING_PROVIDER=sentence_transformers
RAG_SENTENCE_TRANSFORMERS_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY=false
HF_HOME=/tmp/hf_cache
HF_HUB_CACHE=/tmp/hf_cache/hub
HF_DATASETS_CACHE=/tmp/hf_cache/datasets
TRANSFORMERS_CACHE=/tmp/hf_cache/hub
```

For the lightest staging deployment, you may use:

```text
RAG_EMBEDDING_PROVIDER=hashing
```

This is easier to deploy but is not the recommended retrieval setting for serious benchmark work.

Gemini optional:

```text
GEMINI_API_KEY=<set only if intentionally enabled>
RAG_LLM_PROVIDER=deterministic
RAG_LLM_EXTERNAL_ENABLED=false
RAG_LLM_ALLOW_PHI_EXTERNAL=false
```

Do not set `RAG_LLM_ALLOW_PHI_EXTERNAL=true` unless governance has approved external provider use.

## Start Command

`railway.json` uses:

```bash
python -m alembic -c alembic.ini upgrade head && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}
```

The app must bind to Railway `PORT`. Do not hardcode `8080` in Railway.

## Healthcheck

Railway healthcheck path:

```text
/health
```

Readiness endpoint:

```text
/ready
```

`/ready` checks database/configuration and reports vector/artifact/provider readiness. Optional providers such as Gemini or Ollama should not block the app unless explicitly required.

## Local Docker Staging

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
docker compose up --build
```

Then open:

```text
http://127.0.0.1:8080
http://127.0.0.1:8080/health
http://127.0.0.1:8080/ready
```

The compose file uses a lightweight retrieval setting by default so the container starts reliably from a clean clone.

## Post-Deploy Verification

1. Open `/health`.
2. Open `/ready`.
3. Log in with demo credentials/account.
4. Open Doctor Dashboard.
5. Generate a draft from demo/de-identified patient data.
6. Open Review & Evidence.
7. Inspect citation/evidence links.
8. Confirm unsupported claims remain visible.
9. Start review and reject/request revision or approve only if safety gates allow it.
10. Open Admin Evaluation and Jobs & Readiness.
11. Export audit logs from `/api/v1/audit/export` as an admin/auditor.

## Rollback

Use Railway deployment history to roll back to the previous successful deploy. If a migration has already changed the database schema, verify rollback compatibility before switching traffic.

## Known Limitations

- This is staging/demo only.
- No real EHR writeback.
- No real PHI.
- No clinical safety/effectiveness claims.
- Ollama local models are not part of the default Railway runtime.
- Heavy benchmarks should run manually/local, not in Railway deploy or CI.
