# 06 — Golden Path UI v1.0: Doctor Workspace, Admin Dashboard and Evaluation Center

**Document type:** UI Flow Specification  
**Version:** v1.0  

---

## 1. UI Design Goal

The UI must make the system feel like a realistic clinical workflow product, not only an AI demo. The central design principle is:

> Trust through verification: every important clinical claim should be easy to verify, and every AI-generated summary should remain draft until reviewed.

---

## 2. Main UI Surfaces

| UI surface | Main user | Purpose |
|---|---|---|
| Doctor Workspace | Doctor | Generate, verify, edit, approve/reject summaries |
| Admin Dashboard | Clinical Admin / IT Admin | Monitor quality, usage, audit and safety |
| Evaluation & Demo Control Center | Mentor/demo/evaluator | Show system readiness, evaluation layers and demo status |
| Human Evaluation Form | Evaluation Reviewer | Score generated summaries |
| Audit Log View | Auditor | Review sensitive actions |

---

## 3. Doctor Workspace Golden Path

```text
Role selection / login
→ Patient List
→ Patient Detail
→ AI Summary Workspace
→ Citation Evidence Panel
→ Safety Panel
→ HITL Review
→ Audit update
```

---

## 4. Screen 1 — Role Selection / Login

### Purpose

Allow MVP users to select role and load role-based navigation.

### UI elements

- Role selector: doctor, nurse, clinical_admin, it_admin, auditor, ai_safety_reviewer, evaluation_reviewer.
- Role badge in top navigation.
- Access denied state for unauthorized pages.

### Acceptance criteria

- Selected role is visible in UI.
- Role is sent to backend using existing role header/session mechanism.
- UI hides unavailable pages/actions.
- Backend still validates sensitive actions.

---

## 5. Screen 2 — Patient List

### Purpose

Help doctor find the patient to summarize.

### Display fields

| Field | Description |
|---|---|
| Patient ID/hash | De-identified patient reference |
| Age/Gender | Basic context |
| Current encounter | Admission/visit context |
| Last summary status | Draft/approved/rejected |
| Last updated | Data recency |

### Primary action

Open Patient Detail.

---

## 6. Screen 3 — Patient Detail

### Sections

| Section | Purpose |
|---|---|
| Patient header | ID, demographic, encounter status |
| Encounter list | Admission/visit records |
| Documents / structured records | Available clinical evidence |
| Existing summaries | Previous draft/approved/rejected summaries |
| Generate Summary CTA | Start summary generation |

---

## 7. Screen 4 — AI Summary Workspace

### Layout

```text
Header: Patient + Encounter + Provider + Summary status
Left: Summary Sections + Claims + Citation badges
Right: Evidence Panel
Bottom/Side: Safety Panel + Review Actions
```

### Provider selector

| Provider | UI state |
|---|---|
| Deterministic | Default / always available |
| BART | Available if configured or mock mode |
| Pegasus | Available if configured or mock mode |
| Gemini | Disabled unless API key and safety flags enabled |

### Summary sections

- Patient Snapshot
- Active Problems
- Recent Clinical Course
- Medications
- Labs and Imaging Highlights
- Needs Clinician Review

---

## 8. Citation Evidence Panel

### Trigger

User clicks a citation badge next to a claim.

### Display

| Field | Purpose |
|---|---|
| Source type | document_chunk, condition, observation, medication, report |
| Source title | document/record label |
| Timestamp | source recency |
| Highlighted span | exact evidence where available |
| Surrounding context | helps verification |
| Support status | supported / weak / unsupported |

### UX rule

Citation must never show evidence from another patient.

---

## 9. Safety Panel

### Display metrics

| Metric | Description |
|---|---|
| Citation coverage | share of clinical claims with evidence |
| Unsupported claims | claims without sufficient source |
| Weak citations | low-confidence evidence |
| Conflict count | contradictory evidence |
| Missing information | explicitly missing data |
| Approval blockers | safety issues preventing approval |

### Visual design

- Green: safe/supported.
- Yellow: weak/needs review.
- Red: unsupported/conflicting/approval blocking.

---

## 10. HITL Review UI

### Actions

| Action | Visible to | Behavior |
|---|---|---|
| Start Review | Doctor | summary status under_review |
| Edit | Doctor | editable summary text |
| Save Edit | Doctor | status edited |
| Approve | Doctor | confirmation modal, status approved |
| Reject | Doctor | reason required, status rejected |
| Review History | Doctor/Admin/Auditor | read-only history |

### Approval modal

```text
Bạn xác nhận đã kiểm tra bản tóm tắt và các citation liên quan trước khi phê duyệt?
```

### Reject modal required fields

- Rejection reason
- Comment

---

## 11. Admin Dashboard UI

### Purpose

Allow Clinical Admin and IT Admin to monitor system quality and usage.

### Dashboard cards

| Card | Metric |
|---|---|
| Total summaries | summary volume |
| Approval rate | approved / total reviewed |
| Rejection rate | rejected / total reviewed |
| Average citation coverage | evidence traceability |
| Unsupported claim count | safety risk |
| Model runs | provider usage |
| Audit events | governance activity |

### Dashboard tables

- Recent audit logs.
- Rejection reasons.
- Unsupported claims.
- Provider latency/status.

---

## 12. Evaluation & Demo Control Center

### Purpose

Provide one page for mentor/demo to see whether the MVP is ready.

### Tabs/sections

| Section | Purpose |
|---|---|
| Golden Path Status | Shows readiness of patient→summary→review flow |
| Provider Status | Deterministic/BART/Pegasus/Gemini readiness |
| Citation & Safety | Current citation/safety metrics |
| HITL Review | Summary status and recent review actions |
| Monitoring Summary | Dashboard-level metric snapshot |
| Three-layer/Four-layer Evaluation | Functional, structured EHR, proxy model, real benchmark pending, human eval |
| Final Demo Checklist | Step-by-step live demo readiness |

### Real benchmark status rule

If MIMIC-IV-Ext-BHC/MIMIC-IV-Note processed data is missing, UI must show:

```text
Real EHR note-level benchmark: Pending credentialed dataset.
```

No fake metrics.

---

## 13. Human Evaluation UI

### Purpose

Collect structured evaluation from reviewers.

### Form fields

| Field | Type |
|---|---|
| Summary ID | hidden/select |
| Model provider | deterministic/BART/Pegasus/Gemini |
| Factual correctness | 1–5 |
| Completeness | 1–5 |
| Conciseness | 1–5 |
| Readability | 1–5 |
| Citation usefulness | 1–5 |
| Hallucination risk | low/medium/high |
| Comments | text |

---

## 14. Empty/Error States

| Scenario | UI message |
|---|---|
| No data | Không đủ dữ liệu để tạo summary. |
| Provider unavailable | Provider chưa được cấu hình hoặc chưa được bật. |
| Gemini disabled | Gemini external provider is disabled by safety config. |
| Citation missing | Claim này chưa có bằng chứng đủ mạnh. |
| Permission denied | Bạn không có quyền thực hiện thao tác này. |
| Benchmark missing | Real EHR benchmark đang chờ credentialed dataset. |

---

## 15. UI Acceptance Criteria

- Doctor can generate draft summary.
- Provider selector is visible.
- Citation badges are clickable.
- Safety panel is visible.
- Doctor can edit/approve/reject.
- Approved summary is locked from normal editing.
- Admin dashboard shows metrics.
- Evaluation Center shows all layers and pending benchmark clearly.
- Role-based actions are hidden and backend-protected.
