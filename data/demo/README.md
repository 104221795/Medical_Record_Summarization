# Final Demo Cases

`final_demo_cases.json` contains three curated, de-identified FHIR-like import
payloads for the final internship demo:

1. `final_supported_citations_001` - normal case with supported citations.
2. `final_missing_information_002` - missing-information case.
3. `final_unsupported_weak_evidence_003` - unsupported or conflicting evidence case.

These cases are mock/de-identified fixtures for functional demonstration only.
They are not real EHR benchmark data and must not be used to claim clinical
model quality.

`seed_clinical_cases.json` contains ten richer, de-identified, MIMIC-III-demo-
inspired sandbox cases used by `python -m backend.app.db.seed` and
`POST /api/v1/demo/seed`. The local MIMIC-III demo `NOTEEVENTS.csv` does not
contain usable clinical note rows, so these cases combine de-identified MIMIC
demo admission metadata with synthetic clinical note text for workflow testing.
They are suitable for UI, citation, safety, and HITL functional validation, not
for real model quality claims.

To use one case manually:

1. Start the backend.
2. Copy one case's `fhir_like_import` object.
3. POST it to `/api/v1/ingestion/import` with demo headers.
4. Open `/doctor-demo`, select the imported patient, and generate a draft
   `patient_snapshot`.

The committed real benchmark location remains empty until credentialed data is
available:

```text
data/processed/ehr_benchmark/test.jsonl
```
