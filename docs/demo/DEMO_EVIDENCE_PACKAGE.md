# Final Demo Evidence Package

Use this document as the index for final local Docker Compose evidence. Do not
invent missing evidence. Mark an item `Not captured` with a reason until the
corresponding file, screenshot, output, or link exists.

> Evidence scope: de-identified, clinician-review-only PoC. Proxy benchmark
> evidence does not establish clinical safety, clinical effectiveness,
> production HIS/EMR integration, or real-EHR performance.

## Package Metadata

| Item | Value |
| --- | --- |
| Repository commit | Working tree snapshot; record final commit after approval |
| Evidence capture date | `2026-06-22` |
| Operator | Local project operator |
| Demo environment | Local Docker Compose staging |
| Data boundary | Mock/de-identified only |
| Public cloud deployment | Not required; optional future work |

## Required Evidence

| Evidence | Expected content | File/link | Status |
| --- | --- | --- | --- |
| `/health` | HTTP 200 and `status: ok` | `artifacts/demo_evidence/2026-06-22/health.json` | Captured |
| `/ready` | HTTP 200; database, queue/worker, provider, and artifact checks visible | `artifacts/demo_evidence/2026-06-22/ready.json` | Captured |
| Backend full suite | Current Week 5 result: 172 passed; recorded Week 4 result: 165 passed | `artifacts/demo_evidence/2026-06-22/backend_full_suite.txt` | Current captured; historical result preserved separately |
| Deployment-focused tests | Recorded Week 4 evidence: 19 passed | `[LOG_OR_SCREENSHOT]` | Historical evidence; attach source |
| Week 5 lightweight tests | 37 passed; 2 dependency warnings | `artifacts/demo_evidence/2026-06-22/backend_lightweight_tests.txt` | Captured |
| Frontend build | Successful `npm run build` output | `artifacts/demo_evidence/2026-06-22/frontend_build.txt` | Captured |
| Docker build | Successful build output/image tag | `artifacts/demo_evidence/2026-06-22/docker_build.txt` | Captured |
| Docker Compose status | `app`, `worker`, `db`, and `redis`; health/status visible | `artifacts/demo_evidence/2026-06-22/docker_compose_ps.txt` | Captured |
| Docker Compose logs | Startup, migration, Redis/RQ worker registration; no secrets | `artifacts/demo_evidence/2026-06-22/docker_compose_logs.txt` | Captured |
| Doctor draft | Patient/encounter-scoped AI-generated draft label | `[SCREENSHOT]` | Not captured |
| Citation/evidence review | Claim and supporting source evidence visible | `[SCREENSHOT]` | Not captured |
| Clinician action | Edit plus approve/reject/request-revision evidence | `[SCREENSHOT]` | Not captured |
| Audit trail | Relevant review events and PHI-safe audit behavior | `[SCREENSHOT_OR_EXPORT]` | Not captured |
| Admin Flow 2.1 | Five provider rows and 50/50 no-gate completion | `[SCREENSHOT]` | Not captured |
| BERTScore | BERTScore columns populated for all five providers | `artifacts/demo_evidence/2026-06-22/flow_2_1_summary.json` | Data captured; UI screenshot pending |
| Proxy disclaimer | Proxy-evaluation notice present in API/report | `artifacts/demo_evidence/2026-06-22/flow_2_1_summary.json` | Data captured; UI screenshot pending |
| Demo video | Final end-to-end recording | `[LOCAL_PATH_OR_LINK]` | Not recorded |
| SharePoint upload | Folder/link and access check | `[SHAREPOINT_LINK]` | Not uploaded |

## Current Week 5 Verification — 2026-06-22

These checks were run during the repository-hardening work. Final screenshots
or exported logs still need to be added to the package paths above.

| Check | Result |
| --- | --- |
| Python compile | Passed for artifact resolver, evaluation service, runtime config, main app, benchmark scripts, and demo bootstrap helper |
| Current backend full suite | 172 passed, 0 failed; 2 dependency deprecation warnings |
| Lightweight backend tests | 37 passed, 0 failed; 2 dependency deprecation warnings |
| Frontend production build | Passed; Vite transformed 1,866 modules |
| Docker build | Passed |
| Docker Compose config | Passed |
| Docker Compose topology | App healthy; PostgreSQL healthy; Redis running; RQ worker running |
| `/health` | HTTP 200 |
| `/ready` | HTTP 200; database, artifacts, jobs, providers, and configuration passed; overall status degraded only by the expected unconfigured local vector-store warning |
| Current image size | 122,268,908 bytes (approximately 122.27 MB) |
| Portable Admin Flow 2.1 | `/app/artifacts/rag_best_models_benchmark_50_no_gate` selected; 5 providers; 250 completed predictions; BERTScore on 5 providers; Qwen2.5 selected by ROUGE-L; proxy warning present |

