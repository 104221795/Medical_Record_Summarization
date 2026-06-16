# Deployment Readiness Audit

Status: Railway staging preparation for a de-identified, clinician-review-only PoC.

## Repository Surface

| Area | Current finding |
| --- | --- |
| Frontend | React + Vite in `frontend/`; build command: `npm run build`. |
| Backend | FastAPI in `backend/app`; start command: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. |
| API base URL | Frontend supports `VITE_API_PREFIX` and `VITE_API_BASE_URL`; local default is `/api/v1`. |
| Database | SQLAlchemy + Alembic; SQLite local default, PostgreSQL/Railway via `RAG_DATABASE_URL` or `DATABASE_URL`. |
| Retrieval/vector | RAG service supports hashing, FastEmbed, sentence-transformers, and Qdrant-compatible vector store. |
| Benchmarks | Main Flow 2.1 runner: `scripts/run_rag_grounded_benchmark.py`; local artifacts commonly live under `D:/clin_summ_outputs`. |
| Environment files | `.env.example` exists; `.env` and `.env.*` are ignored. |
| Docker | Single-service Dockerfile builds frontend and serves it from FastAPI. |
| CI | GitHub Actions runs lightweight backend smoke/safety tests and frontend build. |
| Railway | `railway.json` uses Dockerfile, `/health`, and `$PORT`. |
| Doctor pages | Dashboard, Patients, Generate Summary, Review & Evidence, Patient History, Audit History, User Guide. |
| Admin pages | Dashboard, Evaluation, Benchmark Results, Flow Comparison, Jobs & Readiness, Human Evaluation. |
| Tests | Backend pytest tests exist; deployment smoke tests were added for health/readiness/golden-path basics. |

## Current Deployment Blockers

- Real EHR use is blocked by design; only mock/de-identified demo data is allowed.
- Railway should not depend on local Windows paths such as `D:\hf_cache` or `D:\ollama_models`.
- Ollama/Qwen/Llama are local testing providers and are not assumed to run on Railway.
- Heavy benchmark/model downloads are manual and must not run in CI.
- If using sentence-transformers on Railway, startup may download/cache models unless baked into the image or provided by a volume/cache.

## Missing Or Risky Environment Variables

- `RAG_AUTH_SECRET_KEY` must be set to a real secret in Railway.
- `RAG_DATABASE_URL` or Railway `DATABASE_URL` must point to a Railway PostgreSQL service.
- `RAG_CORS_ORIGINS` must include the deployed frontend domain if frontend/backend are split.
- `RAG_EVALUATION_ARTIFACT_ROOT` should be set if Admin Evaluation needs persisted artifacts.
- Gemini requires `GEMINI_API_KEY`/`RAG_GEMINI_API_KEY` only when intentionally enabled.

## Risky Files Not To Commit

- `.env`, `.env.*`
- model caches: `hf_cache/`, `ollama_models/`
- vector stores: `.qdrant/`, `qdrant_storage/`
- local databases and runtime folders: `var/`, `backend/var/`
- benchmark outputs: `outputs/`, `output/`, `results/`, `D:/clin_summ_outputs`
- credentialed/raw datasets under `data/raw`, `data/credentialed`, and MIMIC folders

## Responsive Risks

- Dense benchmark/admin tables require horizontal scroll on mobile.
- Review & Evidence is dense by nature; mobile uses tabbed panels.
- Sticky doctor action bars must become static on tablet/mobile to avoid covering content.

## Healthcheck Status

- `/health` and `/healthz` return process health.
- `/ready` validates database/configuration and reports vector/artifact/provider readiness without failing optional providers.
