# Medical Record Summarization MVP

Evidence-grounded clinical summarization prototype with doctor-facing review,
admin evaluation, dataset governance, RAG retrieval, local/cloud provider
testing, and optional Redis/RQ background jobs.

This project is a local/development MVP. It is not a production HIS/EMR
integration. Use mock or de-identified data for local development, demos, and
tests.

Proxy evaluation only. These results do not demonstrate hospital-grade
validation, live-care performance, or real-world healthcare outcomes. Real EHR
evaluation would require credentialed datasets such as MIMIC-IV-Note or
MIMIC-IV-BHC under approved governance processes.

## Project Status

The system now supports:

- Doctor workflow for patient-scoped draft summary generation and evidence review.
- RAG-first summarization path using MiniLM retrieval and Qdrant-compatible vector search.
- Provider testing with deterministic baseline, BART, Pegasus, Qwen2.5, Llama3.2, and optional Gemini 2.5 Flash Lite.
- Admin evaluation dashboards for benchmark results, provider readiness, jobs, human review, and failure analysis.
- Dataset governance and diversity assets for proxy evaluation.
- Redis/RQ background job mode for long-running model generation, plus local in-process mode for stable development.
- Completed Flow 2.1 evaluation with ROUGE, BERTScore, citation metrics, clinical proxy metrics, failure labels, and human review rubric exports.

## Week 5 Focus

Major feature scope is frozen for the final demonstration. P0-P2 implementation
and automated analysis are complete. The remaining priority is:

1. capture doctor/admin UI screenshots;
2. record the end-to-end demo;
3. collect real human-review scores using the blinded protocol;
4. package approved evidence and verify reviewer access.

Public cloud deployment is optional future work. It is not required for the
current demo or delivery.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, React Router, JSX, lucide-react, custom medical SaaS UI components |
| Backend API | FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | PostgreSQL recommended, SQLite fallback |
| Background jobs | Local in-process runner by default, optional Redis/RQ durable queue |
| Retrieval | MiniLM embeddings through `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | Qdrant-compatible service wrapper, local path or Qdrant URL |
| Clinical context | Section-aware chunking, rule/regex section classification, clinical context builder v2 |
| Local LLMs | Ollama models: `qwen2.5:3b`, `llama3.2:3b` |
| HF models | `facebook/bart-large-cnn`, `google/pegasus-pubmed`, optional Pegasus variants, `roberta-large` for BERTScore |
| Cloud provider | Gemini 2.5 Flash Lite, optional and governed |
| Evaluation | ROUGE, BERTScore, citation coverage, unsupported claim rate, failure analysis, latency, provider comparison |
| Local model cache | Configurable through environment variables; `D:\hf_cache` and `D:\ollama_models` are optional Windows examples |

## Architecture

```mermaid
flowchart LR
    User[Doctor or Admin] --> FE[React Frontend]
    FE --> API[FastAPI Backend]

    API --> Auth[Auth and RBAC]
    API --> Patients[Patients, Encounters, Documents]
    API --> Summary[Summary Service]
    API --> Review[Review and Audit Service]
    API --> Eval[Evaluation Service]
    API --> Jobs[Model Jobs Service]

    Patients --> DB[(PostgreSQL or SQLite)]
    Summary --> Context[Clinical Context Builder v2]
    Context --> Retrieval[RAG Retrieval]
    Retrieval --> Chunking[Chunking and Section Classification]
    Chunking --> MiniLM[MiniLM Embeddings]
    MiniLM --> VectorStore[Qdrant Vector Store]
    Retrieval --> Evidence[Retrieved Evidence]
    Evidence --> Providers[Provider Gateway]

    Providers --> Deterministic[Deterministic]
    Providers --> BART[BART]
    Providers --> Pegasus[Pegasus]
    Providers --> Ollama[Qwen2.5 and Llama3.2 via Ollama]
    Providers --> Gemini[Gemini Optional]

    Summary --> Citations[Citation Validation]
    Citations --> Review
    Review --> Audit[Audit Trail]
    Audit --> DB

    Jobs --> Redis[(Redis Queue)]
    Redis --> Worker[RQ Worker]
    Worker --> Summary
    Jobs --> DB

    Eval --> Artifacts[CSV, JSONL, Reports]