The recorded Week 4 full-suite result remains 165 passed, and the recorded
Week 4 deployment-focused result remains 19 passed. Current Week 5 evidence is
reported separately: 172 passed for the full suite and 37 passed for the
lightweight verification set.

## Benchmark Artifact Index

Portable package root:

```text
artifacts/evaluation/
```

Expected Flow 2.1 snapshot:

```text
artifacts/evaluation/
  latest_rag_best_models.json
  rag_best_models_benchmark_50_gated/
  rag_best_models_benchmark_50_no_gate/
    model_comparison.csv
    per_record_metrics.csv
    per_record_failure_analysis.jsonl
    all_predictions.jsonl
    deterministic_predictions.jsonl
    bart_predictions.jsonl
    pegasus_predictions.jsonl
    qwen2.5_predictions.jsonl
    llama3.2_predictions.jsonl
    EVALUATION_REPORT.md
    run_summary.json
    artifact_manifest.json
    rag_benchmark_manifest.json
    reproducibility_manifest.json
  historical_flow_metrics/
    flow_1_raw_per_record_metrics.csv
    flow_1_5_context_per_record_metrics.csv
    flow_2_rag_per_record_metrics.csv
  week5_analysis/
    WEEK5_P1_P2_ANALYSIS.md
    analysis_manifest.json
    diversity_strata_metrics.csv
    provider_failure_matrix.csv
    metric_correlations.csv
    retrieval_gate_case_analysis.csv
    retrieval_threshold_sensitivity.csv
    human_review_cases.jsonl
    human_review_scores.csv
```

Record actual availability without assuming every optional file exists:

| Artifact | Actual path | Present |
| --- | --- | --- |
| Model comparison | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/model_comparison.csv` | Yes |
| Per-record metrics | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/per_record_metrics.csv` | Yes |
| Failure analysis | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/per_record_failure_analysis.jsonl` | Yes |
| Provider predictions | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/*_predictions.jsonl` | Yes |
| Evaluation report | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/EVALUATION_REPORT.md` | Yes |
| Run summary | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/run_summary.json` | Yes |
| Artifact manifest | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/artifact_manifest.json` | Yes |
| Reproducibility manifest | `artifacts/evaluation/rag_best_models_benchmark_50_no_gate/reproducibility_manifest.json` | Yes |

## Metric Consistency Checklist

- [ ] Historical optimized 50-record baseline remains separate.
- [ ] Week 3 20-record provider-selection run remains separate.
- [x] Week 4 stricter gated run remains separate: 50/50 evaluated, 48 generated,
  2 blocked per provider.
- [x] Pre-diversity no-gate run remains separate: 50 records x 5 providers,
  250/250 predictions completed.
- [x] BERTScore is attributed to the no-gate run and was computed from saved
  prediction/reference pairs.
- [x] Qwen2.5 is described only as the strongest generative provider in the
  stated proxy run.
- [x] Deterministic is described as the most reliable smoke/control provider.
- [x] No benchmark result is described as clinical validation.

## Video Recording Checklist

- [ ] Hide passwords, secrets, tokens, and `.env` contents.
- [ ] Do not show identifiable or credentialed clinical data.
- [ ] Begin with the PoC and proxy-evaluation disclaimer.
- [ ] Show `/health` and `/ready`.
- [ ] Complete the doctor draft/review flow.
- [ ] Show citation evidence and unsupported/conflicting evidence behavior.
- [ ] Show the audit trail.
- [ ] Show Admin Flow 2.1 and BERTScore.
- [ ] Explain the separate no-gate and stricter gated runs.
- [ ] End with limitations and clinician-review requirement.

## SharePoint Upload Checklist

- [ ] Create a clearly named Week 5/final-demo folder.
- [ ] Upload the final report and demo checklist.
- [ ] Upload evidence logs/screenshots after checking for secrets and PHI.
- [ ] Upload benchmark reports/manifests, not unreviewed raw clinical data.
- [ ] Upload the final demo video.
- [ ] Test the link with the intended reviewer permissions.
- [ ] Record the final link in this document.

## Final Evidence Sign-off

```text
Evidence package complete: [YES/NO]
Missing items:
- [ITEM]

Reviewed for secrets/PHI: [YES/NO]
Reviewer:
Date:
```
