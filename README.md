# Medical Record Summarization MVP

This repository contains a final internship-demo Medical Record Summarization
MVP with database persistence, FHIR-like ingestion, provider-selectable draft
summary generation, citation evidence, clinician review workflow, auditability,
monitoring, and a multi-layer evaluation strategy.

The implementation is a local/development prototype. It is not a production
HIS/EMR integration and must use de-identified or mock data by default.

## Project Snapshot

**Medical Record Summarization** is a role-based clinical NLP platform prototype
for generating citation-grounded draft summaries from de-identified/mock patient
records. The system separates AI draft generation from doctor review, keeps
clinical evidence visible, records audit events, and provides admin-facing model
evaluation and dataset governance dashboards.

Proxy evaluation only. These results do not demonstrate clinical safety,
clinical effectiveness, or real-world healthcare performance. Real EHR
evaluation requires credentialed datasets such as MIMIC-IV-Note or MIMIC-IV-BHC
under approved governance processes.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, JSX, Vite, React Router, modular component/layout structure |
| Backend API | FastAPI, Pydantic, SQLAlchemy, Alembic |
| Persistence | PostgreSQL via `DATABASE_URL`/`RAG_DATABASE_URL`, SQLite fallback for quick local checks |
| Clinical data model | FHIR-like ingestion models, SQLAlchemy entities for patients, encounters, documents, chunks, summaries, reviews, audit logs |
| Retrieval | Configurable embedding backend, default `sentence-transformers/all-MiniLM-L6-v2` |
| Summarization providers | Deterministic baseline, Gemini governed provider, BART, Pegasus PubMed, Pegasus CNN/DailyMail, optional Pegasus XSum |
| Model execution | Hugging Face `AutoTokenizer` + `AutoModelForSeq2SeqLM` + `model.generate()`; no summarization pipeline for BART/Pegasus |
| Evaluation | ROUGE metrics, per-record predictions, model comparison CSV, evaluation reports, dataset governance workflow |
| Local model/cache | Hugging Face cache on `D:\hf_cache` |
| Dev/runtime | PowerShell on Windows, Docker PostgreSQL, Python virtualenv |

## Architecture

```mermaid
flowchart LR
    User[Doctor / Admin User] --> FE[React Role-Based Frontend]
    FE --> Auth[Demo Auth + Header RBAC]
    FE --> API[FastAPI Backend]

    API --> Patients[Patient / Encounter / Document APIs]
    API --> Summary[Summary Generation Service]
    API --> Review[Human Review Service]
    API --> Audit[Audit Service]
    API --> Eval[Evaluation Service]
    API --> Gateway[Summary Provider Gateway]

    Patients --> DB[(PostgreSQL / SQLite)]
    Summary --> Retrieval[Retrieval + Evidence Context]
    Retrieval --> Embeddings[Sentence-Transformers Embeddings]
    Summary --> Gateway
    Gateway --> Deterministic[Deterministic]
    Gateway --> Gemini[Gemini Optional]
    Gateway --> BART[BART]
    Gateway --> Pegasus[Pegasus PubMed / CNN-DM / XSum]

    Review --> DB
    Audit --> DB
    Eval --> Outputs[outputs/evaluation + D:/clin_summ_outputs]
    Eval --> Reports[Reports / CSV / JSONL]
```

## Highlight Features

- **Doctor workspace:** patient list, patient detail, clinical timeline, document viewer, summary workspace, citation panel, claim validation, unsupported-claim panel, review actions, audit history.
- **Admin workspace:** operational dashboard, model evaluation dashboard, benchmark results page, dataset governance explanation, audit logs, settings.
- **Provider selection:** frontend reads provider metadata from `GET /api/v1/providers` and can send deterministic, Gemini, BART, Pegasus PubMed, Pegasus CNN/DailyMail, or optional Pegasus XSum.
- **Review lifecycle:** generated draft -> start review -> edit/save -> approve or reject -> audit log.
- **Citation and safety posture:** important claims stay linked to evidence or flagged as unsupported/conflicting/insufficient.
- **Dataset governance:** separates Synthea/SyntheticMass ingestion validation, MultiClinSum proxy benchmark, future MTS-Dialog/MEDIQA-Sum cross-dataset checks, and future credentialed MIMIC evaluation.
- **Evaluation visibility:** model comparison table, ROUGE charts, records-evaluated charts, failure-pattern charts, prediction-file availability, proxy warning, Pegasus domain-fit explanation, benchmark artifact paths.
- **PostgreSQL-ready persistence:** users, summaries, reviews, audit logs, patients, documents, and evaluation metadata can persist through SQLAlchemy/Alembic.

## Current Frontend Routes

| Area | Route | Purpose |
| --- | --- | --- |
| Public | `/` | Home page |
| Public | `/about` | Mission, architecture, governance explanation |
| Public | `/login` | Demo role-aware login |
| Public | `/forgot-password` | Demo reset flow |
| Doctor | `/doctor` or `/doctor/dashboard` | Doctor dashboard |
| Doctor | `/doctor/patients` | Patient list |
| Doctor | `/doctor/patients/:patientId` | Patient detail and summary workspace |
| Doctor | `/doctor/review` | Summary review workspace |
| Doctor | `/doctor/audit` | Doctor audit history |
| Admin | `/admin` or `/admin/dashboard` | Admin dashboard |
| Admin | `/admin/evaluation` | Operational evaluation dashboard |
| Admin | `/admin/evaluation/benchmark` | Benchmark artifacts and detailed model results |
| Admin | `/admin/datasets` | Dataset governance |
| Admin | `/admin/audit` | Audit logs |
| Admin | `/admin/settings` | Settings |

