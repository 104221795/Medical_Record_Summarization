# 01 — PRD v1.0: Hệ thống Tóm tắt Bệnh án có Citation, HITL và Evaluation Center

**Product name:** Clinical Record Summarization Assistant  
**Document type:** Mentor-facing Product Requirements Document  
**Version:** v1.0  
**Audience:** Mentor, product reviewer, engineering reviewer, internship evaluation panel  
**Primary language:** Vietnamese with technical terms in English  

---

## 1. Executive Summary

Dự án xây dựng một **production-style MVP prototype** cho hệ thống tóm tắt bệnh án, tập trung vào việc hỗ trợ bác sĩ đọc nhanh bối cảnh bệnh nhân từ dữ liệu EHR/HIS-style. Hệ thống không được định vị như một “AI doctor”; thay vào đó, nó là một **clinical documentation assistant** tạo **draft summary**, gắn **citation** cho từng clinical claim quan trọng, flag claim thiếu bằng chứng, và yêu cầu bác sĩ review trước khi approve.

This is a production-style MVP prototype, not a production-ready medical device
or certified clinical system.

Dự án có hai track song song:

| Track | Mục tiêu | Trạng thái MVP |
|---|---|---|
| Product MVP | Tạo flow sản phẩm gần với hệ thống thật: patient list, summary workspace, citation, safety, HITL, audit, dashboard | Demo-ready |
| Research/Evaluation | Đánh giá BART/Pegasus/Gemini, citation quality, human evaluation và chuẩn bị real EHR benchmark | Một phần hoàn thành; real note benchmark pending |

Điểm nổi bật của hệ thống là không chỉ sinh summary, mà còn tạo một **evidence-aware workflow**:

```text
EHR / demo / structured data
→ ingestion
→ patient / encounter / document records
→ summarization provider
→ summary sections
→ atomic claims
→ citations
→ safety check
→ doctor review
→ audit logs
→ monitoring & evaluation
```

---

## 2. Problem Statement

### 2.1 Core problem

Trong môi trường chăm sóc sức khỏe, thông tin bệnh nhân thường phân tán qua nhiều nguồn: admission notes, discharge records, lab results, medication orders, diagnosis codes, imaging reports và structured events. Việc đọc lại toàn bộ hồ sơ bệnh án trước khi khám, bàn giao hoặc review ca bệnh có thể gây tốn thời gian, tăng cognitive load và làm tăng nguy cơ bỏ sót thông tin quan trọng.

Các mô hình AI/LLM có thể giúp tóm tắt thông tin, nhưng với dữ liệu y tế, summary sai hoặc thiếu citation có thể tạo rủi ro nghiêm trọng. Vì vậy, vấn đề sản phẩm không chỉ là “generate a summary”, mà là:

> Làm thế nào để tạo một bản tóm tắt bệnh án đủ nhanh, đủ traceable, có kiểm soát hallucination, và vẫn giữ bác sĩ là người quyết định cuối cùng?

### 2.2 Why this problem matters

| Pain point | Impact | Product response |
|---|---|---|
| Hồ sơ dài, nhiều nguồn | Bác sĩ mất thời gian đọc và tổng hợp | Patient Summary Workspace |
| AI summary có thể sai | Rủi ro hallucination / unsupported claim | Claim-level citation + safety panel |
| Nguồn dữ liệu không rõ | Bác sĩ khó tin summary | Citation Evidence Panel |
| Không có quy trình review | AI output dễ bị hiểu nhầm là official | Draft → Review → Approve/Reject workflow |
| Thiếu audit | Khó truy vết ai tạo/sửa/phê duyệt | Audit logs + review history |
| Đánh giá model khó | ROUGE chưa đủ cho y tế | multi-layer evaluation design |

---

## 3. Product Positioning

### 3.1 What the system is

Hệ thống là một **AI-assisted clinical documentation workflow**. Nó hỗ trợ:

- Tóm tắt thông tin bệnh nhân từ structured/unstructured clinical data.
- Gắn citation/evidence cho các clinical claims.
- Flag unsupported hoặc conflicting claims.
- Cho phép bác sĩ edit, approve hoặc reject summary.
- Ghi audit logs cho các hành động quan trọng.
- Hiển thị dashboard monitoring và evaluation status.

