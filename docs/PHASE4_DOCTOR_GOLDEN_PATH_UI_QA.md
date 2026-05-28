# Phase 4 Doctor Golden Path UI QA

Use the FastAPI-served UI at:

```text
http://localhost:8080/doctor-demo
```

Manual checklist:

- Select the mock `doctor` role and continue.
- If the local database is empty or uninitialized, click `Create demo data`.
- Confirm demo seeding creates de-identified records and then the Patient List loads from `GET /api/v1/patients`.
- Open a patient and confirm Patient Detail renders patient header, encounters, and documents.
- Click `Generate AI Summary`.
- Generate a `patient_snapshot` summary.
- Confirm the summary is labeled `Draft` and does not appear as an official clinical conclusion.
- Confirm required sections render: Patient Snapshot, Active Problems, Recent Clinical Course, Medications, Labs and Imaging Highlights, Needs Clinician Review.
- Confirm supported claims show clickable citation badges.
- Confirm claims without citations show `Missing citation`.
- Click a citation and confirm the Evidence Panel updates with source type, highlighted span, surrounding context, and metadata.
- Confirm the Safety Panel shows status, citation coverage, unsupported claim count, and conflict count.
- Confirm unsupported or insufficient-evidence claims are visible in the Safety Panel or Needs Clinician Review section.
- Confirm `Regenerate` creates a new draft version after a summary exists.
- Confirm Phase 5 review actions are visible: Start Review, Edit, Approve, Reject, and View Review History.
- Confirm there are no UI actions for diagnosis recommendation, treatment recommendation, prescription, autonomous discharge approval, or medical image diagnosis.

Known Phase 4 API gap:

- Patient List cannot display last summary status from the backend because `GET /api/v1/patients/{patient_id}/summaries` is not implemented yet.