## Key Backend APIs

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/auth/login` | Create demo doctor/admin session |
| `POST /api/v1/auth/logout` | Clear demo session on client |
| `GET /api/v1/providers` | List summary providers, model names, domain fit, and readiness status |
| `GET /api/v1/patients` | List persisted de-identified/mock patients |
| `GET /api/v1/patients/{patient_id}` | Patient detail |
| `POST /api/v1/patients/{patient_id}/summaries/generate` | Generate draft summary with selected provider |
| `POST /api/v1/summaries/{summary_id}/review/start` | Start doctor review |
| `PATCH /api/v1/summaries/{summary_id}/edit` | Save edited draft |
| `POST /api/v1/summaries/{summary_id}/approve` | Approve reviewed summary |
| `POST /api/v1/summaries/{summary_id}/reject` | Reject reviewed summary |
| `GET /api/v1/audit/logs` | View audit history |
| `GET /api/v1/evaluation/benchmark/results` | Discover benchmark folders, merge model comparison CSV with prediction JSONL metrics, and return benchmark artifacts |

## Evaluation Outputs

The controlled summarization benchmark writes local artifacts such as:

```text
D:\clin_summ_outputs\medium_benchmark_bart_pegasus\
  evaluation_run_manifest.json
  model_comparison.csv
  per_record_metrics.csv
  deterministic_predictions.jsonl
  bart_predictions.jsonl
  pegasus_predictions.jsonl
  pegasus_pubmed_predictions.jsonl
  pegasus_cnn_dailymail_predictions.jsonl
  all_predictions.jsonl
  failure_analysis.md
  EVALUATION_REPORT.md
```

Admin Evaluation and Benchmark Results pages read these outputs through
`GET /api/v1/evaluation/benchmark/results`. The backend discovers these folders,
prefers the newest valid run with a 200-record Pegasus PubMed prediction file,
and merges prediction JSONL metrics into the dashboard response when a model is
missing from `model_comparison.csv`.

Current local benchmark folders inspected by the dashboard:

```text
D:\clin_summ_outputs\medium_benchmark
D:\clin_summ_outputs\medium_benchmark_bart_pegasus
D:\clin_summ_outputs\performance_benchmark
```

Latest valid local medium benchmark snapshot, updated June 4, 2026:

| Provider | Checkpoint | Records | ROUGE-1 | ROUGE-2 | ROUGE-L | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| deterministic | `deterministic_sentence_baseline` | 50/50 | 0.3138 | 0.1504 | 0.2407 | Fast extractive baseline |
| BART | `facebook/bart-large-cnn` | 200/200 | 0.3379 | 0.1615 | 0.2533 | Best ROUGE-L in current proxy run |
| Pegasus XSum | `google/pegasus-xsum` | 200/200 | 0.1804 | 0.0512 | 0.1340 | Accepted with static positional embedding warning |
| Pegasus PubMed | `google/pegasus-pubmed` | 200/200 | 0.3301 | 0.1099 | 0.2108 | Loaded from `pegasus_pubmed_predictions.jsonl` |
| Pegasus CNN/DailyMail | `google/pegasus-cnn_dailymail` | 104/104 | 0.2810 | 0.1499 | 0.2303 | Partial auxiliary comparison file |

These are proxy/open benchmark numbers only. They are not evidence of clinical
safety or real EHR performance.

## Quick Start

Use one dependency file for the whole prototype:

```powershell
cd D:\MyNewDesktop\clin-summ
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Then initialize the local database and start the API with SQLite:

```powershell
$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
python -m uvicorn backend.app.main:app --reload --port 8080
```

For PostgreSQL instead of SQLite, use `RAG_DATABASE_URL=postgresql+psycopg://...` and follow [docs/POSTGRES_SETUP.md](docs/POSTGRES_SETUP.md).

Recommended PostgreSQL local setup uses host port `5433` to avoid collisions
with native Windows PostgreSQL services on `5432`:

```powershell
docker run --name clin-summ-postgres `
  -e POSTGRES_USER=clin_summ `
  -e POSTGRES_PASSWORD=clin_summ_dev `
  -e POSTGRES_DB=clin_summ `
  -p 5433:5432 `
  -v clin_summ_pgdata:/var/lib/postgresql/data `
  -d postgres:16

$env:DATABASE_URL = "postgresql+psycopg://clin_summ:clin_summ_dev@127.0.0.1:5433/clin_summ"
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
python -m uvicorn backend.app.main:app --reload --port 8080
```

Run the React frontend:

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to the FastAPI backend on port `8080`.
Keep both terminals open while using the React app:

```text
Backend:  http://127.0.0.1:8080
Frontend: http://127.0.0.1:5173
```

Build the React frontend:

```powershell
cd frontend
npm run build
```

Main local URLs:

| Surface | URL |
| --- | --- |
| API docs | `http://127.0.0.1:8080/docs` |
| React frontend | `http://127.0.0.1:5173` when `npm run dev` is running |
| React Benchmark Results | `http://127.0.0.1:5173/admin/evaluation/benchmark` |
| Unified Demo Console | `http://127.0.0.1:8080/demo-console` |
| Doctor UI | `http://127.0.0.1:8080/doctor-demo` |
| Admin dashboard | `http://127.0.0.1:8080/admin/dashboard` |
| Static Evaluation center | `http://127.0.0.1:8080/evaluation-demo` |
| Citation demo | `http://127.0.0.1:8080/citation-demo` |

## Repository Guide

