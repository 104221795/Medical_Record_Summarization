# Final Demo Script

## 1. Opening

This project is a Medical Record Summarization MVP for clinicians. The goal is
to turn fragmented EHR/HIS-style patient records into a draft, citation-grounded
summary that a doctor can review, edit, approve, or reject.

Important safety framing:

- This is a prototype, not a certified medical product.
- It does not recommend diagnosis, treatment, prescriptions, discharge approval,
  or image diagnosis.
- AI output is always a draft until a doctor approves it.
- Important clinical claims must have citations or be flagged for review.

## 2. Problem

Clinicians often need to review notes, observations, medication records,
diagnostic reports, and encounter context spread across multiple systems. A
summarization assistant can reduce review burden, but only if it is grounded in
source evidence and keeps uncertainty visible.

## 3. Objective

The MVP demonstrates:

- FHIR-like ingestion into a persisted clinical domain model.
- Provider-selectable summary generation.
- Claim-level citation mapping.
- Safety flags for missing, unsupported, or conflicting information.
- Human-in-the-loop review and auditability.
- Monitoring and evaluation readiness.

## 4. Architecture Walkthrough

Show the high-level architecture:

- FastAPI backend under `backend/app`.
- SQLAlchemy models and Alembic migrations.
- FHIR-like ingestion endpoints.
- Summary providers: deterministic, BART, Pegasus, Gemini.
- Citation and safety services.
- Doctor UI, admin dashboard, and Evaluation & Demo Control Center.
- Dataset and baseline utilities under `src/` and `scripts/`.

Explain that all providers flow into the same persisted schema:

```text
provider output
-> summary sections
-> summary claims
-> claim citations
-> safety calculation
-> draft summary
-> doctor review
-> audit/model_run tracking
```

## 5. Doctor Golden Path

Open:

```text
http://127.0.0.1:8080/doctor-demo
```

Demo steps:

1. Select mock role `doctor`.
2. Click `Create demo data` if no patient is visible.
3. Open the patient record.
4. Show patient header, encounter list, and clinical documents.
5. Choose `patient_snapshot`.
6. Choose provider `deterministic` for the safest local demo.
7. Click `Generate`.
8. Point out draft status.
9. Show sections, claims, citation badges, and safety panel.

## 6. Citation Pipeline

Click a citation badge.

Show:

- Citation source type.
- Document metadata.
- Highlighted source span.
- Surrounding context.
- Same-patient evidence lookup.

Explain that supported claims require citations. Claims without evidence are
flagged as unsupported or insufficient evidence.

## 7. Safety Flags

Show the safety panel:

- Draft status.
- Citation coverage.
- Unsupported claim count.
- Conflict count.
- Unsupported or insufficient-evidence claims.

Use the curated cases in `data/demo/final_demo_cases.json`:

- Supported citations case.
- Missing information case.
- Weak/conflicting evidence case.

## 8. HITL Review

Show:

1. Start Review.
2. Edit summary.
3. Save Edit.
4. Approve a safe draft, or reject a draft with a reason.
5. Open Review History.

Explain:

- Approved summaries are locked from normal editing.
- Rejected summaries preserve reason/comment.
- Sensitive review actions create audit logs.

## 9. Monitoring Dashboard

Open:

```text
http://127.0.0.1:8080/admin/dashboard
```

Show:

- Summary status counts.
- Usage metrics.
- Safety metrics.
- MVP readiness gates.
- Review metrics.
- Audit log table and filters.

Explain that this is a read-only clinical quality and audit view.

## 10. Evaluation & Demo Control Center

Open:

```text
http://127.0.0.1:8080/evaluation-demo
```

Show:

- Golden path status.
- Provider status.
- Citation and safety status.
- HITL review status.
- Monitoring summary.
- Three-layer evaluation.
- Functional validation runner.
- Human evaluation form.
- Final demo checklist.

Click `Run Functional Validation`.

Expected current result:

```text
passed
```

## 11. Three-layer Evaluation

Layer A - Functional validation:

- Runs now on mock/de-identified data.
- Validates workflow behavior, not clinical model quality.

Layer B - Real EHR benchmark:

- Prepared but pending.
- Expected file: `data/processed/ehr_benchmark/test.jsonl`.
- No benchmark metrics are claimed without credentialed real/de-identified EHR
  data such as MIMIC-IV-Note or MIMIC-IV-Ext-BHC.

Layer C - Human evaluation:

- Can run now on demo outputs.
- Collects reviewer scores and comments.
- Must be described as demo usability/safety review unless real clinical
  validation is conducted.

## 12. Limitations

- No production SSO/OAuth.
- No production HIS/EMR writeback.
- No real EHR benchmark results yet.
- BART/Pegasus real execution requires explicit local model enablement.
- Gemini external calls require explicit governance flags and API key.
- Safety checks are MVP-level, not a certified clinical safety system.

## 13. Closing

The final MVP demonstrates a production-style workflow for evidence-grounded,
doctor-reviewed medical record summarization. It is ready for local demo and
internship submission, while real benchmark performance remains pending until
credentialed EHR data is available.