```

## Summarization Flows

| Flow | Name | Purpose | Status |
| --- | --- | --- | --- |
| Flow 1 | Raw Summarization | Send normalized source note directly to summarizer for baseline comparison | Available for benchmark comparison |
| Flow 1.5 | Clinical Context | Build structured context before summarization | Available for controlled comparison |
| Flow 2 | RAG Grounded | Chunk, embed, retrieve evidence, summarize, validate citations | Main recommended doctor workflow direction |
| Flow 2.1 | RAG Best Models | RAG comparison across deterministic, BART, Pegasus, Qwen2.5, and Llama3.2 | Completed on 50 records for all five providers; available in Admin Evaluation |

Recommended current path for doctor-facing testing:

```text
Doctor generation
  -> patient/encounter scoped notes
  -> chunking
  -> section-aware retrieval queries
  -> MiniLM embedding
  -> Qdrant retrieval
  -> clinical context builder v2
  -> provider generation
  -> citation validation
  -> doctor review
```

## Provider Matrix

| Provider | Model | Runtime | Current role |
| --- | --- | --- | --- |
| deterministic | `deterministic_sentence_baseline` | local Python | Fast baseline and safe smoke test |
| bart | `facebook/bart-large-cnn` | Hugging Face local cache | Proxy benchmark baseline |
| pegasus | `google/pegasus-pubmed` | Hugging Face local cache | Medical/scientific proxy baseline |
| qwen2.5 | `ollama/qwen2.5:3b` | Ollama local | Strong RAG testing provider |
| llama3.2 | `ollama/llama3.2:3b` | Ollama local | Strong RAG testing provider |
| gemini2.5_flash_lite | `gemini/gemini-2.5-flash-lite` | external API | Optional governed cloud provider |

For Qwen/Llama, use:

```env
LLM_GATEWAY_MODE=litellm
OLLAMA_MODELS=D:\ollama_models
OLLAMA_API_BASE=http://127.0.0.1:11434
```

With `LLM_GATEWAY_MODE=litellm`, local Ollama models are called through
LiteLLM's Python client. A separate LiteLLM proxy on port `4000` is only needed
when using `LLM_GATEWAY_MODE=proxy`.

## Run Guide

### 1. Install

Choose the dependency set for the work you intend to run:

```powershell
# Lightweight Docker web/worker runtime; excludes local ML and benchmark stacks.
python -m pip install -r requirements-runtime.txt

# Full local research/development environment, including ML and tests.
python -m pip install -r requirements.txt
```

The root `requirements.txt` composes `requirements-runtime.txt`,
`requirements-ml.txt`, and `requirements-test.txt`. The lightweight Docker
image installs only `requirements-runtime.txt`, so it does not install Torch,
Transformers, sentence-transformers, BERTScore, MLflow, or CUDA/NVIDIA wheels.

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Apply Database Migrations

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

### 3. Run Backend In Stable Local Mode

This is the recommended default while building or demoing the doctor UI.

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
.\.venv\Scripts\python.exe -m scripts.run_backend --job-backend in_process
```

### 4. Run Redis/RQ Test Mode

Use this when testing background jobs before deployment.

Terminal 1 - Redis:

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
.\.venv\Scripts\python.exe -m scripts.run_redis_dev --start
```

Terminal 2 - Backend:

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
.\.venv\Scripts\python.exe -m scripts.run_backend --job-backend rq
```

Terminal 3 - Worker:

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
.\.venv\Scripts\python.exe -m scripts.run_rq_worker
```

### 5. Test Redis/RQ Quickly

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
.\.venv\Scripts\python.exe -m scripts.cleanup_rq_state
.\.venv\Scripts\python.exe -m scripts.smoke_rq_job --run-worker-burst
```

Expected smoke path:

```text
queued_rq -> worker picked job -> completed
```

Current verification:

```text
Redis/RQ smoke pass
backend background job regression: 6 passed
```

### 6. Run Frontend

```powershell
Set-Location "D:\MyNewDesktop\clin-summ\frontend"
npm install
npm run dev
```

Default URLs:

```text
Backend:  http://127.0.0.1:8080
Frontend: http://127.0.0.1:5173
API docs: http://127.0.0.1:8080/docs
Health:   http://127.0.0.1:8080/health
Ready:    http://127.0.0.1:8080/ready
```