| Area | Path | Purpose |
| --- | --- | --- |
| Backend app | `backend/app/` | FastAPI routes, services, repositories, models, database setup |
| Backend tests | `backend/tests/` | Regression, workflow, importer, baseline, and safety tests |
| Demo UIs | `backend/ui/` | Doctor, admin, unified, evaluation, and citation demo pages |
| Evaluation importers | `backend/app/evaluation/` | Dataset import and summarization baseline runners |
| Research utilities | `src/` | Dataset loading and baseline model adapters |
| Data | `data/` | Mock/demo fixtures, local external dataset placement, processed outputs |
| Docs | `docs/` | Mentor delivery, product specs, safety docs, evaluation plans |
| Deploy | `deploy/k8s/` | Prototype Kubernetes manifests |
| Requirements | `requirements.txt` | Single dependency entrypoint for local/dev/test/Docker setup |

For docs navigation, start with `docs/README.md`.

## Current Implementation Status

Implemented through the final demo/submission package:

| Phase | Status | Scope |
| --- | --- | --- |
| Phase 0 | Done | Repository stabilization, README cleanup, AGENTS.md, setup docs |
| Phase 1 | Done | SQLAlchemy models, Alembic migrations, persistence foundation, seed data |
| Phase 2 | Done | DB-backed Patient, Encounter, Document, Ingestion, and Audit APIs |
| Phase 3 | Done | Deterministic draft summaries, sections, claims, citations, safety flags |
| Phase 4 | Done | Doctor Golden Path UI |
| Phase 5 | Done | Human-in-the-loop edit, approve, reject, review history, versioning |
| Phase 6 | Done | Audit visibility, metrics APIs, admin quality dashboard, evaluation template |
| Phase 7A | Done | Real/de-identified EHR dataset loader, normalization, and mock evaluation fixture |
| Phase 7B | Done | BART/Pegasus baseline provider adapters and baseline evaluation runner |
| Phase 7C | Done | Gemini provider integration into the persisted draft summary workflow |
| Provider unification | Done | Deterministic, Gemini, BART, and Pegasus selectable from the persisted summary endpoint |
| Phase 8 | Done | Evaluation & Demo Control Center, functional validation, pending benchmark status, human evaluation |

Not implemented yet:

- Production SSO/OAuth
- Production HIS/EMR writeback
- Advanced retrieval evaluation and wrong-patient retrieval tracking

## Safety Boundaries

The system must not implement or expose actions for:

- Diagnosis recommendation
- Treatment recommendation
- Prescription
- Autonomous discharge approval
- Medical image diagnosis

AI-generated summaries always start as `draft` and require explicit clinician
review before approval. Every important clinical claim must be citation-linked
or visibly flagged as unsupported, conflicting, unchecked, or insufficiently
evidenced. Sensitive actions create audit logs.

## Repository Layout Details

```text
backend/app/
  main.py                  FastAPI app factory and route registration
  routers/                 API routers
  services/                Business logic and workflow services
  repositories/            Database query/write layer
  models/                  SQLAlchemy ORM models
  db/                      DB session, base metadata, seed utilities
backend/alembic/           Alembic migration environment
backend/tests/             Backend regression and workflow tests
backend/ui/citation/       Citation evidence demo UI
backend/ui/doctor/         Doctor Golden Path UI
backend/ui/admin/          Phase 6 audit and quality dashboard
backend/ui/unified/        Unified role-based demo console served by FastAPI
src/data/                  Phase 7A dataset loading and normalization utilities
src/models/                Phase 7B deterministic, BART, and Pegasus baseline providers
scripts/                   Baseline/evaluation command-line utilities
data/evaluation/           Committed mock/de-identified evaluation fixture and docs
data/demo/                 Curated final demo cases, all mock/de-identified
docs/                      MVP source-of-truth docs and QA templates
deploy/k8s/                Kubernetes deployment manifests
```

Final submission documents:

- `docs/FINAL_DEMO_SCRIPT.md`
- `docs/FINAL_REPORT.md`
- `docs/SUBMISSION_CHECKLIST.md`
- `docs/Buildingphases/PHASE8_EVALUATION_DESIGN.md`

## Requirements

Validated locally with:

- Python `3.13.2`
- PowerShell on Windows
- SQLite for local development and tests
- PostgreSQL-compatible SQLAlchemy models and migrations

Optional:

- PostgreSQL for integration testing
- Node.js for static JavaScript syntax checks

Use the `.venv` environment. A redundant `venv` directory was removed because it
did not contain the backend test dependencies.

## Environment Setup

From the repository root:

```powershell
cd D:\MyNewDesktop\clin-summ

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Confirm that you are using the correct interpreter:

```powershell
python -c "import sys; print(sys.executable)"
```

Expected path:

```text
D:\MyNewDesktop\clin-summ\.venv\Scripts\python.exe
```

Check dependency consistency:

```powershell
python -m pip check
```

Expected result:

```text
No broken requirements found.
```

## Database Setup

### Local SQLite

Use SQLite for the fastest local end-to-end test:

```powershell
$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"

python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

The seed command is idempotent and creates de-identified sandbox data:

- Demo doctor/admin/auditor users
- Ten de-identified MIMIC-III-demo-inspired patients
- Ten encounters across medicine, ICU, neurology, nephrology, cardiac surgery,
  orthopedics, vascular surgery, and telemetry
- Clinical documents and chunks with source spans
- Structured conditions, medications, observations, and diagnostic reports
- Seeded draft summaries for navigation plus source evidence for fresh summary generation
- Audit events

### PostgreSQL

Use PostgreSQL when you want to test the production-style database backend:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://clin_summ:clin_summ_dev@127.0.0.1:5433/clin_summ"

python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

Do not commit real credentials. Prefer local throwaway databases for
development.

## Run The Backend

```powershell
.\.venv\Scripts\Activate.ps1
$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"

python -m uvicorn backend.app.main:app --reload --port 8080
```

