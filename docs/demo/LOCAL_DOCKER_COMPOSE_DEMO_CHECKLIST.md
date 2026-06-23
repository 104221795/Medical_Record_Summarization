# Local Docker Compose Demo Checklist

This is the validated Week 5 staging/demo path. Public Render or Railway
deployment is optional future work and is not required for the final demo.

> Safety boundary: use only mock or approved de-identified data. Every
> AI-generated summary is a draft that requires clinician review. This demo
> does not establish clinical safety, clinical effectiveness, production
> HIS/EMR integration, or real-EHR performance.

## 1. Prepare the Repository

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
git status --short
docker version
docker compose version
```

Confirm that no secret `.env` file, credential, real patient record, or
credentialed dataset will be captured in screenshots or the demo video.

## 2. Prepare the Portable Flow 2.1 Snapshot

The Admin dashboard reads `RAG_EVALUATION_ARTIFACT_ROOT`. Docker Compose maps
the repository folder `artifacts/evaluation` to `/app/artifacts`.

If the completed local snapshot still lives on the original D drive, copy only
the approved de-identified proxy-evaluation package:

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
$source = "D:\clin_summ_outputs\rag_best_models_benchmark_50_no_gate"
$target = "artifacts\evaluation\rag_best_models_benchmark_50_no_gate"

New-Item -ItemType Directory -Force "artifacts\evaluation" | Out-Null
Copy-Item -Recurse -Force $source $target

@{
  selected_output_dir = "rag_best_models_benchmark_50_no_gate"
} | ConvertTo-Json | Set-Content `
  "artifacts\evaluation\latest_rag_best_models.json" `
  -Encoding utf8
```

Confirm the required files exist:

```powershell
Get-Item `
  "artifacts\evaluation\rag_best_models_benchmark_50_no_gate\model_comparison.csv", `
  "artifacts\evaluation\rag_best_models_benchmark_50_no_gate\per_record_metrics.csv", `
  "artifacts\evaluation\latest_rag_best_models.json"
```

Do not rerun the heavy benchmark for the demo. The expected snapshot is:

- 50 records x 5 providers;
- 250/250 no-gate predictions completed;
- BERTScore available for all five providers;
- separate stricter gated evidence: 50/50 evaluated, 48 generated, 2 blocked.

## 3. Start the Staging Topology

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
docker compose up --build -d
docker compose ps
```

Expected services:

- `app`;
- `worker`;
- `db`;
- `redis`.

Wait until PostgreSQL and the web service are healthy and the RQ worker is
registered.

## 4. Bootstrap De-identified Demo Data and Accounts

Run the local-only helper. It prompts for one temporary password without
printing it:

```powershell
docker compose exec app python -m scripts.bootstrap_demo_accounts
```

Accounts:

```text
Doctor: doctor.demo@example.invalid
Admin:  clinical.admin@example.invalid
```

Do not reuse a real password. Do not place the temporary password in Git,
screenshots, logs, or the evidence package.

## 5. Verify Health and Readiness

```powershell
$health = Invoke-RestMethod "http://127.0.0.1:8080/health"
$ready = Invoke-RestMethod "http://127.0.0.1:8080/ready"

$health | ConvertTo-Json -Depth 10
$ready | ConvertTo-Json -Depth 10
```

Expected:

- `/health` returns HTTP 200 with `status: ok`;
- `/ready` returns HTTP 200;
- database check passes;
- Redis/RQ and worker checks pass;
- deterministic provider is selectable;
- artifact root is readable;
- `clinical_use` remains `staging_demo_only`.

If `/ready` initially returns HTTP 503, inspect startup state and wait for the
worker:

```powershell
docker compose ps
docker compose logs --tail 100 app worker db redis
```

Do not continue recording until readiness is understood.

## 6. Doctor End-to-End Flow

Open:

```text
http://127.0.0.1:8080/login
```

Use the doctor demo account and the temporary password.

- [ ] Log in as Doctor.
- [ ] Open Patient List.
- [ ] Select a de-identified patient.
- [ ] Select the intended encounter.
- [ ] Start summary generation with the deterministic staging provider.
- [ ] Confirm the result is labeled as an AI-generated draft.
- [ ] Open Review & Evidence.
- [ ] Select important claims and inspect their citation/source evidence.
- [ ] Confirm unsupported or conflicting evidence remains visible.
- [ ] Edit the draft to demonstrate clinician control.
- [ ] Approve, reject, or request revision according to the displayed evidence.
- [ ] Confirm the review action and reviewer identity are recorded.

Do not describe approval as autonomous. The clinician is the decision-maker.

## 7. Audit Trail

After the doctor action:

- [ ] Sign out.
- [ ] Sign in with the Admin demo account.
- [ ] Open the audit page.
- [ ] Locate generation, citation-view, edit, approval/rejection, and review
  events from the demo.
- [ ] Confirm the audit export is marked PHI-safe and does not expose raw
  clinical note text.

## 8. Admin Flow 2.1

Open the Admin Evaluation pages:

- [ ] Evaluation Readiness.
- [ ] Benchmark Results.
- [ ] RAG Best Models / Flow 2.1.

Confirm:

- [ ] the selected output is under `/app/artifacts`;
- [ ] five providers are visible: deterministic, BART, Pegasus, Qwen2.5, and
  Llama3.2;
- [ ] each provider shows 50/50 completion in the no-gate snapshot;
- [ ] total predictions are 250/250;
- [ ] BERTScore is displayed for all five providers;
- [ ] Qwen2.5 is described as the strongest generative provider for this proxy
  run;
- [ ] deterministic is described as the smoke/control provider;
- [ ] BART and Pegasus remain baseline comparisons;
- [ ] the proxy-evaluation notice is visible.

State verbally:

> These results are proxy evaluation only. They do not establish clinical
> safety, clinical effectiveness, or real-world healthcare performance. The
> separate stricter gated run evaluated all 50 records per provider, generated
> 48 summaries, and intentionally blocked 2 records with insufficient required
> evidence.

## 9. Capture Evidence

Follow `docs/demo/DEMO_EVIDENCE_PACKAGE.md`. Capture:

- health and readiness output;
- service status and limited logs;
- doctor draft and citation review;
- clinician review action;
- audit trail;
- Flow 2.1 provider table and BERTScore;
- visible proxy-evaluation disclaimer.

## 10. Stop or Reset

Stop services while preserving PostgreSQL data:

```powershell
docker compose down
```

Only when an intentional clean demo reset is required:

```powershell
docker compose down --volumes
```

The second command removes local Compose database state. Confirm that this is
desired before running it.

