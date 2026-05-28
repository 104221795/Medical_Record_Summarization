# Medical Record Summarization MVP

This repository contains a FastAPI-based Medical Record Summarization MVP with
database persistence, FHIR-like ingestion, deterministic draft summary
generation, citation evidence, clinician review workflow, and an admin quality
dashboard.

The implementation is a local/development prototype. It is not a production
HIS/EMR integration and must use de-identified or mock data by default.

## Current Implementation Status

Implemented through provider unification after Phase 7C:

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

## Repository Layout

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
src/data/                  Phase 7A dataset loading and normalization utilities
src/models/                Phase 7B deterministic, BART, and Pegasus baseline providers
scripts/                   Baseline/evaluation command-line utilities
data/evaluation/           Committed mock/de-identified evaluation fixture and docs
docs/                      MVP source-of-truth docs and QA templates
deploy/k8s/                Kubernetes deployment manifests
```

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
python -m pip install -r requirements-mlops.txt -r requirements-guardrails-onnx.txt
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

- One doctor user
- One patient
- One encounter
- Clinical documents and chunks
- One draft summary with claims and citations
- Audit events

### PostgreSQL

Use PostgreSQL when you want to test the production-style database backend:

```powershell
$env:RAG_DATABASE_URL = "postgresql+psycopg://<user>:<password>@localhost:5432/clin_summ"

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

Backend URLs:

- OpenAPI: `http://127.0.0.1:8080/docs`
- Health check: `http://127.0.0.1:8080/healthz`
- Doctor UI: `http://127.0.0.1:8080/doctor-demo`
- Admin dashboard: `http://127.0.0.1:8080/admin/dashboard`
- Evaluation & Demo Control Center: `http://127.0.0.1:8080/evaluation-demo`
- Citation demo: `http://127.0.0.1:8080/citation-demo`

If the app reports that the schema is not initialized, run:

```powershell
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

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
5. Confirm Layer B says `pending_dataset` until
   `data/processed/ehr_benchmark/test.jsonl` exists.
6. Submit human evaluation scores for a generated summary ID if you want demo
   usability feedback.

Layer A functional validation uses mock/de-identified data only. Layer B real
EHR benchmark status remains pending until credentialed MIMIC-IV-Note or
MIMIC-IV-Ext-BHC data is processed locally. Mock data is never used to claim
real benchmark performance.

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
- `pegasus`: Hugging Face Pegasus baseline provider

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

### BART and Pegasus in the persisted workflow

BART and Pegasus are available as persisted baseline providers, but real model
execution is disabled by default to avoid surprise Hugging Face downloads during
tests and local demos.

Enable real BART/Pegasus execution only when you intentionally want local model
loading:

```powershell
$env:RUN_REAL_BASELINES = "1"
$env:BART_MODEL_NAME = "facebook/bart-large-cnn"
$env:PEGASUS_MODEL_NAME = "google/pegasus-xsum"
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
.\.venv\Scripts\python.exe -m pytest backend/tests -q
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

Run Phase 7C Gemini persisted workflow tests without any external API call:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_gemini_persisted_summary.py -q
```

Optional static UI JavaScript syntax checks:

```powershell
node --check backend/ui/doctor/app.js
node --check backend/ui/admin/app.js
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
