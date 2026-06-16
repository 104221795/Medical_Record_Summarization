# QA Checklist

Use this checklist before every Railway staging deploy. Mark each item Pass/Fail/N/A.

## Doctor Workflow

| Check | Result | Notes |
| --- | --- | --- |
| Doctor dashboard loads |  |  |
| Patient list loads |  |  |
| Patient selection works |  |  |
| Provider selection works |  |  |
| Summary generation works |  |  |
| Async generation shows progress/status |  |  |
| Draft preview appears after generation |  |  |
| Review & Evidence opens from draft |  |  |
| Citation hover works on desktop |  |  |
| Citation click/tap works on touch/mobile |  |  |
| Evidence card highlight works |  |  |
| Linked claim highlight works |  |  |
| Unsupported claims are visible and prominent |  |  |
| Approve works only when safety gates permit it |  |  |
| Reject/request revision works with reason/comment |  |  |
| Patient history updates |  |  |
| Audit/history updates |  |  |

## Admin Evaluation

| Check | Result | Notes |
| --- | --- | --- |
| Admin dashboard loads |  |  |
| Benchmark overview loads |  |  |
| Model comparison loads |  |  |
| Flow 2.1 results load or show graceful empty state |  |  |
| Failure analysis loads or shows graceful empty state |  |  |
| Artifact paths resolve or show missing-state guidance |  |  |
| Provider readiness page loads |  |  |
| Jobs/readiness page loads |  |  |

## Backend

| Check | Result | Notes |
| --- | --- | --- |
| `GET /health` returns 200 |  |  |
| `GET /ready` returns structured JSON |  |  |
| Patient endpoint works |  |  |
| Generation endpoint returns a draft |  |  |
| Review endpoint works |  |  |
| Audit/history endpoint works |  |  |
| Audit export returns PHI-safe output |  |  |
| Artifact resolver handles missing artifacts cleanly |  |  |

## Safety

| Check | Result | Notes |
| --- | --- | --- |
| AI output is marked as draft |  |  |
| Human review is required before approval |  |  |
| Unsupported claims cannot be hidden |  |  |
| Citation coverage/status is visible |  |  |
| Proxy evaluation disclaimer is visible in admin/evaluation areas |  |  |
| Demo data is mock/de-identified only |  |  |
| No auto-approval path exists |  |  |
| Wrong-patient citation is blocked before approval |  |  |
| Encounter-scoped citation mismatch is blocked before approval |  |  |

## Responsive UI

| Viewport | Result | Notes |
| --- | --- | --- |
| Desktop 1920px |  |  |
| Desktop 1440px |  |  |
| Laptop 1280px |  |  |
| Tablet 768-1024px |  |  |
| Mobile 375-430px |  |  |

Acceptance: no horizontal overflow, no clipped buttons, action bars do not cover content, citation/evidence tracing remains usable.

## Deployment

| Check | Result | Notes |
| --- | --- | --- |
| Clean clone setup documented |  |  |
| Environment variables documented |  |  |
| Docker build works |  |  |
| `docker compose up --build` starts |  |  |
| Railway config exists |  |  |
| Railway service uses `$PORT` |  |  |
| CI passes |  |  |
| `.env` and local caches are not committed |  |  |