### 3.2 What the system is not

Hệ thống **không** làm các tác vụ sau:

- Không đưa ra diagnosis recommendation.
- Không đưa ra treatment recommendation.
- Không kê đơn thuốc.
- Không tự động approve discharge.
- Không chẩn đoán hình ảnh y tế.
- Không thay thế bác sĩ hoặc quy trình clinical governance.

### 3.3 Boundary statement

> The system provides draft clinical documentation support only. All generated summaries require clinician review before being used in any clinical workflow.

---

## 4. Research Background

Clinical text summarization là một hướng nghiên cứu quan trọng do khối lượng dữ liệu EHR ngày càng lớn. Các nghiên cứu gần đây cho thấy LLMs và encoder-decoder models như BART/Pegasus có tiềm năng trong summarization, nhưng clinical summarization vẫn gặp các thách thức lớn: factual correctness, hallucination, missing information, evaluation difficulty, privacy constraints và workflow integration.

Các nguồn dữ liệu như MIMIC-IV-Note cung cấp discharge summaries và radiology reports đã de-identified; MIMIC-IV-Ext-BHC cung cấp dataset chuyên cho Brief Hospital Course summarization. Tuy nhiên, các dataset này thường yêu cầu credentialed access, làm cho MVP cần tách rõ functional validation, proxy evaluation và real benchmark evaluation.

---

## 5. Research Gaps Addressed

| Research/Product gap | Explanation | How this MVP addresses it |
|---|---|---|
| Gap 1 — Summary without evidence | Nhiều hệ thống chỉ sinh text summary, không gắn nguồn | Citation-based claim mapping |
| Gap 2 — Automatic metrics insufficient | ROUGE/BERTScore không đủ đánh giá factuality y tế | Human evaluation + citation metrics |
| Gap 3 — Weak clinical workflow integration | Nhiều prototype chỉ là notebook/model output | Doctor UI + HITL workflow |
| Gap 4 — Hallucination risk | LLM có thể thêm thông tin không có trong record | Unsupported claim detection + safety panel |
| Gap 5 — No auditability | Khó truy vết ai tạo/approve/sửa summary | Audit log + review history |
| Gap 6 — Data access constraint | Real EHR note data bị restricted | multi-layer evaluation with pending real benchmark |
| Gap 7 — Model comparison thiếu workflow | Model evaluation thường tách khỏi product UI | Provider selection + evaluation center |

---

## 6. Target Users and Personas

### Persona 1 — Doctor / Clinician

**Goal:** Nắm nhanh tình trạng bệnh nhân trước khám, bàn giao hoặc review ca bệnh.  
**Pain:** Hồ sơ dài, nhiều nguồn, mất thời gian đọc.  
**Needs:** Summary ngắn gọn, có citation, có warning nếu claim yếu.  
**Key actions:** Generate summary, click citation, edit, approve, reject.

### Persona 2 — Nurse

**Goal:** Xem thông tin đã được bác sĩ approve hoặc các điểm cần chú ý khi bàn giao.  
**Pain:** Không nên có quyền approve clinical summary.  
**Needs:** View-only access, approved summaries, limited citations.

### Persona 3 — Clinical Admin / Quality Reviewer

**Goal:** Theo dõi chất lượng summary, rejection reasons, unsupported claims và audit trends.  
**Needs:** Dashboard metrics, safety overview, review statistics.

### Persona 4 — IT Admin

**Goal:** Quản lý ingestion, system health, provider config, demo seed data.  
**Needs:** Data import status, provider readiness, logs, system configuration.

### Persona 5 — Auditor

**Goal:** Xem audit trail và review history.  
**Needs:** Read-only logs, filtering by user/action/resource.

### Persona 6 — Evaluation Reviewer

**Goal:** Chấm điểm generated summaries theo factual correctness, completeness, readability và citation usefulness.  
**Needs:** Human evaluation form and model comparison output.

---

## 7. MVP Scope

### 7.1 In scope

