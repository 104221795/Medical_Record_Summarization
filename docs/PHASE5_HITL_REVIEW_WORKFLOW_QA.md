# Phase 5 HITL Review Workflow QA

Use the FastAPI-served UI at:

```text
http://localhost:8080/doctor-demo
```

Manual checklist:

- Select mock role `doctor` and continue.
- Create demo data if the local database is empty.
- Open a patient, generate a `patient_snapshot` summary, and confirm status is `draft`.
- Click `Start Review` and confirm status changes to `under_review`.
- Click `Edit`, change the summary text, add an edit comment, and click `Save Edit`.
- Confirm status changes to `edited` and the UI warns that citation mapping may need revalidation.
- Click `View Review History` and confirm `start_review` and `edit` entries are visible.
- Click `Approve`, confirm the Vietnamese approval modal text is shown, and approve.
- Confirm status changes to `approved` and normal editing is locked.
- Generate or open another draft summary, click `Reject`, and confirm both `rejection_reason` and `rejection_comment` are required.
- Reject with a valid reason such as `wrong_citation`.
- Confirm status changes to `rejected`, the reason/comment are visible, and review history includes `reject`.
- Log in as mock `nurse` and confirm approve/reject actions fail with a permission error if attempted.
- Confirm Safety Panel remains visible before approval with citation coverage, unsupported claim count, and conflict count.
- Confirm the UI still has no diagnosis recommendation, treatment recommendation, prescription, autonomous discharge approval, or medical image diagnosis actions.

Backend API smoke examples:

```http
POST /api/v1/summaries/{summary_id}/review/start
PATCH /api/v1/summaries/{summary_id}/edit
POST /api/v1/summaries/{summary_id}/approve
POST /api/v1/summaries/{summary_id}/reject
GET /api/v1/summaries/{summary_id}/reviews
```