If you changed backend Python code or benchmark discovery logic, restart the
backend process and hard-refresh the browser (`Ctrl + F5`). A running Uvicorn
process can otherwise keep serving the old response shape.

Backend URLs:

- OpenAPI: `http://127.0.0.1:8080/docs`
- Health check: `http://127.0.0.1:8080/healthz`
- Unified Demo Console: `http://127.0.0.1:8080/demo-console`
- Doctor UI: `http://127.0.0.1:8080/doctor-demo`
- Admin dashboard: `http://127.0.0.1:8080/admin/dashboard`
- Evaluation & Demo Control Center: `http://127.0.0.1:8080/evaluation-demo`
- Citation demo: `http://127.0.0.1:8080/citation-demo`

React development URLs:

- App root: `http://127.0.0.1:5173`
- Admin benchmark dashboard: `http://127.0.0.1:5173/admin/evaluation/benchmark`

If the app reports that the schema is not initialized, run:

```powershell
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

## Run The Unified Demo Console

The main mentor-demo UI is:

```text
http://127.0.0.1:8080/demo-console
```

It provides a role-based mock login/logout screen and a medical-themed unified
workspace for:

- Demo setup and seeding
- Patient registry
- Encounters and clinical documents
- Doctor summary workspace
- HITL review actions
- Citation explorer with highlighted evidence
- Admin metrics
- Audit logs
- Evaluation status
- FHIR-like ingestion

Default demo roles:

- `doctor`: patient workflow, summary generation, citations, and HITL review
- `clinical_admin`: metrics, audit, evaluation, and integration overview
- `auditor`: read-only audit/evaluation flow
- `ai_safety_reviewer`: safety, citation, metrics, and evaluation review
- `it_admin`: monitoring/integration-focused view
- `nurse`: limited patient context view, no approval actions

The console sends these headers with API calls:

```text
X-Tenant-ID
X-User-ID
X-Role-Code
```

This is a mock local login only. Production would require SSO/OAuth, hardened
RBAC, session management, and audit review.

## Run The Doctor Flow Through Phase 5

1. Start the backend.
2. Open `http://127.0.0.1:8080/doctor-demo`.
3. Select mock role `doctor`.
4. If no patient is visible, click `Create demo data`.
5. Open a patient.
6. Review encounters and documents.
7. Generate `patient_snapshot`.
8. Inspect summary sections, claims, citation badges, evidence panel, and safety panel.
9. Start review.
10. Edit and save the summary if needed.
11. Approve or reject with a required reason/comment.
12. Open review history.

The UI labels AI output as draft and keeps safety/citation information visible
before approval.

## Run The Admin Flow Through Phase 6

1. Complete at least one doctor workflow action so metrics and audit logs exist.
2. Open `http://127.0.0.1:8080/admin/dashboard`.
3. Select mock role `clinical_admin`, `auditor`, `it_admin`, or
   `ai_safety_reviewer`.
4. Review:
   - Overview cards
   - Summary status breakdown
   - Usage metrics
   - Safety metrics
   - MVP readiness gates
   - Review metrics
   - Audit log table
5. Use audit filters for action, patient ID, user ID, and date range.
6. Click an audit row to inspect safe audit metadata.

The dashboard is read-only and does not intentionally expose raw clinical text
or patient names.

## Run The Phase 8 Evaluation Demo

1. Start the backend.
2. Open `http://127.0.0.1:8080/evaluation-demo`.
3. Review golden path, provider, citation/safety, HITL, and monitoring status.
4. Click `Run Functional Validation` to execute the mock/de-identified workflow check.
5. Review the model benchmark dashboard. It reads discovered benchmark folders,
   shows the selected output directory, charts ROUGE and records evaluated, and
   displays Pegasus PubMed when `pegasus_pubmed_predictions.jsonl` exists.
6. Confirm the real EHR note benchmark layer says `pending_dataset` until
   `data/processed/ehr_benchmark/test.jsonl` exists.
7. Submit human evaluation scores for a generated summary ID if you want demo
   usability feedback.

Layer A functional validation uses mock/de-identified data only. The real EHR
note benchmark layer remains pending until credentialed MIMIC-IV-Note or
MIMIC-IV-Ext-BHC data is processed locally. Mock data is never used to claim
real benchmark performance.

For the richer React dashboard, run the frontend and open:

```text
http://127.0.0.1:5173/admin/evaluation/benchmark
```

## Final Demo Cases

Three curated mock/de-identified cases are available at:

```text
data/demo/final_demo_cases.json
```

They cover:

- Normal supported-citation flow.
- Missing-information flow.
- Unsupported or weak/conflicting evidence flow.

Copy a case's `fhir_like_import` object into `POST /api/v1/ingestion/import`,
then run the Doctor UI golden path.

## Phase 7A Dataset Pipeline

The dataset layer normalizes real/de-identified EHR summarization datasets into
one internal schema:

```json
{
  "note_id": "note_001",
  "patient_id": "patient_001",
  "encounter_id": "enc_001",
  "source_note": "...",
  "reference_summary": "...",
  "dataset": "mock|mimic_iv_note|mimic_iv_ext_bhc",
  "split": "train|validation|test"
}
```

Implemented loaders:

- `load_jsonl_dataset()` for the committed mock JSONL fixture and legacy
  `inputs`/`target` JSONL rows.
- `load_mimic_iv_note_dataset()` for MIMIC-IV-Note-style discharge summaries.
- `load_bhc_dataset()` for MIMIC-IV-Ext-BHC-style hospital course datasets.
- `normalize_to_internal_schema()` for common source/target column names.
- `create_small_demo_subset()` for deterministic smoke-test/demo subsets.

