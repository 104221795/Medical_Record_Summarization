# Submission Checklist

## Repository Safety

- [ ] Do not commit `.env`, credentials, or real clinical data.
- [ ] Keep raw/credentialed datasets outside git.
- [ ] Use mock/de-identified data for demo.
- [ ] Do not claim real EHR benchmark results without credentialed benchmark
      data.

## Environment Setup

```powershell
cd D:\MyNewDesktop\clin-summ
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-mlops.txt -r requirements-guardrails-onnx.txt
```

## Database Setup

```powershell
$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

## Run Backend

```powershell
.\.venv\Scripts\Activate.ps1
$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"
python -m uvicorn backend.app.main:app --reload --port 8080
```

Open:

- API docs: `http://127.0.0.1:8080/docs`
- Doctor UI: `http://127.0.0.1:8080/doctor-demo`
- Admin Dashboard: `http://127.0.0.1:8080/admin/dashboard`
- Evaluation & Demo Control Center: `http://127.0.0.1:8080/evaluation-demo`
- Citation demo: `http://127.0.0.1:8080/citation-demo`

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -p no:cacheprovider -q
```

Expected final validation result:

```text
101 passed
```

## Run Functional Validation

Use the UI:

1. Open `http://127.0.0.1:8080/evaluation-demo`.
2. Click `Run Functional Validation`.

Or call the API:

```http
POST /api/v1/evaluation/functional/run
```

Expected current status:

```text
passed
```

## Final Demo Cases

Curated demo cases are stored in:

```text
data/demo/final_demo_cases.json
```

Cases:

- Normal case with supported citations.
- Missing information case.
- Unsupported or weak/conflicting evidence case.

These are mock/de-identified fixtures for demonstration only.

## Doctor UI Demo Checklist

- [ ] Start backend.
- [ ] Open Doctor UI.
- [ ] Select mock role `doctor`.
- [ ] Seed demo data if needed.
- [ ] Open a patient.
- [ ] Generate `patient_snapshot`.
- [ ] Select provider.
- [ ] Show draft status.
- [ ] Click citation badge.
- [ ] Show evidence source panel.
- [ ] Show safety panel.
- [ ] Start review.
- [ ] Edit summary.
- [ ] Approve or reject.
- [ ] Show review history.

## Admin Dashboard Demo Checklist

- [ ] Open Admin Dashboard.
- [ ] Select role `clinical_admin`.
- [ ] Show summary status cards.
- [ ] Show usage metrics.
- [ ] Show safety metrics.
- [ ] Show review metrics.
- [ ] Show audit logs and filters.

## Evaluation Demo Checklist

- [ ] Open Evaluation & Demo Control Center.
- [ ] Show golden path status.
- [ ] Show provider status.
- [ ] Show three-layer evaluation cards.
- [ ] Run functional validation.
- [ ] Show Layer B `pending_dataset`.
- [ ] Explain mock data is not benchmark evidence.
- [ ] Optionally submit human evaluation for a generated summary.

## Pending Until Real EHR Data Is Available

The real EHR benchmark layer remains pending until this local-only file exists:

```text
data/processed/ehr_benchmark/test.jsonl
```

Expected schema:

```json
{
  "note_id": "note_001",
  "patient_id": "patient_001",
  "encounter_id": "enc_001",
  "source_note": "...",
  "reference_summary": "...",
  "dataset": "mimic_iv_note|mimic_iv_ext_bhc",
  "split": "test"
}
```

Do not commit real EHR data or derived clinical text.