### 7. Run Docker Local Staging

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
docker compose up --build
```

The compose profile builds the React frontend, serves it through FastAPI, starts PostgreSQL and Redis, and exposes the app at:

```text
http://127.0.0.1:8080
```

Docker Compose is the current verified staging and final-demo path. It
bind-mounts the portable benchmark package from `artifacts/evaluation` into
`/app/artifacts`.

Use the executable checklist:

```text
docs/demo/LOCAL_DOCKER_COMPOSE_DEMO_CHECKLIST.md
```

### 8. Optional Future Railway Staging

Railway uses `railway.json`, the root `Dockerfile`, and the Railway-provided `PORT`.
The image uses the hashing retrieval path to keep the staging web/worker runtime
small and independent of local Hugging Face model execution. This is a runtime
feasibility choice for the de-identified staging PoC, not a clinical-performance
claim.

Railway provider strategy:

- Gemini is the primary Railway provider when its API key is configured and
  external use is approved for the de-identified staging data.
- Deterministic is the smoke-test fallback.
- Qwen/Llama through Ollama remain local benchmark providers unless a reachable
  external `OLLAMA_BASE_URL` is explicitly configured and readiness succeeds.
- BART/Pegasus remain local/offline benchmark providers and are not installed in
  the Railway runtime image.

This is retained as optional future architecture documentation. It is not a
current Week 5 requirement.

Detailed deployment guide:

```text
docs/DEPLOYMENT_RAILWAY.md
```

Deploy this only as a de-identified, clinician-review-only staging PoC.

## Environment Configuration

The repository uses `.env` as the persistent local runtime configuration.

Important values:

```env
RAG_DATABASE_URL=postgresql+psycopg://clin_summ:clin_summ_dev@127.0.0.1:5433/clin_summ

HF_HOME=D:\hf_cache
HF_HUB_CACHE=D:\hf_cache\hub
HF_DATASETS_CACHE=D:\hf_cache\datasets
TRANSFORMERS_CACHE=D:\hf_cache\hub

RAG_EMBEDDING_PROVIDER=sentence_transformers
RAG_SENTENCE_TRANSFORMERS_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY=true

RAG_EVALUATION_ARTIFACT_ROOT=artifacts/evaluation

OLLAMA_MODELS=D:\ollama_models
OLLAMA_API_BASE=http://127.0.0.1:11434
LLM_GATEWAY_MODE=litellm