Committed demo fixture:

```text
data/evaluation/sample_ehr_notes.jsonl
```

Credentialed MIMIC data must stay local and must not be committed. After
obtaining access through the official PhysioNet process, place files in ignored
local folders such as:

```text
data/mimic_iv_note/discharge.csv.gz
data/mimic_iv_ext_bhc/mimic_iv_ext_bhc.csv
```

These paths are ignored by `.gitignore`.

How the dataset feeds final evaluation:

1. Load and normalize rows with `src.data.dataset_loader`.
2. Use `source_note` as provider input for deterministic, BART, Pegasus, or
   Gemini evaluation.
3. Use `reference_summary` for automated metrics and human review.
4. Preserve `note_id`, `patient_id`, and `encounter_id` as provenance keys.
5. Run claim extraction, citation verification, safety scoring, and model-run
   tracking for every provider output.

## Phase 7B BART/Pegasus Baselines

Baseline providers live under `src/models/`:

- `DeterministicSummarizer`
- `BartSummarizer`
- `PegasusSummarizer`

All providers return the same output shape:

```json
{
  "note_id": "...",
  "model_provider": "bart|pegasus|deterministic",
  "source_note": "...",
  "reference_summary": "...",
  "generated_summary": "...",
  "latency_ms": 1234
}
```

Run the baseline script with the deterministic provider, which requires no
model download:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_baseline_summarization `
  --provider deterministic `
  --dataset-path data/evaluation/sample_ehr_notes.jsonl `
  --output-dir results
```

This writes:

```text
results/deterministic_outputs.jsonl
results/model_comparison.csv
```

BART/Pegasus execution uses Hugging Face Transformers and is disabled by
default so CI/tests do not download models. To run real local baselines:

```powershell
python -m pip install -r requirements.txt
$env:RUN_REAL_BASELINES = "1"

.\.venv\Scripts\python.exe -m scripts.run_baseline_summarization `
  --provider all `
  --dataset-path data/evaluation/sample_ehr_notes.jsonl `
  --output-dir results `
  --allow-model-downloads
```

Default models:

- BART: `facebook/bart-large-cnn`
- Pegasus: `google/pegasus-xsum`

You may override them:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_baseline_summarization `
  --provider bart `
  --bart-model sshleifer/distilbart-cnn-12-6 `
  --allow-model-downloads
```

Automatic metrics currently include ROUGE-1, ROUGE-2, and ROUGE-L. BERTScore is
optional via `--include-bertscore` and is skipped if the optional package is not
installed.

Generated baseline files under `results/` are ignored by git.

## Evaluation Pipeline

The full layered evaluation pipeline is the recommended entrypoint for proxy
evaluation runs. It validates the processed JSONL input, runs dataset governance
and data-quality routing, checks chunking/retrieval sanity signals, runs the
selected providers, writes per-record predictions, writes model comparison
metrics, prepares a human-review CSV, and generates a mentor-readable Markdown
report.

All outputs include this warning:

```text
Proxy evaluation only. Do not claim real EHR benchmark or clinical performance from these outputs.
Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes.
```

Default output directory:

```text
D:\clin_summ_outputs\
```

For repository-local smoke runs, pass
`--output-dir outputs/evaluation/full_pipeline` explicitly.

The runner pins local cache/output locations to D drive and fails if Hugging
Face cache variables point to C drive:

```powershell
$env:HF_HOME = "D:\hf_cache"
$env:HF_HUB_CACHE = "D:\hf_cache\hub"
$env:HF_DATASETS_CACHE = "D:\hf_cache\datasets"
$env:TRANSFORMERS_CACHE = "D:\hf_cache\hub"
$env:CLIN_SUMM_DATA_DIR = "D:\clin_summ_data"
$env:CLIN_SUMM_MODEL_DIR = "D:\clin_summ_models"
$env:CLIN_SUMM_OUTPUT_DIR = "D:\clin_summ_outputs"
```

Expected files:

```text
evaluation_run_manifest.json
run_manifest.json
dataset_profile.json
quality_metrics.json
retrieval_metrics.json
model_manifest.json
model_comparison.csv
all_predictions.jsonl
deterministic_predictions.jsonl
bart_predictions.jsonl
pegasus_predictions.jsonl
human_review_template.csv
failure_analysis.md
EVALUATION_REPORT.md
run.log
data_governance/dataset_manifest.json
data_governance/benchmark_manifest.jsonl
data_governance/warning_manifest.jsonl
data_governance/rejected_manifest.jsonl
data_governance/chunking_manifest.json
```

Dry run without downloads:

```powershell
python -m scripts.run_full_evaluation_pipeline `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train_smoke.jsonl `
  --models deterministic,bart,pegasus `
  --limit 3 `
  --output-dir D:\clin_summ_outputs\full_pipeline `
  --dry-run
```

Deterministic smoke test:

```powershell
python -m scripts.run_full_evaluation_pipeline `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train_smoke.jsonl `
  --models deterministic `
  --limit 3 `
  --output-dir D:\clin_summ_outputs\full_pipeline
```

BART run, intentionally allowing Hugging Face model loading:

```powershell
python -m scripts.run_full_evaluation_pipeline `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train_smoke.jsonl `
  --models bart `
  --limit 3 `
  --output-dir D:\clin_summ_outputs\full_pipeline `
  --allow-model-downloads `
  --include-bertscore
```

Pegasus run, intentionally allowing Hugging Face model loading:

```powershell
python -m scripts.run_full_evaluation_pipeline `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train_smoke.jsonl `
  --models pegasus `
  --limit 3 `
  --output-dir D:\clin_summ_outputs\full_pipeline `
  --allow-model-downloads `
  --include-bertscore