| Module | MVP requirement |
|---|---|
| Data ingestion | Mock/FHIR-like import, structured EHR import, demo seed |
| Patient workflow | Patient list, patient detail, documents/chunks |
| Summary generation | deterministic, Gemini, BART/Pegasus baseline support |
| Citation | Claim-to-source citation, citation source viewer |
| Safety | Unsupported claim flag, conflict/missing data rules |
| HITL | start review, edit, approve, reject, review history |
| Role-based UI | doctor, nurse, clinical_admin, it_admin, auditor, evaluator |
| Monitoring | metrics dashboard, audit logs |
| Evaluation center | functional validation, structured EHR validation, BART/Pegasus proxy eval, real benchmark pending, human eval |
| Documentation | PRD, User Flow, Evaluation Plan, Survey Plan, Research Gaps |

### 7.1.1 Current implementation status clarity

| Component | Status |
|---|---|
| FastAPI backend | Implemented |
| Demo seed data | Implemented |
| Unified Demo Console | Implemented |
| Citation-grounded summary flow | Implemented / demo-ready |
| HITL review workflow | Implemented |
| Gemini provider integration | Implemented, requires API key and explicit external-provider flags |
| BART/Pegasus proxy evaluation | Partially implemented / prepared for optional local model execution |
| MIMIC-IV real benchmark | Planned / pending credentialed access |
| Human evaluation with clinicians | Planned |

### 7.2 Out of scope

| Out-of-scope item | Reason |
|---|---|
| Production SSO/OAuth | Future hardening |
| Real-time HIS/EMR integration | Requires hospital sandbox |
| EMR write-back | Requires governance and clinical approval |
| Medical image diagnosis | Outside summarization scope |
| Treatment recommendation | Regulatory/safety risk |
| Automated clinical approval | Must remain clinician-controlled |

---

## 8. Data Strategy

### 8.1 Current data layers

| Data layer | Dataset/source | Purpose | Status |
|---|---|---|---|
| Functional demo | Mock/de-identified data | UI/API workflow validation | Implemented |
| Structured EHR validation | MIMIC-III demo structured DB | Patient/encounter/lab/diagnosis/medication workflow | Partially implemented |
| Proxy model evaluation | OPI/D2N/CHQ or available medical summarization data | BART/Pegasus evaluation requirement | Partially implemented / proxy only |
| Real note benchmark | MIMIC-IV-Ext-BHC / MIMIC-IV-Note | True EHR note-level summarization benchmark | Planned / pending credentialed access |
| Human evaluation | Demo summaries and reviewer scoring | Human quality and usability assessment | Planned |

### 8.2 Important dataset boundary

MIMIC-III demo structured DB is useful for product workflow validation, but not enough for BART/Pegasus note summarization because the demo version has no clinical note rows in NOTEEVENTS. It should be used for structured EHR validation, not as a note summarization benchmark.

---

## 9. AI and Model Strategy

### 9.1 Provider types

| Provider | Purpose | Notes |
|---|---|---|
| Deterministic | Stable baseline and test default | No external dependency |
| BART | Summarization baseline | Proxy/benchmark evaluation |
| Pegasus | Summarization baseline | Comparison with BART |
| Gemini | Real LLM provider | Disabled by default; PHI controls required |

### 9.2 Unified provider principle

All providers should output into the same normalized workflow:

```text
provider output
→ sections
→ claims
→ citations
→ safety flags
→ draft summary
→ doctor review
```

### 9.3 External LLM policy

Gemini should be disabled by default for restricted or identifiable clinical data unless compliant data governance is confirmed. For demo, use mock/de-identified data.

---

## 10. Functional Requirements

### FR-01 — Patient List and Detail

The system shall allow authorized users to view a list of patients and open patient detail records.

### FR-02 — Clinical Data Import

The system shall support importing mock/FHIR-like clinical data and structured EHR demo data.

### FR-03 — Summary Generation

The system shall allow doctors to generate a draft patient summary using a selected provider.

### FR-04 — Citation-based Summary

The system shall link important clinical claims to supporting evidence from source documents, chunks, or structured records.

### FR-05 — Safety Panel

The system shall show citation coverage, unsupported claims, missing information, weak citations, and conflicts where available.

### FR-06 — HITL Review

The system shall allow doctors to start review, edit, approve, or reject summaries.

