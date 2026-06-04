# React UI Refactor

This repository now includes a new React JSX frontend in `frontend/`. The legacy backend-served HTML UIs under `backend/ui/` are preserved and remain available while the React app is validated.

## Structure

- `frontend/src/routes/`: React Router route definitions and role guards.
- `frontend/src/layouts/`: shared layout shell with role-aware sidebar and topbar.
- `frontend/src/components/common/`: reusable UI primitives.
- `frontend/src/components/navigation/`: sidebar, topbar, role switcher, breadcrumbs.
- `frontend/src/components/patient/`: patient list, detail header, clinical timeline, document viewer.
- `frontend/src/components/summary/`: summary workspace, provider selector, citations, claims, review actions.
- `frontend/src/components/admin/`: admin overview, dataset status, system health, audit logs.
- `frontend/src/components/evaluation/`: model comparison dashboard, ROUGE cards, report/failure panels.
- `frontend/src/pages/`: doctor, admin, and shared pages.
- `frontend/src/services/`: backend API wrappers.
- `frontend/src/hooks/`: small data-fetching and role/session hooks.
- `frontend/src/context/`: demo auth/session and role context.

## Role-Based UI

The React app uses a simple demo role context with `Doctor` and `Admin` roles. It does not implement production authentication.

Doctor navigation includes:

- Dashboard
- Patients
- Summary Review
- Audit History

Doctor workflow:

1. Open Patients.
2. Select a patient.
3. Review encounter timeline and documents.
4. Generate a draft summary with provider selection.
5. Inspect citations, claim validation, and unsupported claims.
6. Edit, approve, reject, or request revision through review actions.

Admin navigation includes:

- Dashboard
- Dataset Governance
- Evaluation
- Benchmark Results
- Audit Logs
- Settings

Admin workflow:

1. Review system/provider readiness.
2. Inspect dataset governance status.
3. Open Evaluation to compare deterministic, BART, Pegasus PubMed, and Pegasus CNN/DailyMail results.
4. Review failure analysis/report availability.
5. Inspect audit logs and system health.

## Connected Backend APIs

The React services call existing backend routes:

- `GET /api/v1/patients`
- `GET /api/v1/patients/{patient_id}`
- `GET /api/v1/patients/{patient_id}/encounters`
- `GET /api/v1/patients/{patient_id}/documents`
- `POST /api/v1/patients/{patient_id}/summaries/generate`
- `GET /api/v1/summaries/{summary_id}`
- `POST /api/v1/summaries/{summary_id}/review/start`
- `PATCH /api/v1/summaries/{summary_id}/edit`
- `POST /api/v1/summaries/{summary_id}/approve`
- `POST /api/v1/summaries/{summary_id}/reject`
- `GET /api/v1/evaluation/benchmark/results`
- `GET /api/v1/audit/logs`

Supported summary providers:

- `deterministic`
- `gemini`
- `bart`
- `pegasus_pubmed`
- `pegasus_cnn_dailymail`

## Run Frontend

From `frontend/`:

```powershell
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The frontend expects the backend API at `/api/v1`. For local development, run the FastAPI backend on port `8080`; `frontend/vite.config.js` proxies `/api` requests to `http://127.0.0.1:8080`.

Build:

```powershell
npm run build
```

## Evaluation Dashboard

The dashboard reads:

```text
D:\clin_summ_outputs\medium_benchmark_bart_pegasus\model_comparison.csv
D:\clin_summ_outputs\medium_benchmark_bart_pegasus\EVALUATION_REPORT.md
D:\clin_summ_outputs\medium_benchmark_bart_pegasus\failure_analysis.md
```

Every evaluation report must preserve:

> Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes.