```

Full proxy run:

```powershell
python -m scripts.run_full_evaluation_pipeline `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train_smoke.jsonl `
  --models deterministic,bart,pegasus `
  --limit 3 `
  --output-dir D:\clin_summ_outputs\full_pipeline
```

Gemini is optional and disabled unless explicitly enabled with governance
environment flags:

```powershell
$env:RUN_GEMINI_EVALUATION = "1"
$env:RAG_LLM_PROVIDER = "gemini"
$env:RAG_LLM_EXTERNAL_ENABLED = "true"
$env:RAG_LLM_ALLOW_PHI_EXTERNAL = "true"
$env:RAG_GEMINI_API_KEY = "<google-ai-studio-api-key>"

python -m scripts.run_full_evaluation_pipeline `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train_smoke.jsonl `
  --models deterministic,gemini `
  --limit 3 `
  --output-dir D:\clin_summ_outputs\full_pipeline `
  --allow-gemini
```

Read results in:

- `D:\clin_summ_outputs\full_pipeline\EVALUATION_REPORT.md`
- `D:\clin_summ_outputs\full_pipeline\model_comparison.csv`
- `D:\clin_summ_outputs\full_pipeline\all_predictions.jsonl`
- `D:\clin_summ_outputs\full_pipeline\failure_analysis.md`
- `D:\clin_summ_outputs\full_pipeline\data_governance\quality_report.md`
- `D:\clin_summ_outputs\full_pipeline\run.log`

BART/Pegasus real generation is blocked by default. Without
`--allow-model-downloads` or `RUN_REAL_BASELINES=1`, those providers are written
as skipped rows instead of downloading models unexpectedly.

## Unified Provider Proxy Evaluation

Use the unified provider evaluation runner when you want one comparison pass
across:

- `deterministic`
- `bart`
- `pegasus`
- `gemini`

This runner is for proxy evaluation only. It uses mock/de-identified demo rows
and writes explicit warnings into every output file. Do not report these
numbers as real EHR benchmark performance.

Safe default run:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_provider_evaluation `
  --providers all `
  --dataset-path data/evaluation/sample_ehr_notes.jsonl `
  --output-dir results/provider_evaluation
```

Expected behavior in the safe default:

- `deterministic` runs locally.
- `bart` is skipped unless real Hugging Face baselines are explicitly enabled.
- `pegasus` is skipped unless real Hugging Face baselines are explicitly enabled.
- `gemini` is skipped unless external Gemini evaluation is explicitly enabled.

Generated files:

```text
results/provider_evaluation/provider_outputs.jsonl
results/provider_evaluation/deterministic_outputs.jsonl
results/provider_evaluation/bart_outputs.jsonl
results/provider_evaluation/pegasus_outputs.jsonl
results/provider_evaluation/gemini_outputs.jsonl
results/provider_evaluation/provider_model_comparison.csv
results/provider_evaluation/EVALUATION_SUMMARY.md
```

Each JSONL row includes:

- `evaluation_type = proxy_deidentified_demo_evaluation`
- `proxy_evaluation = true`
- provider/model metadata
- source and reference text from the demo/de-identified dataset
- generated summary when a provider runs
- ROUGE-1, ROUGE-2, ROUGE-L for completed rows
- skipped/failed status and error details when a provider is unavailable

Enable real BART/Pegasus model loading only when you intentionally want local
Hugging Face execution:

```powershell
python -m pip install -r requirements.txt
$env:RUN_REAL_BASELINES = "1"

.\.venv\Scripts\python.exe -m scripts.run_provider_evaluation `
  --providers deterministic,bart,pegasus `
  --dataset-path data/evaluation/sample_ehr_notes.jsonl `
  --output-dir results/provider_evaluation `
  --allow-model-downloads
```

Enable Gemini proxy evaluation only for de-identified/governed data:

```powershell
$env:RUN_GEMINI_EVALUATION = "1"
$env:RAG_LLM_PROVIDER = "gemini"
$env:RAG_LLM_EXTERNAL_ENABLED = "true"
$env:RAG_LLM_ALLOW_PHI_EXTERNAL = "true"
$env:RAG_GEMINI_API_KEY = "<google-ai-studio-api-key>"

.\.venv\Scripts\python.exe -m scripts.run_provider_evaluation `
  --providers deterministic,gemini `
  --dataset-path data/evaluation/sample_ehr_notes.jsonl `
  --output-dir results/provider_evaluation `
  --allow-gemini
```

Strong safety warning: the unified runner is not a clinical validation study.
It is a final-demo comparison harness for de-identified/demo data. Real
MIMIC-IV-Note or MIMIC-IV-Ext-BHC evaluation remains pending until credentialed
data is processed locally and reviewed under the evaluation protocol.

## Persisted Summary Provider Selection

The main persisted workflow now supports provider selection behind the same
summary endpoint used by the Doctor UI:

```http
POST /api/v1/patients/{patient_id}/summaries/generate
```

Supported `model_provider` values:

- `deterministic`: default safe local workflow for development, tests, and demos
- `gemini`: governed external Gemini JSON provider
- `bart`: Hugging Face BART baseline provider
- `pegasus`: generic Hugging Face Pegasus baseline provider
- `pegasus_pubmed`: Pegasus PubMed checkpoint, preferred Pegasus option for medical/scientific proxy runs
- `pegasus_cnn_dailymail`: Pegasus CNN/DailyMail auxiliary comparison checkpoint
- `pegasus_xsum`: optional Pegasus XSum comparison checkpoint

All providers persist through the same internal path: draft summary, sections,
claims, citations, safety calculation, `model_runs`, audit logs, and the doctor
review workflow. Deterministic generation remains the safe default when no
provider is requested.

