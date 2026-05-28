# 08 — Role-based UI and Permission Model

**Document type:** Role-based UI Specification  
**Version:** v1.0  

---

## 1. Purpose

This document defines the role-based UI and permission model for the Medical Record Summarization MVP. Role-based access is important because medical AI workflows involve different responsibilities: doctors review and approve, admins monitor, IT configures/imports, auditors review logs, and evaluators score model outputs.

The MVP uses mock/header-based roles. Production future work should replace this with SSO/OAuth and stricter RBAC.

---

## 2. Supported Roles

| Role | Description |
|---|---|
| doctor | primary clinical reviewer and approver |
| nurse | limited viewer of approved/clinical context |
| clinical_admin | quality and metrics reviewer |
| it_admin | ingestion, system health, provider status |
| auditor | audit log and review history reader |
| ai_safety_reviewer | safety/citation issue reviewer |
| evaluation_reviewer | human evaluation scorer |

---

## 3. Role-based Navigation

### Doctor

- Patient List
- Patient Detail
- AI Summary Workspace
- My Reviews
- Evaluation Demo Center

### Nurse

- Patient List limited
- Approved Summaries
- Citation View limited
- Evaluation Demo Center read-only

### Clinical Admin

- Admin Dashboard
- Metrics
- Safety Overview
- Human Evaluation Summary
- Evaluation Demo Center

### IT Admin

- Ingestion / Demo Seed
- Provider Status
- System Health
- Admin Dashboard
- Evaluation Demo Center

### Auditor

- Audit Logs
- Review History
- Evaluation Demo Center read-only

### AI Safety Reviewer

- Safety Overview
- Unsupported Claims
- Citation Quality
- Evaluation Demo Center

### Evaluation Reviewer

- Human Evaluation Form
- Model Comparison
- Evaluation Demo Center

---

## 4. Action Permission Matrix

| Action | Doctor | Nurse | Clinical Admin | IT Admin | Auditor | AI Safety Reviewer | Evaluation Reviewer |
|---|---:|---:|---:|---:|---:|---:|---:|
| View patient | Yes | Limited | Limited | No | Read-only | Limited | No |
| Generate summary | Yes | No | No | No | No | No | No |
| View summary | Yes | Approved only | Yes | No | Read-only | Yes | Yes |
| View citation | Yes | Limited | Yes | No | Read-only | Yes | Yes |
| Edit summary | Yes | No | No | No | No | No | No |
| Approve/reject | Yes | No | No | No | No | No | No |
| View audit logs | Limited | No | Yes | Yes | Yes | Read-only | No |
| Import data | No | No | No | Yes | No | No | No |
| Run functional validation | Yes/optional | No | Yes | Yes | Read-only | Yes | No |
| Submit human evaluation | Optional | Optional | Optional | No | No | Optional | Yes |

---

## 5. Frontend Behavior

### Role selection

MVP should provide a role selector or mock login screen.

Selected role should be shown as a badge:

```text
Current role: doctor
```

### Page guard

If user opens unauthorized page:

```text
Access denied. Your current role does not have permission to access this page.
```

### Action guard

If role cannot perform action:

- Hide the button, or
- Disable it with explanatory tooltip.

Example:

```text
Only doctor can approve or reject a clinical summary.
```

---

## 6. Backend Permission Alignment

Frontend hiding is not enough. Backend must reject unauthorized sensitive actions.

Backend must enforce:

| Endpoint/action | Required role |
|---|---|
| generate summary | doctor |
| edit summary | doctor |
| approve summary | doctor |
| reject summary | doctor |
| global audit logs | clinical_admin / it_admin / auditor |
| ingestion | it_admin |
| metrics dashboard | clinical_admin / it_admin / auditor / ai_safety_reviewer |
| human evaluation submit | evaluation_reviewer or allowed reviewer roles |

---

## 7. Role-based UI in Evaluation Center

Evaluation Center should show:

| Capability | Display |
|---|---|
| Can run functional validation | yes/no |
| Can view audit logs | yes/no |
| Can view metrics | yes/no |
| Can submit human evaluation | yes/no |
| Can approve summary | yes/no |
| Real benchmark status | visible to all allowed roles |

---

## 8. Security and Privacy Notes

- Use de-identified patient IDs in UI where possible.
- Avoid exposing raw clinical text to roles that do not need it.
- Do not expose external LLM configuration to non-IT roles.
- Do not show full audit metadata to non-auditor roles.
- All sensitive actions must create audit logs.

---

## 9. MVP vs Production

### MVP implementation

- Mock role selector
- Header-based role code
- Static route guards
- Backend permission checks for high-risk actions

### Production future work

- SSO/OAuth2
- SMART on FHIR launch context
- Patient-level access control
- Department-level policies
- Audit export
- Session timeout
- Security review

---

## 10. Acceptance Criteria

| ID | Criterion |
|---|---|
| RBAC-01 | User can select role in MVP UI |
| RBAC-02 | Navigation changes by role |
| RBAC-03 | Doctor can approve/reject |
| RBAC-04 | Nurse cannot approve/reject |
| RBAC-05 | Auditor sees audit logs read-only |
| RBAC-06 | IT Admin can access ingestion/system status |
| RBAC-07 | Evaluation Reviewer can submit human evaluation |
| RBAC-08 | Backend rejects unauthorized approval even if API called directly |
| RBAC-09 | Evaluation Center shows role capability status |