RAG_JOB_BACKEND=in_process
RAG_REDIS_URL=redis://127.0.0.1:6379/0
RAG_RQ_QUEUE_NAME=clin_summ_jobs
RAG_JOB_FALLBACK_TO_IN_PROCESS=true
RAG_RQ_REQUIRE_LIVE_WORKER=true
```

Notes:

- `RAG_JOB_BACKEND=in_process` keeps the original stable local behavior.
- `RAG_JOB_BACKEND=rq` enables Redis/RQ queue mode.
- `RAG_JOB_FALLBACK_TO_IN_PROCESS=true` prevents Redis issues from blocking local demos.
- `RAG_CORS_ORIGINS` should include the frontend domain when frontend/backend are split.
- `VITE_API_BASE_URL` is only needed when the React frontend is hosted on a different domain from the backend.
- Do not commit real API keys or credentialed datasets.

## Frontend Routes

| Area | Route | Purpose |
| --- | --- | --- |
| Public | `/` | Home page |
| Public | `/about` | Project mission and architecture |
| Public | `/login` | Login |
| Public | `/signup` | Signup |
| Doctor | `/doctor/dashboard` | Doctor landing dashboard |
| Doctor | `/doctor/patients` | Patient list |
| Doctor | `/doctor/generate-summary` | Generate draft summary |
| Doctor | `/doctor/review` | Review and evidence workspace |
| Doctor | `/doctor/history` | Patient/history related review records |
| Admin | `/admin/dashboard` | Admin overview |
| Admin | `/admin/evaluation` | Evaluation dashboard |
| Admin | `/admin/evaluation/benchmark` | Benchmark results |
| Admin | `/admin/evaluation/flow-comparison` | Same-record flow comparison |
| Admin | `/admin/jobs` | Model jobs and readiness |
| Admin | `/admin/human-evaluation` | Human evaluation workflow |
| Admin | `/admin/datasets` | Dataset governance |
| Admin | `/admin/audit` | Audit logs |

## Main Backend APIs

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process healthcheck for Docker/Railway |
| `GET /ready` | Structured readiness check for database, config, artifacts, and provider catalog |
| `GET /api/v1/providers` | Provider metadata and readiness |
| `GET /api/v1/patients` | List patients |
| `GET /api/v1/patients/{patient_id}` | Patient detail |
| `POST /api/v1/patients/{patient_id}/summaries/generate` | Synchronous draft generation |
| `POST /api/v1/patients/{patient_id}/summaries/generate-async` | Background draft generation |
| `GET /api/v1/jobs` | List model jobs |
| `GET /api/v1/jobs/readiness` | Cache, model, provider, and queue readiness |
| `POST /api/v1/jobs/{job_id}/cancel` | Cancel a job |
| `GET /api/v1/summaries/{summary_id}` | Summary detail with citations |
| `POST /api/v1/summaries/{summary_id}/review/start` | Start doctor review |
| `PATCH /api/v1/summaries/{summary_id}/edit` | Save doctor edits |
| `POST /api/v1/summaries/{summary_id}/approve` | Approve reviewed summary |
| `POST /api/v1/summaries/{summary_id}/reject` | Reject summary |
| `GET /api/v1/evaluation/benchmark/results` | Benchmark results and artifact status |
| `GET /api/v1/evaluation/benchmark/flow-comparison` | Same-record flow comparison |
| `GET /api/v1/audit/export` | PHI-safe audit export for admin/auditor roles |
| `GET /api/v1/evaluation/human/rubric` | Human evaluation rubric |
| `GET /api/v1/evaluation/human/analytics` | Human review analytics |

## Doctor Workflow

The doctor workflow is evidence-first:

1. Select patient and encounter.
2. Select provider.
3. Generate draft using RAG-first context.
4. Inspect generated summary with inline citations.
5. Hover/click citations to view source evidence.
6. Review unsupported claims and missing diagnosis/medication/timeline flags.
7. Edit, approve, reject, or request revision.
8. Store review event, diff, reason, signature, and audit trail.

AI output remains a draft until approved by an authorized doctor.

## RAG Pipeline Details

### Section Classification

Clinical text is chunked and section-labeled using deterministic rules and
regular expressions. The system recognizes evidence categories such as:

- Diagnosis
- Medications
- Timeline
- Diagnostics
- Assessment
- Plan
- Unknown or missing evidence

The section labels then guide retrieval queries and clinical context assembly.

### Retrieval

Current default embedding model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Configured cache:

```text
HF_HOME=D:\hf_cache
HF_HUB_CACHE=D:\hf_cache\hub
HF_DATASETS_CACHE=D:\hf_cache\datasets
TRANSFORMERS_CACHE=D:\hf_cache\hub
```

Important note: if an old vector index was built using the development hashing
embedder, changing config is not enough. Reingest or rebuild the vector index so
all chunk vectors are regenerated with MiniLM.

### Context Builder v2

The structured context sent to providers is organized as:

```text
[Patient Snapshot]
[Diagnosis Evidence]
[Medication Evidence]
[Timeline Evidence]
[Diagnostics Evidence]
[Assessment Evidence]
[Plan Evidence]
[Unknown / Missing Evidence]
```

This reduces hallucination risk and makes evidence review easier for doctors.

## Evaluation and Benchmarking

The evaluation system supports:

- ROUGE-1, ROUGE-2, ROUGE-L.
- BERTScore.
- Citation coverage.
- Unsupported claim rate.
- Missing diagnosis rate.
- Missing medication rate.
- Timeline completeness.
- Hallucinated clinical entity proxy.
- Critical information omission proxy.
- Failure pattern analysis.
- Per-record prediction JSONL.
- Model comparison CSV.
- Markdown reports.
- Human evaluation rubric and export-ready review records.

Benchmark flows:

- Flow 1 Raw Summarization.
- Flow 1.5 Clinical Context.
- Flow 2 RAG Grounded.
- Flow 2.1 RAG Best Models.

### Latest Flow 2.1 Result

The latest pre-diversity Flow 2.1 run evaluated 50 MultiClinSum proxy records
with five providers. Every provider completed 50/50 records, for 250/250
completed predictions and zero failed predictions.

BERTScore was computed afterward from the saved prediction/reference pairs; the
generation models were not rerun. The evaluator used `roberta-large` on CPU
with batch size 2.

| Provider | Completion | ROUGE-L | BERTScore P | BERTScore R | BERTScore F1 | Citation coverage | Faithfulness proxy | Critical omission | Latency p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Deterministic | 50/50 | `0.1737` | `0.7440` | `0.8546` | `0.7952` | `0.9147` | `0.9071` | `0.3688` | `0.00 ms` |
| BART | 50/50 | `0.0757` | `0.8217` | `0.7815` | `0.8010` | `0.1307` | `0.7585` | `0.9583` | `59,018.25 ms` |
| Pegasus CNN/DailyMail | 50/50 | `0.1495` | `0.8381` | `0.8091` | `0.8232` | `0.3800` | `0.7626` | `0.9236` | `50,691.55 ms` |
| Qwen2.5 | 50/50 | `0.2122` | `0.8118` | `0.8690` | `0.8391` | `0.8884` | `0.8713` | `0.4460` | `46,864.95 ms` |
| Llama3.2 | 50/50 | `0.1863` | `0.7796` | `0.8545` | `0.8149` | `0.8620` | `0.8413` | `0.5108` | `65,747.15 ms` |

Qwen2.5 is the strongest generative PoC provider in this run by ROUGE-L,
BERTScore F1, citation coverage, and faithfulness proxy. Deterministic remains
the most reliable smoke/control provider. BART and Pegasus remain useful
baselines, but their semantic similarity scores do not compensate for weak
citation coverage and high omission proxies.

This run disabled retrieval blocking only for benchmark completion. The
separate gated run remains evidence that insufficient retrieval can block
generation. The doctor-facing workflow retains its retrieval and clinical
safety gates.

Artifacts:

```text
artifacts/evaluation/rag_best_models_benchmark_50_no_gate
artifacts/evaluation/rag_best_models_benchmark_50_gated
artifacts/evaluation/week5_analysis
```

Admin pages load this run through:

```text
artifacts/evaluation/latest_rag_best_models.json
```

Set `RAG_EVALUATION_ARTIFACT_ROOT` to use another location. Existing
`D:\clin_summ_outputs` folders remain an optional backward-compatible discovery
fallback, but they are no longer required on another machine.

These are proxy evaluation results. They do not establish hospital-grade
validation, live-care performance, or real EHR performance. Generated summaries
remain clinician-review-only drafts.

### Week 5 P1/P2 Analysis

The saved 50-record artifacts were analyzed without rerunning generation or
retrieval models. The package adds:

- balanced easy/medium/hard source strata (17/16/17 records);
- provider-by-stratum metrics and failure taxonomy;
- a focused study of the two section-aware retrieval-gate blocks;
- exploratory ROUGE/BERTScore/grounding correlations;
- historical Flow 1/1.5/2/2.1 comparison on common records;
- post-hoc retrieval-threshold sensitivity;
- a blinded 12-case human-review package with intentionally blank scores.

Run or regenerate the analysis with:

```powershell
python -m scripts.analyze_week5_evaluation
```

The human-review package is ready, but real clinician/reviewer scoring remains
pending. AI-generated scores must not be presented as human evaluation.

Typical benchmark artifact locations:

```text
artifacts/evaluation/medium_benchmark
artifacts/evaluation/medium_benchmark_bart_pegasus
artifacts/evaluation/rag_grounded_benchmark
artifacts/evaluation/rag_best_models_benchmark_50_no_gate
```

Admin dashboards read available benchmark artifacts and show provider readiness,
model comparison, failure analysis, and per-record review views.

## Dataset Governance

Current dataset work includes:

- MultiClinSum governed benchmark set.
- MTS-Dialog and MEDIQA-Sum support planning.
- Synthetic structured EHR cases.
- Messy formatting cases.
- Stratified subsets by note length, diagnosis density, medication density, and timeline complexity.

Dataset governance separates:

- Benchmark-ready records.
- Warning records.
- Rejected records.

Rejected records must not enter model evaluation.

Real EHR evaluation with MIMIC-IV-Note or MIMIC-IV-BHC remains pending
credentialed access and governance approval.

## Human Evaluation

Human evaluation supports:

- Rubric form.
- Factual correctness score.
- Completeness score.
- Conciseness/readability score.
- Citation usefulness score.
- Doctor edit diff.
- Approve/reject reason analytics.
- Reviewer signature.
- Final approved summary lock.
- Exportable human evaluation dataset.

Human review data is intended to become a training signal for prompt tuning,
retrieval tuning, reranking, and future safety evaluation.

The Week 5 blinded protocol and score package are documented in
`docs/evaluation/HUMAN_EVALUATION_PROTOCOL.md`. Scores remain blank until real
reviewers complete the protocol.

## Background Jobs

Use local mode when you want the simplest stable development loop:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_backend --job-backend in_process
```