Example deterministic request:

```json
{
  "encounter_id": "00000000-0000-0000-0000-000000000000",
  "summary_type": "patient_snapshot",
  "language": "vi",
  "model_provider": "deterministic",
  "options": {
    "require_citations": true,
    "include_safety_check": true
  }
}
```

`provider` is still accepted as a backward-compatible alias for
`model_provider`.

### Gemini

Gemini is disabled by default. To enable Gemini for the main persisted workflow,
all of these environment variables must be set explicitly:


```powershell
$env:RAG_LLM_PROVIDER = "gemini"
$env:RAG_LLM_EXTERNAL_ENABLED = "true"
$env:RAG_LLM_ALLOW_PHI_EXTERNAL = "true"
$env:RAG_GEMINI_API_KEY = "<google-ai-studio-api-key>"
$env:RAG_GEMINI_MODEL = "gemini-2.5-flash-lite"
```

Strong safety warning: enable this only for de-identified data or data covered
by an approved governance, security, and data-processing agreement. The app does
not send clinical data to Gemini unless `RAG_LLM_PROVIDER=gemini`,
`RAG_LLM_EXTERNAL_ENABLED=true`, and
`RAG_LLM_ALLOW_PHI_EXTERNAL=true` are all present.

Example request:

```json
{
  "encounter_id": "00000000-0000-0000-0000-000000000000",
  "summary_type": "patient_snapshot",
  "language": "vi",
  "model_provider": "gemini",
  "options": {
    "require_citations": true,
    "include_safety_check": true
  }
}
```

Gemini output is required to be strict JSON and is validated before persistence.
Every supported claim must map back to a source ID from the current patient's
evidence pack. Claims without valid evidence are downgraded and shown for
clinician review. Generated summaries remain `draft`; the HITL review workflow
is still required for approval.

Provider troubleshooting:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_provider_setup
```

If Gemini does not run, check that the backend process sees
`RAG_LLM_PROVIDER=gemini`, `RAG_LLM_EXTERNAL_ENABLED=true`,
`RAG_LLM_ALLOW_PHI_EXTERNAL=true`, and a Gemini key. The backend accepts
`RAG_GEMINI_API_KEY`; it also accepts the legacy local variable
`GEMINI_API_KEY` as a fallback. Installing `google-generativeai` is not required
for this backend path because the app uses a small HTTPS JSON client.

If Gemini returns `invalid structured JSON`, the backend rejects the output
safely and creates no summary. The prompt schema restricts allowed section,
claim, support-status, and risk-level values; minor structural variants are
normalized into the internal schema, but non-JSON or unsafe outputs still fail.

### BART and Pegasus in the persisted workflow

BART and Pegasus are available as persisted baseline providers, but real model
execution is disabled by default to avoid surprise Hugging Face downloads during
tests and local demos.

Enable real BART/Pegasus execution only when you intentionally want local model
loading:

```powershell
python -m pip install -r requirements.txt
$env:RUN_REAL_BASELINES = "1"
$env:BART_MODEL_NAME = "facebook/bart-large-cnn"
$env:PEGASUS_MODEL_NAME = "google/pegasus-pubmed"
$env:PEGASUS_PUBMED_MODEL_NAME = "google/pegasus-pubmed"
$env:PEGASUS_CNN_DAILYMAIL_MODEL_NAME = "google/pegasus-cnn_dailymail"
$env:PEGASUS_XSUM_MODEL_NAME = "google/pegasus-xsum"
```

Then request the provider:

```json
{
  "summary_type": "patient_snapshot",
  "language": "vi",
  "model_provider": "bart",
  "options": {
    "require_citations": true,
    "include_safety_check": true
  }
}
```

```json
{
  "summary_type": "patient_snapshot",
  "language": "vi",
  "model_provider": "pegasus",
  "options": {
    "require_citations": true,
    "include_safety_check": true
  }
}
```

Preferred Pegasus PubMed request:

```json
{
  "summary_type": "patient_snapshot",
  "language": "vi",
  "model_provider": "pegasus_pubmed",
  "options": {
    "require_citations": true,
    "include_safety_check": true
  }
}
```

BART/Pegasus plain-text outputs are normalized into a `Generated Summary`
section, split into atomic claims, citation-matched against the current
patient's evidence pack, and flagged for clinician review when evidence is weak
or missing.

## Main API Groups

All APIs are mounted under `/api/v1`.

Patient and encounter:

- `GET /patients`
- `GET /patients/{patient_id}`
- `GET /patients/{patient_id}/encounters`
- `GET /encounters/{encounter_id}`

Documents:

- `GET /patients/{patient_id}/documents`
- `GET /documents/{document_id}`
- `GET /documents/{document_id}/chunks`

Ingestion:

- `POST /ingestion/import`

Summary generation and citation:

- `POST /patients/{patient_id}/summaries/generate`
- `GET /summaries/{summary_id}`
- `POST /summaries/{summary_id}/regenerate`
- `GET /claims/{claim_id}/citations`
- `GET /citations/{citation_id}/source`

Clinician review:

- `POST /summaries/{summary_id}/review/start`
- `PATCH /summaries/{summary_id}/edit`
- `POST /summaries/{summary_id}/approve`
- `POST /summaries/{summary_id}/reject`
- `GET /summaries/{summary_id}/reviews`

Audit and metrics:

- `GET /audit/logs`
- `GET /audit/logs/{audit_id}`
- `GET /metrics/summary-quality`
- `GET /metrics/usage`
- `GET /metrics/safety`
- `GET /metrics/review`

Evaluation and demo readiness:

- `GET /demo/readiness`
- `GET /evaluation/status`
- `GET /evaluation/functional/status`
- `POST /evaluation/functional/run`
- `GET /evaluation/benchmark/status`
- `POST /evaluation/human`
- `GET /evaluation/human/summary`
- `GET /evaluation/human/by-summary/{summary_id}`

Mock RBAC headers:

```text
X-Tenant-ID: sandbox
X-User-ID: doctor-demo
X-Role-Code: doctor
```

Admin dashboard roles:

- `clinical_admin`
- `auditor`
- `it_admin`
- `ai_safety_reviewer`

## Run Tests

Run the full backend regression suite:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -p no:cacheprovider -q
```

