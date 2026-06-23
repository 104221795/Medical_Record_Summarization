# Week 5 Repository Audit

Status: recommendation-first audit for the final local Docker Compose demo.

## Scope Freeze

Week 5 is limited to repeatability, demo evidence, documentation, presentation
readiness, metric consistency, and portable benchmark artifacts. Public cloud
deployment is optional future work. No large product feature or model-behavior
change is required for the final demonstration.

The project remains a de-identified, clinician-review-only PoC. AI-generated
summaries are drafts. This repository does not claim clinical safety, clinical
effectiveness, production HIS/EMR integration, real-EHR validation, or
autonomous clinical decision-making.

## Audit Findings and Recommendations

| Area | Finding | Recommendation | Action in this pass |
| --- | --- | --- | --- |
| Main documentation | `README.md` is the practical entry point, but its local verification and artifact-path guidance need a clearer Week 5 framing. | Keep `README.md` as the canonical run guide and link the final demo checklist and evidence package from it. | Update |
| Week 4 delivery | The report already separates the historical baseline, Week 3 run, stricter gated run, and no-gate 50-record run. Metrics and safety disclaimers are present. | Preserve all benchmark numbers and make Docker Compose the explicit current demo path. | Targeted wording only |
| Deployment documents | Railway documents are useful historical architecture evidence but can make public deployment look like the next required milestone. | Retain them, label public cloud as optional future work, and point current reviewers to the local Docker Compose checklist. | Document, do not delete |
| Benchmark loading | `backend/app/services/evaluation_service.py` discovers artifacts from fixed `D:/clin_summ_outputs` paths. | Resolve `RAG_EVALUATION_ARTIFACT_ROOT` first, fall back to repository-relative `artifacts/evaluation`, and retain the D-drive location only as legacy discovery. | Fix |
| Benchmark scripts | Several evaluation scripts default to `D:/clin_summ_outputs`. | Use the same configurable/repository-relative artifact root for new outputs. Keep explicit `--output-dir` support and legacy read fallback where required. | Fix primary scripts |
| Docker Compose artifacts | The app mounts an empty named volume at `/app/artifacts`, which does not automatically expose a prepared local benchmark package. | Bind-mount `artifacts/evaluation` read-only for the demo dashboard. | Fix |
| Admin evaluation frontend | Flow 2.1 already reads backend-selected artifacts and shows BERTScore, provider rows, per-record failures, and a proxy-evaluation notice. | Do not redesign the dashboard before the final demo. Verify it against the portable snapshot. | Verify only |
| Demo authentication | Staging correctly blocks public admin signup. A clean demo database therefore needs an intentional local account bootstrap step. | Provide a local-only bootstrap helper that prompts for a password and never commits it. | Add operational helper |
| Evidence capture | Evidence is distributed across Week 4, README, CI, screenshots, logs, and benchmark folders. | Use one evidence-package checklist with placeholders for files not yet captured. | Create |
| Duplicate documentation | `docs/8.USER_FLOW.md` and `docs/12.evaluationplan.md` currently have identical content hashes. | Review ownership and rename/consolidate only after checking inbound links. | Remaining cleanup; no deletion |
| Accidental root file | `taging hardening and verification…` contains terminal `less` help output and appears unrelated to the project. | Remove in a separate, explicitly reviewed cleanup commit. | Remaining cleanup; no deletion |
| Historical UI folders | `api/ui` and `backend/ui/*` coexist with the current React frontend. | Mark the React app as canonical; archive legacy demos only after confirming no test or mentor link depends on them. | Remaining cleanup |
| Cache defaults | Some local ML helpers still use Windows-specific `D:/hf_cache` defaults. | Later introduce configurable cache roots; this is not required for artifact loading or the final lightweight demo. | Remaining cleanup |

## Metric Consistency Result

The following statements are consistent between the current README and Week 4
evidence and must remain separate from newly run verification:

- recorded full backend suite: 165 passed, 0 failed;
- recorded deployment-focused suite: 19 passed;
- recorded Docker build: passed;
- recorded Docker Compose staging: passed;
- recorded `/health`: HTTP 200;
- recorded `/ready`: HTTP 200;
- recorded runtime image size: approximately 122 MB;
- heavy ML/benchmark packages are excluded from the runtime image;
- no-gate Flow 2.1: 50 records x 5 providers, 250/250 predictions completed,
  with BERTScore computed from saved predictions;
- stricter gated Flow 2.1: 50/50 records evaluated per provider, 48 generated
  and 2 intentionally blocked;
- Qwen2.5 is the strongest generative provider in the no-gate proxy run;
- deterministic is the most reliable smoke/control provider.

These are recorded delivery results, not clinical validation claims. Commands
run during Week 5 should be reported separately with their execution date and
must not silently replace the recorded Week 4 evidence.

Current verification captured separately on 2026-06-22: 172 backend tests
passed in the full suite and 37 tests passed in the lightweight staging suite.

## Recommended Canonical Week 5 Documents

1. `README.md` — project entry point and concise status.
2. `docs/demo/LOCAL_DOCKER_COMPOSE_DEMO_CHECKLIST.md` — executable demo flow.
3. `docs/demo/DEMO_EVIDENCE_PACKAGE.md` — evidence capture index.
4. `docs/delivery 4/delivery week4.md` — preserved Week 4 delivery evidence.
5. `docs/demo/WEEK5_REPOSITORY_AUDIT.md` — cleanup decisions and deferred work.

## Remaining Cleanup Requiring Separate Review

- Remove the accidental pager-output file from the repository root.
- Decide which of `docs/8.USER_FLOW.md` and `docs/12.evaluationplan.md` is
  canonical, then replace the duplicate with a redirect/index note.
- Review whether the legacy `api/` app and `backend/ui/*` demos are still used.
- Standardize local Hugging Face and Ollama cache paths independently from
  benchmark artifact portability.
- Capture the actual final screenshots, logs, video link, and SharePoint link.
