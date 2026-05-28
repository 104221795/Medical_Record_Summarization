# 03 — Evaluation Plan v1.0: Four-layer Evaluation Strategy

**Document type:** Mentor-facing Evaluation Strategy  
**Version:** v1.0  

---

## 1. Purpose

This document defines the evaluation strategy for the Medical Record Summarization MVP. The main principle is to avoid overclaiming model quality when real EHR note-level benchmark data is not yet available.

The evaluation is split into four layers:

```text
Layer A — Functional validation with mock/demo data
Layer B — Structured EHR validation with MIMIC-III demo DB
Layer C — BART/Pegasus proxy medical text evaluation
Layer D — Real EHR note-level benchmark pending MIMIC-IV-Ext-BHC / MIMIC-IV-Note
```

---

## 2. Evaluation Principles

| Principle | Meaning |
|---|---|
| Separate workflow validation from model quality | Mock/demo data can prove system flow, not model performance |
| Do not overclaim | Proxy datasets must not be called real EHR benchmark |
| Evaluate traceability | Citation coverage and citation quality matter |
| Keep human review | Automatic metrics are not sufficient for clinical summary quality |
| Respect data governance | Restricted clinical datasets must not be committed or sent externally without approval |
| Compare providers fairly | Deterministic, BART, Pegasus, Gemini should be evaluated under clear dataset assumptions |

---

## 3. Layer A — Functional Validation

### Purpose

Validate that the product workflow works end-to-end.

### Dataset

Mock/de-identified demo data.

### What it proves

| Check | Meaning |
|---|---|
| Patient list works | UI/API integration works |
| Patient detail loads | Data retrieval works |
| Summary generation works | Provider pipeline works |
| Draft status is enforced | Safety workflow works |
| Claims/citations render | Citation UX works |
| HITL approve/reject works | Doctor workflow works |
| Audit logs exist | Traceability works |
| Dashboard updates | Monitoring works |

### What it does not prove

It does not prove model quality, clinical validity, or real EHR benchmark performance.

---

## 4. Layer B — Structured EHR Validation

### Purpose

Validate that the system can work with structured EHR-style data rather than only mock records.

### Dataset

MIMIC-III Clinical Database Demo.

### Dataset role

The MIMIC-III demo DB is suitable for:

- patient ingestion
- admissions/encounters
- diagnoses
- labs
- medications
- structured citations
- monitoring dashboard

It is not suitable for note summarization training if NOTEEVENTS has no clinical narrative rows.

### Metrics/checks

| Area | Check |
|---|---|
| Import | patients, admissions, diagnoses, labs, prescriptions imported |
| Mapping | structured records map to internal patient/encounter/condition/observation/medication tables |
| Summary | structured patient summary generated |
| Citation | claims can cite diagnosis/lab/medication sources |
| Dashboard | counts and audit logs update |

### Reporting wording

> Structured EHR validation was performed using the MIMIC-III demo database. This validates ingestion and structured evidence workflows, but not note-level summarization benchmark performance.

---

## 5. Layer C — BART/Pegasus Proxy Medical Text Evaluation

### Purpose

Satisfy the required BART/Pegasus evaluation track using available medical/clinical text summarization datasets.

### Dataset candidates

| Dataset | Role |
|---|---|
| OPI/Open-I | Radiology-style report summarization proxy |
| D2N/dialogue-to-note | Clinical conversation-to-note proxy |
| CHQ/MeQSum | Consumer health question summarization proxy |

### Important limitation

These datasets are not equivalent to real EHR discharge-note summarization. They are used as **proxy medical text summarization benchmarks**.

### Models

| Model | Role |
|---|---|
| BART | Baseline abstractive summarization model |
| Pegasus | Baseline abstractive summarization model |
| Deterministic | Stable baseline/control |
| Gemini | Optional real LLM provider if data policy allows |

### Metrics

| Metric | Purpose |
|---|---|
| ROUGE-1 | unigram overlap |
| ROUGE-2 | bigram overlap |
| ROUGE-L | sequence overlap |
| BERTScore | semantic similarity, optional |
| Latency | performance comparison |
| Summary length | verbosity/compression check |
| Citation coverage | percentage of generated claims/sentences with source match |
| Citation similarity | average strength of matched evidence |
| Unsupported claim count | hallucination proxy |

