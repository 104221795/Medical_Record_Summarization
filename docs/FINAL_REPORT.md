# Final Report: Medical Record Summarization MVP

## 1. Project Overview

This project is a production-style Medical Record Summarization MVP. It ingests
FHIR-like clinical records, generates citation-grounded draft summaries, exposes
a doctor review workflow, and provides monitoring and evaluation readiness
views.

The system is a prototype for internship demonstration and research evaluation.
It is not a certified medical product.

## 2. Problem Statement

Clinical records are fragmented across notes, encounters, medications,
observations, reports, and other EHR/HIS structures. Clinicians need concise
summaries, but uncontrolled AI summarization can hallucinate facts or hide
uncertainty. The MVP addresses this by grounding draft summaries in source
evidence and keeping unsupported claims visible for doctor review.

## 3. Production-style MVP Scope

Implemented scope:

- FastAPI backend.
- SQLAlchemy persistence and Alembic migrations.
- FHIR-like ingestion.
- Patient, encounter, document, summary, claim, citation, review, audit, metric,
  model run, and human evaluation records.
- Deterministic, Gemini, BART, and Pegasus provider support.
- Claim-level citation mapping.
- Safety checks.
- Doctor UI.
- HITL edit, approve, reject, and review history.
- Audit log APIs.
- Admin metrics dashboard.
- Evaluation & Demo Control Center.

Excluded safety-sensitive scope:

- Diagnosis recommendation.
- Treatment recommendation.
- Prescription.
- Autonomous discharge approval.
- Medical image diagnosis.

## 4. System Architecture

The MVP has four main layers:

1. Backend API layer: FastAPI routers under `backend/app/routers`.
2. Persistence layer: SQLAlchemy models, repositories, and Alembic migrations.
3. Summarization and safety layer: provider adapters, deterministic workflow,
   citation service, safety service, and review service.
4. UI layer: static Doctor UI, Admin Dashboard, and Evaluation Control Center.

Provider outputs flow into one persisted workflow:

```text
provider output
-> sections
-> claims
-> citations
-> safety metrics
-> draft summary
-> doctor review
-> audit/model_run tracking
```

## 5. Dataset Strategy

The repository uses mock/de-identified data by default.

Current dataset assets:

- `data/evaluation/sample_ehr_notes.jsonl`: mock evaluation fixture.
- `data/demo/final_demo_cases.json`: three final demo cases.
- Dataset loader support under `src/data`.

Prepared real EHR benchmark path:

```text
data/processed/ehr_benchmark/test.jsonl
```

Real EHR benchmark data is not available yet. The project does not claim real
EHR benchmark performance from mock data.

## 6. Model Providers

Supported providers:

- `deterministic`: safe local default for tests and demos.
- `bart`: Hugging Face baseline provider, disabled for real execution unless
  explicitly enabled.
- `pegasus`: Hugging Face baseline provider, disabled for real execution unless
  explicitly enabled.
- `gemini`: governed external provider, disabled unless all required governance
  environment flags and API key are set.

All providers must produce draft summaries and pass through citation and safety
processing before review.

## 7. Citation Pipeline

The MVP stores generated claims as atomic `summary_claims`. Supported claims
must link to `claim_citations`, which can point to clinical documents, document
chunks, or structured records such as conditions, observations, medications, or
diagnostic reports.

Citation source APIs expose highlighted evidence spans and metadata without
requiring the UI to trust provider output blindly.

## 8. Hallucination Mitigation

Implemented controls:

- Draft-only AI output.
- Claim-level support status.
- Citation requirement for important clinical claims.
- Unsupported, insufficient-evidence, unchecked, and conflicting statuses.
- Needs Clinician Review section.
- Safety metrics: citation coverage, unsupported claim count, conflict count.
- Approval blocking for critical unsupported claims.
- Audit logs for sensitive actions.

## 9. Doctor Review Workflow

The HITL workflow supports:

- Start review.
- Edit draft summary.
- Approve summary.
- Reject summary with reason/comment.
- View review history.
- Preserve status transitions and audit events.

AI-generated summaries are never auto-approved.

## 10. Evaluation Design

Evaluation has three layers:

Layer A - Functional validation:

- Runs now with mock/de-identified demo data.
- Validates system behavior and workflow integration.

Layer B - Real EHR benchmark:

- Prepared but pending credentialed data.
- Expected file: `data/processed/ehr_benchmark/test.jsonl`.
- No fake benchmark metrics are generated.

Layer C - Human evaluation:

- Can run now on generated demo summaries.
- Stores 1-5 scores and reviewer comments.
- Suitable for demo usability/safety review, not real clinical validation unless
  conducted with appropriate data and governance.

## 11. Functional Validation Results

Final local validation was run on May 29, 2026.

Backend regression:

```text
101 passed
```

Functional validation endpoint:

```text
FUNCTIONAL_STATUS 200 passed
demo_data_seed=passed
patient_list=passed
patient_detail=passed
document_endpoint=passed
summary_generation=passed
summary_claims=passed
citation_or_unsupported=passed
citation_source=passed
hitl_review=passed
audit_logs=passed
metrics=passed
```

Static UI smoke:

```text
/doctor-demo 200
/admin/dashboard 200
/evaluation-demo 200
/doctor-assets/app.js 200
/admin-assets/app.js 200
/evaluation-assets/app.js 200
```

Alembic migration check:

```text
b888cb77eb72 -> c6b0b16f9b78 -> d1b21e8a9c04
```

Final MVP readiness:

```text
Ready for local demo and internship submission, with real EHR benchmark pending.
```

## 12. Human Evaluation Results

The system supports human evaluation storage and aggregation through:

- `POST /api/v1/evaluation/human`
- `GET /api/v1/evaluation/human/summary`
- `GET /api/v1/evaluation/human/by-summary/{summary_id}`

No final human evaluation results are claimed in this report unless evaluator
scores are submitted during the demo.

## 13. Real EHR Benchmark Pending Status

Current benchmark status:

```text
pending_dataset
```

Reason:

```text
Real EHR benchmark requires credentialed MIMIC-IV-Ext-BHC or MIMIC-IV-Note
processed JSONL. No benchmark result is available yet.
```

The project explicitly separates functional validation from real EHR benchmark
evaluation.

## 14. Limitations

- No production SSO/OAuth.
- No production EHR writeback.
- No real EHR benchmark dataset or results yet.
- BART/Pegasus real model execution requires explicit local enablement and
  model availability.
- Gemini requires explicit external-provider governance flags.
- Safety checks are MVP-level and not certified for clinical deployment.
- The UI is static and optimized for demo clarity, not production UX.

## 15. Future Work

- Add credentialed MIMIC-IV-Note or MIMIC-IV-Ext-BHC benchmark pipeline output.
- Expand retrieval and citation evaluation.
- Add production authentication and RBAC.
- Add deployment-grade secrets management.
- Add stronger semantic entailment and contradiction detection.
- Add larger clinician evaluation study.
- Improve provider-specific structured claim extraction.