Use Redis/RQ mode when testing deployment-like background generation:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_redis_dev --start
.\.venv\Scripts\python.exe -m scripts.run_backend --job-backend rq
.\.venv\Scripts\python.exe -m scripts.run_rq_worker
```

The `/admin/jobs` page shows:

- Queue backend.
- Redis reachability.
- Worker count.
- Cache status.
- Model readiness.
- Warmup jobs.
- Job progress.
- Cancel actions.

If a demo is interrupted, clean stale Redis entries:

```powershell
.\.venv\Scripts\python.exe -m scripts.cleanup_rq_state
```

## Tests

Useful checks:

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
.\.venv\Scripts\python.exe -m py_compile backend/app/config.py backend/app/services/background_jobs.py scripts/run_backend.py scripts/run_redis_dev.py scripts/run_rq_worker.py scripts/cleanup_rq_state.py scripts/smoke_rq_job.py
.\.venv\Scripts\python.exe -m pytest backend/tests/test_background_jobs.py -q
```

Frontend build:

```powershell
Set-Location "D:\MyNewDesktop\clin-summ\frontend"
npm run build
```

Recorded Week 4 delivery verification:

```text
Full backend suite: 165 passed, 0 failed
Deployment-focused suite: 19 passed
Docker build: pass
Docker Compose staging: pass
/health: HTTP 200
/ready: HTTP 200
Runtime image: approximately 122 MB
Runtime image excludes Torch, Transformers, sentence-transformers, BERTScore,
datasets, evaluate, MLflow, CUDA, and NVIDIA packages
Flow 2.1 benchmark: 5 providers x 50 records, 250/250 completed
Flow 2.1 BERTScore: computed for all five providers
Admin Flow 2.1 artifact selection: verified
Frontend build: pass
```

