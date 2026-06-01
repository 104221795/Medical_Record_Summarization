# Documentation Index

This directory is the source of truth for product scope, clinical safety, API/FHIR design, UI direction, and evaluation framing.

## Read First

| File | Use it for |
| --- | --- |
| `mentor_delivery_week_1/README_FOR_MENTOR_ONLY.md` | Mentor-facing summary, evidence ladder, current results, and Q&A |
| `mentor_delivery_week_1/01_PRD_V1_MEDICAL_RECORD_SUMMARIZATION.md` | Product requirements and scope boundaries |
| `mentor_delivery_week_1/02_USER_FLOW_V1.md` | Doctor workflow, citation verification, HITL review, role-based navigation |
| `mentor_delivery_week_1/03_EVALUATION_PLAN_V1.md` | Multi-layer evaluation strategy and reporting rules |
| `mentor_delivery_week_1/04_RESEARCH_BACKGROUND_AND_GAPS.md` | Research motivation, gaps, and dataset limitations |

## Week 1 Research Addenda

| File | Use it for |
| --- | --- |
| `mentor_delivery_week_1/09_DATASET_STRATEGY_AND_RESEARCH_EVALUATION.md` | Dataset roles, allowed claims, and metric mapping |
| `mentor_delivery_week_1/10_HYBRID_INPUT_NORMALIZATION_AND_EVALUATION.md` | Rule-based plus optional Gemini-assisted normalization policy |
| `mentor_delivery_week_1/11_EVALUATION_SMOKE_TEST_RESULTS.md` | Smoke test commands, outputs, and interpretation |

Some of these addenda may be created or expanded during stabilization. If a file is missing, use the closest preceding mentor delivery document as the current source.

## Product And Technical Specs

| File | Use it for |
| --- | --- |
| `1.MVP_SCOPE_MEDICAL_RECORD_SUMMARIZATIOn.md` | MVP scope |
| `2technical_prd_full.md` | Broader technical PRD |
| `3.PROJECT_BRIEF_RECORD_SUMMARIZATION_VI.md` | Project brief |
| `4.DB_SCHEMAS_MEDICAL_RECORD_SUMMARIZATION.md` | Database schema design |
| `5.SYSTEM_ARCHITECTURE.md` | System architecture |
| `6.API_SPECIFICATIONS.md` | API contract |
| `7.FHIR_DATA_MAPPING.md` | FHIR mapping |
| `8.USER_FLOW.md` | General user flow |
| `9.PROMPT_DESIGN.md` | Prompt design |
| `10.HALLUCIATION_MITIGATION.md` | Hallucination mitigation |
| `12.evaluationplan.md` | General evaluation plan |

## Delivery And Demo

| File | Use it for |
| --- | --- |
| `FINAL_DEMO_SCRIPT.md` | Final demo flow |
| `FINAL_REPORT.md` | Final report draft |
| `SUBMISSION_CHECKLIST.md` | Submission and validation checklist |
| `EVALUATION_REPORT_TEMPLATE.md` | Evaluation report skeleton |

## Building Phases

`docs/Buildingphases/` contains implementation notes and QA summaries by phase. Treat these as phase history and engineering traceability. For the current product/evaluation story, prefer the mentor delivery docs first.

## Documentation Rules

- Do not describe proxy datasets as real EHR benchmarks.
- Use "multi-layer evaluation strategy" or the exact five-layer Evidence Ladder.
- Keep mock/demo workflow validation separate from model performance evaluation.
- Keep mtsamples_clean framed as a normalization stress test, not the main supervised summarization benchmark.
- Keep MIMIC-IV-Ext-BHC and MIMIC-IV-Note as future credentialed real EHR note-level benchmarks.