### FR-07 — Audit Logging

The system shall log sensitive actions including generation, citation view, edit, approve, reject, import, and metrics access.

### FR-08 — Admin Monitoring

The system shall provide dashboard metrics on summary volume, approval/rejection, citation coverage, safety flags, and audit activity.

### FR-09 — Human Evaluation

The system shall allow evaluation reviewers to score generated summaries on factual correctness, completeness, conciseness, readability, citation usefulness, and hallucination risk.

### FR-10 — Evaluation Center

The system shall provide a control center showing golden path readiness, provider readiness, functional validation, benchmark status, human evaluation and demo checklist.

---

## 11. Non-functional Requirements

| Category | Requirement |
|---|---|
| Safety | No autonomous clinical decision-making |
| Traceability | Each supported clinical claim should be traceable to evidence |
| Security | Role-based access and audit logs |
| Privacy | No raw PHI exposure in logs; external LLM disabled by default |
| Usability | Doctor can verify evidence with one click |
| Maintainability | Provider abstraction and modular service layer |
| Evaluation | Functional, structured EHR, proxy model and human evaluation separated |
| Reliability | Clear failure handling for model/provider errors |

---

## 12. User Stories and Acceptance Criteria

### US-001 — Generate patient summary

As a doctor, I want to generate a structured patient summary so that I can review the patient's context faster.

**Acceptance criteria**

```gherkin
Given a patient has available clinical data
When the doctor clicks Generate Summary
Then the system creates a draft summary
And summary sections are displayed
And audit log generate_summary is created
```

### US-002 — Verify claim citation

As a doctor, I want to click a citation next to a claim so that I can verify the source evidence.

**Acceptance criteria**

```gherkin
Given a summary claim has a citation
When the doctor clicks the citation badge
Then the source evidence panel opens
And the source text or structured record is displayed
And audit log view_citation is created
```

### US-003 — Flag unsupported claim

As a doctor, I want unsupported claims to be flagged so that I do not rely on unsupported information.

**Acceptance criteria**

```gherkin
Given a generated claim has no valid source
When safety check runs
Then the claim is marked unsupported or insufficient_evidence
And it appears in the safety panel or Needs Clinician Review
```

### US-004 — Approve reviewed summary

As a doctor, I want to approve a summary only after review so that it can be marked as clinician-reviewed.

**Acceptance criteria**

```gherkin
Given a summary is draft, under_review or edited
When the doctor approves it
Then status becomes approved
And approved_by and approved_at are saved
And approve_summary audit log is created
```

### US-005 — Submit human evaluation

As an evaluation reviewer, I want to score generated summaries so that model outputs can be compared beyond automatic metrics.

**Acceptance criteria**

```gherkin
Given a generated summary exists
When the reviewer submits scores from 1 to 5
Then the evaluation is stored
And aggregate human evaluation metrics update
```

---

## 13. Role and Permission Matrix

| Feature | Doctor | Nurse | Clinical Admin | IT Admin | Auditor | AI Safety Reviewer | Evaluation Reviewer |
|---|---:|---:|---:|---:|---:|---:|---:|
| View patient list | Yes | Limited | Limited | No | Read-only | Limited | No |
| Generate summary | Yes | No | No | No | No | No | No |
| View citation | Yes | Limited | Yes | No | Read-only | Yes | Yes |
| Edit summary | Yes | No | No | No | No | No | No |
| Approve/reject summary | Yes | No | No | No | No | No | No |
| View dashboard | Limited | No | Yes | Yes | Read-only | Yes | Limited |
| View audit logs | Limited | No | Yes | Yes | Yes | Read-only | No |
| Import data | No | No | No | Yes | No | No | No |
| Submit human evaluation | Optional | Optional | Optional | No | No | Optional | Yes |

---

## 14. Evaluation Strategy

The evaluation design is a multi-layer evaluation design to avoid overclaiming
model quality.

