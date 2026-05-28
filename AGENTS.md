# Repository Guidance for Coding Agents

## Purpose

This repository contains an original clinical text summarization research project
and a Medical Record Summarization MVP prototype under `backend/`, `docs/`, and
`deploy/`.

The current implementation is a prototype. The Markdown specifications under
`docs/` describe the target MVP and are the source of truth for product,
clinical safety, API, FHIR, UI, and evaluation decisions.

## Current Stabilization Boundary

- Keep Phase 0 work limited to repository stabilization, documentation,
  dependency/setup correctness, and test reliability unless a later task
  explicitly expands the scope.
- Do not present currently implemented prototype endpoints as a complete
  production HIS/EMR integration.
- Preserve existing research code and prototype demos unless a requested change
  specifically requires touching them.

## Clinical Safety Boundaries

- Do not implement diagnosis recommendation, treatment recommendation,
  prescription, autonomous discharge approval, or medical image diagnosis.
- AI-generated summaries are drafts until approved by an authorized doctor.
- Every important clinical claim must carry citation evidence or be visibly
  flagged as unsupported.
- Conflicting or unsupported evidence must remain visible for clinician review.
- Sensitive clinical actions must ultimately be auditable.
- Use mock or de-identified data by default for local development, tests, and
  demos.
- Do not enable real EMR/FHIR writeback before approval, access control, audit,
  and evidence-validation requirements are implemented and verified.

## Key Locations

- `backend/app/`: FastAPI prototype application and services.
- `backend/tests/`: backend automated tests.
- `backend/ui/citation/`: citation demo UI.
- `docs/`: MVP source-of-truth documentation.
- `docs/Buildingphases/`: implemented/proposed technical increment notes.
- `deploy/k8s/`: deployment prototype manifests.

## Local Backend Validation

PowerShell commands for the complete currently routed backend surface:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-mlops.txt -r requirements-guardrails-onnx.txt
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
python -m pytest backend\tests -p no:cacheprovider -q
python -m uvicorn backend.app.main:app --reload --port 8080
```

The application documentation is available at `http://127.0.0.1:8080/docs`;
the citation demo is available at `http://127.0.0.1:8080/citation-demo`.