Final local validation result on May 29, 2026:

```text
105 passed
```

Run DB and workflow-focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  backend/tests/test_persistence.py `
  backend/tests/test_persistence_api.py `
  backend/tests/test_summary_generation.py `
  backend/tests/test_review_workflow.py `
  backend/tests/test_phase6_audit_metrics.py `
  -q
```

Run Phase 7A dataset tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_ehr_dataset_pipeline.py -q
```

Run Phase 7B baseline provider tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_baseline_providers.py -q
```

Run the unified provider proxy evaluation tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_provider_evaluation_runner.py -q
```

Run Phase 7C Gemini persisted workflow tests without any external API call:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_gemini_persisted_summary.py -q
```

Optional static UI JavaScript syntax checks:

```powershell
node --check backend/ui/doctor/app.js
node --check backend/ui/admin/app.js
node --check backend/ui/evaluation/app.js
```

Run Phase 8 evaluation readiness tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_phase8_evaluation.py -q
```

Run functional validation through the UI:

```text
http://127.0.0.1:8080/evaluation-demo
```

or through the API:

```http
POST /api/v1/evaluation/functional/run
```

## Troubleshooting

### I am in a venv but dependencies conflict

Use `.venv`, not `venv`.

```powershell
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip check
```

If the interpreter path does not point to `.venv`, close the terminal and
activate `.venv` again.

### `patients` table or other DB table errors

Run migrations and seed data:

```powershell
$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

### No patients appear in the Doctor UI

Either run the seed command above, or use the Doctor UI `Create demo data`
button in local development.

### Admin dashboard is empty

The dashboard does not fake data. Generate/review a summary in the Doctor UI
first, then reload `/admin/dashboard`.

### Benchmark dashboard does not show Pegasus PubMed

Pegasus PubMed is loaded from:

```text
D:\clin_summ_outputs\medium_benchmark_bart_pegasus\pegasus_pubmed_predictions.jsonl
```

The backend endpoint merges that prediction JSONL into the dashboard response:

```http
GET /api/v1/evaluation/benchmark/results
```

If the UI does not show Pegasus PubMed:

1. Restart the backend so it loads the latest `evaluation_service.py`.
2. Hard-refresh the browser with `Ctrl + F5`.
3. Make sure you are opening the intended UI:
   - React dashboard: `http://127.0.0.1:5173/admin/evaluation/benchmark`
   - Static evaluation demo: `http://127.0.0.1:8080/evaluation-demo`
4. Check that the endpoint response has `selected_output_dir` and a
   `pegasus_pubmed` model row.

PowerShell check:

```powershell
$headers = @{
  "X-Tenant-ID" = "sandbox"
  "X-User-ID" = "clinical-admin-demo"
  "X-Role-Code" = "clinical_admin"
}

$r = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/api/v1/evaluation/benchmark/results" `
  -Headers $headers

$r.selected_output_dir
$r.models | Where-Object { $_.model_provider -eq "pegasus_pubmed" } |
  Select-Object model_provider, model_name, completed_count, record_count, rouge1, rouge2, rougeL, stage_name
```

Expected current local row:

```text
model_provider: pegasus_pubmed
model_name: google/pegasus-pubmed
completed_count / record_count: 200 / 200
rougeL: 0.2108
stage_name: stage_pegasus_pegasus_pubmed_limit200
```

### Nurse role cannot load dashboard metrics

This is expected. Global metrics and audit visibility are limited to admin,
auditor, IT admin, and AI safety reviewer roles.

## Source-Of-Truth Docs

- `docs/1.MVP_SCOPE_MEDICAL_RECORD_SUMMARIZATIOn.md`
- `docs/2.PRD_MEDICAL_RECORD_SUMMARIZATION_VI.md`
- `docs/3.PROJECT_BRIEF_RECORD_SUMMARIZATION_VI.md`
- `docs/4.DB_SCHEMAS_MEDICAL_RECORD_SUMMARIZATION.md`
- `docs/5.SYSTEM_ARCHITECTURE.md`
- `docs/6.API_SPECIFICATIONS.md`
- `docs/7.FHIR_DATA_MAPPING.md`
- `docs/8.USER_FLOW.md`
- `docs/9.PROMPT_DESIGN.md`
- `docs/10.HALLUCIATION_MITIGATION.md`
- `docs/11.GOLDEN_PATH_UI.md`
- `docs/12.evaluationplan.md`
- `docs/EVALUATION_REPORT_TEMPLATE.md`
- `docs/PHASE6_AUDIT_METRICS_DASHBOARD_QA.md`
- `docs/PHASE7C_GEMINI_PROVIDER.md`

## Original Research Repository Context

This workspace began from the Stanford clinical text summarization research
codebase associated with:

> Adapted Large Language Models Can Outperform Medical Experts in Clinical Text
> Summarization, Nature Medicine, 2024.

The MVP backend and UI described above are an added medical-record
summarization prototype layer. The original research scripts and datasets under
`src/`, `api/`, and `data/` remain separate from the FastAPI MVP workflow.