| Layer | Dataset | Purpose | Status |
|---|---|---|---|
| A — Functional validation | Mock/demo data | Prove end-to-end system workflow | Implemented |
| B — Structured EHR validation | MIMIC-III demo DB | Validate structured EHR ingestion, citation and dashboard workflow | Partially implemented |
| C — BART/Pegasus proxy evaluation | OPI/D2N/CHQ or equivalent medical text datasets | Satisfy model comparison requirement | Partially implemented / proxy only |
| D — Real EHR note benchmark | MIMIC-IV-Ext-BHC / MIMIC-IV-Note | True note-level EHR benchmark | Planned / pending credentialed access |
| E — Human evaluation | Demo or governed de-identified summaries | Score factuality, completeness, readability and citation usefulness | Planned |

### Success metrics

| Area | Metric |
|---|---|
| Functional validation | E2E workflow pass/fail |
| Summary quality | ROUGE/BERTScore where reference exists |
| Citation | citation coverage, citation similarity, missing citation count |
| Safety | unsupported claim count, conflict count, critical hallucination proxy |
| HITL | approval rate, rejection rate, edit distance |
| Human evaluation | factual correctness, completeness, readability, citation usefulness |

---

## 15. Risks and Mitigation

| Risk | Severity | Mitigation |
|---|---:|---|
| Model hallucinates clinical fact | High | Citation-required claims, unsupported flag, doctor review |
| Citation is weak or wrong | High | Citation confidence, source viewer, human review |
| User over-trusts AI output | High | Draft status, safety label, approval workflow |
| Real EHR benchmark unavailable | Medium | Separate evaluation layers, do not overclaim |
| External LLM data privacy risk | High | Disabled by default, de-identified demo data only unless approved |
| Role misuse | Medium | Role-based UI + backend permission checks |
| Metrics misinterpreted | Medium | Separate functional/proxy/real benchmark claims |

---

## 16. Roadmap

| Phase | Outcome |
|---|---|
| Phase 1 | Database and persistence foundation |
| Phase 2 | API and ingestion alignment |
| Phase 3 | Deterministic summary + claims + citations |
| Phase 4 | Doctor Golden Path UI |
| Phase 5 | HITL review workflow |
| Phase 6 | Audit, metrics and dashboard |
| Phase 7 | BART/Pegasus/Gemini provider integration |
| Phase 8 | Evaluation center and multi-layer validation |
| Phase 9 | Final demo hardening and report |
| Future | Real EHR benchmark and clinical validation |

---

## 17. Future Work

1. Acquire credentialed MIMIC-IV-Ext-BHC/MIMIC-IV-Note access for true EHR note benchmark.
2. Improve claim-level factuality verification.
3. Add stronger medication/allergy/lab validation.
4. Implement SMART on FHIR sandbox integration.
5. Replace mock RBAC with production SSO/OAuth.
6. Add prompt/model regression testing before release.
7. Run human evaluation with clinicians or medical students.

---


## References

- Aali, A. et al. (2025) *MIMIC-IV-Ext-BHC: Labeled Clinical Notes Dataset for Hospital Course Summarization*. PhysioNet. Available at: https://physionet.org/content/labelled-notes-hospital-course/
- Bednarczyk, L. et al. (2025) *Scientific Evidence for Clinical Text Summarization Using Large Language Models*. Journal of Medical Internet Research. Available at: https://www.jmir.org/2025/1/e68998/
- Croxford, E. et al. (2025) *Evaluating clinical AI summaries with large language models*. npj Digital Medicine. Available at: https://www.nature.com/articles/s41746-025-02005-2
- FDA (2026) *Clinical Decision Support Software: Guidance for Industry and Food and Drug Administration Staff*. Available at: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
- HL7 (2024) *SMART App Launch Implementation Guide*. Available at: https://build.fhir.org/ig/HL7/smart-app-launch/
- Johnson, A. et al. (2024) *MIMIC-IV-Note: Deidentified free-text clinical notes*. PhysioNet. Available at: https://physionet.org/content/mimic-iv-note/
- NIST (2024) *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. Available at: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
- Tang, L. et al. (2023) *Evaluating large language models on medical evidence summarization*. npj Digital Medicine. Available at: https://pmc.ncbi.nlm.nih.gov/articles/PMC10449915/
- WHO (2021) *Ethics and governance of artificial intelligence for health*. Available at: https://www.who.int/publications/i/item/9789240029200
