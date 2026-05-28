# Phase 6 Manual QA Checklist

Use mock/de-identified data only.

## Admin Dashboard

- [ ] Clinical admin can open `/admin/dashboard`.
- [ ] Overview cards load without fake data.
- [ ] Summary status breakdown displays draft, under review, edited, approved, rejected, and archived counts.
- [ ] Safety metrics load and show citation coverage, unsupported claims, conflicting claims, and MVP readiness status.
- [ ] Review metrics load and show approvals, rejections, edits, and rejection reasons when present.
- [ ] Usage metrics load and show patients, encounters, documents, chunks, summaries, and model runs.
- [ ] Audit table loads recent events.
- [ ] Audit filters work for action.
- [ ] Audit filters work for patient_id.
- [ ] Clicking an audit row opens safe audit detail.
- [ ] Empty states display clearly when no data exists.
- [ ] Dashboard does not expose raw clinical document text or patient names.
- [ ] Nurse role cannot access global dashboard metrics.

## Safety Boundaries

- [ ] Dashboard is read-only.
- [ ] No diagnosis recommendation action is present.
- [ ] No treatment recommendation action is present.
- [ ] No prescription action is present.
- [ ] No autonomous discharge approval action is present.
- [ ] No medical image diagnosis action is present.

## Audit Coverage Review

- [ ] `generate_summary` events are visible after summary generation.
- [ ] `view_summary` events are visible after opening summary detail.
- [ ] `view_citation` events are visible after opening citation evidence.
- [ ] `edit_summary` events are visible after clinician edit.
- [ ] `approve_summary` events are visible after clinician approval.
- [ ] `reject_summary` events are visible after clinician rejection.
- [ ] `import_data` events are visible after FHIR-like import.