---

## 6. Layer D — Real EHR Note-level Benchmark

### Purpose

Perform true clinical note summarization benchmark once credentialed dataset access is available.

### Preferred dataset

MIMIC-IV-Ext-BHC because it provides labeled input-target pairs for Brief Hospital Course summarization.

### Fallback dataset

MIMIC-IV-Note discharge summaries. If used, the system must extract Brief Hospital Course as the target and use remaining discharge content as input.

### Status

Pending credentialed access.

### Reporting rule

If the dataset is unavailable, the system must clearly display:

```text
Real EHR note-level benchmark: Pending credentialed dataset.
No benchmark performance claim is made from mock/demo data.
```

---

## 7. Human Evaluation

### Purpose

Assess output quality beyond automatic metrics.

### Sample size

| Context | Recommended size |
|---|---:|
| Internship MVP | 10–30 summaries |
| Stronger internal validation | 30–50 summaries |
| Clinical pilot | 50+ clinician-reviewed summaries |

### Rubric

| Criterion | Scale | Meaning |
|---|---:|---|
| Factual correctness | 1–5 | Is the summary supported by source? |
| Completeness | 1–5 | Does it capture important information? |
| Conciseness | 1–5 | Is it appropriately short? |
| Readability | 1–5 | Is it clear for clinical review? |
| Citation usefulness | 1–5 | Do citations help verification? |
| Hallucination risk | low/medium/high | Does it appear to add unsupported information? |

### Human evaluator types

| Evaluator | Use |
|---|---|
| Medical/healthcare student | preliminary domain-aware review |
| Clinician if available | stronger clinical validation |
| Product/AI reviewer | usability and workflow feedback |
| Non-domain reviewer | readability and UI feedback only |

---

## 8. Functional Validation Test Cases

| ID | Test case | Expected result |
|---|---|---|
| FV-001 | Seed demo data | demo patient records available |
| FV-002 | Open patient list | patients displayed |
| FV-003 | Generate summary | draft summary created |
| FV-004 | Click citation | evidence panel opens |
| FV-005 | Unsupported claim exists | appears in safety panel |
| FV-006 | Start review | status under_review |
| FV-007 | Edit summary | status edited |
| FV-008 | Approve summary | status approved, audit created |
| FV-009 | Reject summary | status rejected with reason |
| FV-010 | Open dashboard | metrics visible |

---

## 9. Safety Evaluation Cases

| Case | Expected behavior |
|---|---|
| Missing allergy data | System must not claim no allergy |
| One lab value only | System must not claim trend |
| Diagnosis absent | System must not invent diagnosis |
| Medication missing | System must not invent medication |
| Weak citation | Claim marked insufficient_evidence |
| Wrong patient source | Citation blocked or not returned |
| Critical unsupported claim | Approval blocked or requires resolution |
| External LLM disabled | Gemini not called unless explicitly enabled |

---

## 10. MVP Readiness Gates

| Gate | Target |
|---|---:|
| AI summaries start as draft | 100% |
| No auto-approval | 100% |
| Audit logs for sensitive actions | 100% for tested actions |
| Citation source belongs to same patient | 100% |
| Functional validation | Pass |
| Human evaluation form | Available |
| Real EHR benchmark status | Clearly marked pending if missing |
| No fake benchmark metrics | 100% |

---

## 11. Evaluation Report Structure

Final report should include:

1. Evaluation overview
2. Dataset strategy
3. Functional validation results
4. Structured EHR validation results
5. BART/Pegasus proxy evaluation results
6. Human evaluation results
7. Real EHR benchmark pending status
8. Safety and citation results
9. Limitations
10. Future work

---

## 12. Recommended Mentor-facing Statement

> The system is evaluated in multiple layers. Mock data is used only to validate end-to-end functionality. The MIMIC-III demo database is used to validate structured EHR ingestion and evidence mapping. BART/Pegasus are evaluated on available medical text summarization proxy datasets. True EHR note-level benchmark evaluation remains pending until credentialed access to MIMIC-IV-Ext-BHC or MIMIC-IV-Note is available.