These are recorded delivery results. New Week 5 commands and screenshots must
be captured separately in `docs/demo/DEMO_EVIDENCE_PACKAGE.md`; do not silently
replace historical evidence with an unrecorded rerun.

Current Week 5 automated evidence captured on 2026-06-22:

```text
Full backend suite: 172 passed
Lightweight backend verification: 37 passed
Frontend production build: pass
Docker build: pass
Docker Compose app/database health: pass
Redis/RQ worker readiness: pass
/health: HTTP 200
/ready: HTTP 200
Portable Flow 2.1: 5 providers, 250 outputs, BERTScore 5/5
```

## Troubleshooting

### Backend starts, but Qwen/Llama readiness fails with URL error or WinError 10061

This usually means the provider is trying to call a local gateway or Ollama
endpoint that is not running.

For local Ollama direct mode:

```env
LOCAL_OLLAMA_ENABLED=true
LLM_GATEWAY_MODE=litellm
OLLAMA_MODELS=D:\ollama_models
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Check Ollama:

```powershell
ollama serve
ollama list
```

Expected models:

```text
qwen2.5:3b
llama3.2:3b
```

If Qwen is missing:

```powershell
ollama pull qwen2.5:3b
```

If you use a different local Qwen tag, keep the provider name as `qwen2.5` but
override the actual Ollama model:

```env
LLM_GATEWAY_QWEN2_5_MODEL=ollama/qwen2.5:7b
```

The app accepts `OLLAMA_BASE_URL`, `OLLAMA_API_BASE`, or `OLLAMA_HOST`; values
like `localhost:11434` and `http://127.0.0.1:11434/api` are normalized for
readiness checks.

### Redis/RQ job stays at queued_rq

Check worker is running:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_rq_worker
```

Clean stale queue entries:

```powershell
.\.venv\Scripts\python.exe -m scripts.cleanup_rq_state
```

Run smoke:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_rq_job --run-worker-burst
```

### I want the old stable behavior

Restart backend with:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_backend --job-backend in_process
```

### Hugging Face downloads go to C drive

Make sure `.env` has:

```env
HF_HOME=D:\hf_cache
HF_HUB_CACHE=D:\hf_cache\hub
HF_DATASETS_CACHE=D:\hf_cache\datasets
TRANSFORMERS_CACHE=D:\hf_cache\hub
```

Then restart backend and worker.

### Alembic says model_jobs already exists

The migration is now idempotent. Run:

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Do not drop the table unless you intentionally want to delete job history.

## Repository Layout

```text
backend/app/                       FastAPI app, routers, services, repositories, models
backend/app/services/              RAG, summarization, review, jobs, providers
backend/app/evaluation/            Evaluation and benchmark helpers
backend/alembic/versions/          Database migrations
backend/tests/                     Backend tests
frontend/src/                      React frontend
scripts/                           Benchmark, worker, Redis, and operational scripts
docs/                              Product, architecture, delivery, and research documents
outputs/evaluation/                Local evaluation outputs
```

## Safety Boundaries

- Do not implement autonomous diagnosis, treatment recommendation, prescription, discharge approval, or medical image diagnosis.
- AI-generated summaries are drafts until reviewed and approved by an authorized clinician.
- Important clinical claims must carry citation evidence or remain visibly flagged.
- Unsupported and conflicting evidence must remain visible for review.
- Sensitive clinical actions must be auditable.
- Real EHR writeback must not be enabled without governance, access control, audit, and validation.

## Clinical Safety Layer

The MVP now includes an explicit safety layer before any real EHR integration:

- **PHI-safe audit metadata:** audit log metadata is sanitized at write time, so raw notes, generated summaries, evidence excerpts, prompts, and free-text review comments are not stored in audit metadata.
- **No raw-note logging:** long text and clinical note fields are dropped or redacted from audit responses and exports.
- **Unsupported claim blocking:** approval is blocked for unsupported, unchecked, insufficient, or conflicting clinically actionable claims.
- **Wrong-patient citation prevention:** citation sources are validated against the summary patient before approval.
- **Encounter-scope enforcement:** encounter-specific sources must match the summary encounter when both sides are encounter-scoped.
- **Audit export:** `/api/v1/audit/export` produces a PHI-safe audit package for admin, auditor, IT admin, and AI safety reviewer roles.
- **Role/access hardening:** audit export is restricted to global audit roles; doctor access remains limited to permitted review workflows.

Operational docs:

Primary submission package:

- [Week 5 final delivery report](docs/delivery%205/WEEK5_FINAL_DELIVERY.md)
- [Medical record summarization solution proposal](docs/proposal/MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md)

Supporting/reference documents:

- [Local Docker Compose demo checklist](docs/demo/LOCAL_DOCKER_COMPOSE_DEMO_CHECKLIST.md)
- [Demo evidence package](docs/demo/DEMO_EVIDENCE_PACKAGE.md)
- [Final demo and presentation runbook](docs/demo/FINAL_DEMO_AND_PRESENTATION_RUNBOOK.md)
- [Week 5 repository audit](docs/demo/WEEK5_REPOSITORY_AUDIT.md)
- [Human evaluation protocol](docs/evaluation/HUMAN_EVALUATION_PROTOCOL.md)
- [Retrieval gate case study](docs/evaluation/RETRIEVAL_GATE_CASE_STUDY.md)
- [Vinmec medical record summarization research proposal](docs/research/VINMEC_MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md)
- [Vinmec medical record summarization research roadmap](docs/research/VINMEC_MEDICAL_RECORD_SUMMARIZATION_RESEARCH_ROADMAP.md)
- [Vinmec pilot proposal](docs/research/VINMEC_PILOT_PROPOSAL.md)
- [Final research conclusion](docs/research/FINAL_RESEARCH_CONCLUSION.md)
- [Deployment readiness audit](docs/DEPLOYMENT_READINESS_AUDIT.md)
- [QA checklist](docs/QA_CHECKLIST.md)
- [Guardrails](docs/GUARDRAILS.md)
- [Optional future Railway deployment](docs/DEPLOYMENT_RAILWAY.md)
- [Evaluation snapshot](docs/EVALUATION_SNAPSHOT.md)

## Recommended Week 5 Work

1. Run one final dry-run using the presentation runbook.
2. Capture the remaining doctor/admin UI screenshots.
3. Record the end-to-end demo and verify reviewer access to the evidence package.
4. Invite qualified reviewers to complete the blinded human-evaluation sheet.
5. Avoid major new features before the final presentation.
6. Submit the Week 5 delivery report together with the professional solution
   proposal in `docs/proposal`; treat public cloud deployment,
   additional datasets, reranking, medical NLI, and long-term monitoring as
   optional future work.
