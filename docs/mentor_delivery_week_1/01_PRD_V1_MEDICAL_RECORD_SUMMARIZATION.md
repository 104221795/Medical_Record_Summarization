# 01 — PRD v1.1: Hệ thống Tóm tắt Bệnh án có Citation, HITL và Evaluation Center

**Tên sản phẩm:** Clinical Record Summarization Assistant
**Loại tài liệu:** Product Requirements Document dành cho mentor
**Phiên bản:** v1.1
**Đối tượng đọc:** Mentor, product reviewer, engineering reviewer, hội đồng đánh giá thực tập
**Ngôn ngữ chính:** Tiếng Việt, giữ một số thuật ngữ kỹ thuật tiếng Anh khi cần thiết

---

## 1. Tóm tắt điều hành

Dự án xây dựng một **production-style MVP prototype** cho hệ thống **Medical Record Summarization Assistant** — một trợ lý tài liệu lâm sàng có khả năng tạo bản tóm tắt nháp từ dữ liệu bệnh án, gắn citation cho các clinical claims quan trọng, flag các claim thiếu bằng chứng, và yêu cầu bác sĩ review trước khi approve.

Luận điểm cốt lõi của dự án là: **tóm tắt bệnh án không chỉ là bài toán sinh văn bản**. Trong bối cảnh y tế, một bản tóm tắt chỉ thực sự hữu ích khi nó có thể **truy vết nguồn, được kiểm chứng, được review, được audit, và bị giới hạn rõ trong phạm vi hỗ trợ tài liệu lâm sàng**. Nếu một summary không chỉ ra được nguồn bằng chứng, hoặc trình bày thông tin chưa được kiểm chứng như một sự thật chắc chắn, hệ thống có thể làm tăng rủi ro thay vì giảm cognitive load cho bác sĩ.

Vì vậy, MVP này không được thiết kế như một “AI doctor”. Hệ thống không đưa ra chẩn đoán, không khuyến nghị điều trị, không kê đơn, và không tự động phê duyệt bất kỳ quyết định lâm sàng nào. Thay vào đó, hệ thống được định vị là một **citation-grounded clinical documentation assistant**: AI chỉ tạo **draft summary**, còn bác sĩ vẫn giữ vai trò kiểm tra, chỉnh sửa, approve hoặc reject.

Dự án có hai track song song:

| Track                       | Mục tiêu                                                                                                                                                         | Trạng thái Week 1                                                                     |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Product / Workflow Track    | Thiết kế workflow tài liệu lâm sàng gồm patient context, source documents, draft summary, citation, unsupported claim flag, HITL review, audit log và monitoring | Hoàn thành PRD + User Flow; đã chuẩn bị hướng demo workflow ban đầu                   |
| Research / Evaluation Track | Thiết kế chiến lược đánh giá nhiều tầng, tách biệt functional validation, open benchmark evaluation, future real EHR benchmark và human evaluation               | Đã xác định hướng đánh giá; phần chạy benchmark đầy đủ để triển khai ở bước tiếp theo |

Điểm nổi bật của hệ thống là không dừng ở việc sinh summary, mà xây dựng một **evidence-aware documentation lifecycle**:

```text
patient / encounter / document data
→ source-aware ingestion
→ section-aware chunking
→ draft summary generation
→ claim extraction
→ citation grounding
→ unsupported claim flagging
→ doctor review
→ edit / approve / reject
→ audit log
→ evaluation and monitoring
```

Đây là **production-style MVP prototype**, chưa phải hệ thống y tế production-ready, chưa phải medical device được chứng nhận, và chưa phải hệ thống đã được clinical validation.

---

## 2. Phát biểu vấn đề

### 2.1 Vấn đề cốt lõi

Hồ sơ bệnh án thường dài, phân tán và khó review trong điều kiện thời gian hạn chế. Thông tin của một bệnh nhân có thể nằm rải rác trong admission notes, progress notes, discharge records, medication orders, diagnosis codes, lab results, imaging reports và các structured events khác. Sự phân tán này làm tăng cognitive load cho bác sĩ và làm tăng nguy cơ bỏ sót bối cảnh quan trọng khi khám, bàn giao hoặc review ca bệnh.

Tuy nhiên, trong y tế, vấn đề không chỉ là “cần một bản tóm tắt”. Vấn đề sâu hơn là: **clinical summary phải đáng tin cậy**. Một bản summary do AI sinh ra có thể rất mạch lạc, nhưng vẫn có thể bỏ sót thông tin quan trọng, diễn giải quá mức, thêm claim không có trong nguồn, hoặc làm người dùng tin nhầm rằng thông tin đó đã được kiểm chứng.

Vì vậy, bài toán sản phẩm được đặt ra là:

> Làm thế nào để hệ thống giúp bác sĩ review bối cảnh bệnh nhân nhanh hơn, nhưng vẫn giữ được khả năng truy vết bằng chứng, khả năng kiểm chứng, và trách nhiệm lâm sàng của con người?

MVP giải quyết bài toán này bằng cách thiết kế một workflow có kiểm soát: summary do AI tạo ra luôn ở trạng thái draft; các claim quan trọng nên được liên kết với nguồn bằng chứng; claim thiếu bằng chứng phải được hiển thị rõ; và bác sĩ vẫn là người review, chỉnh sửa, approve hoặc reject cuối cùng.

### 2.2 Vì sao vấn đề này quan trọng?

| Pain point                                           | Rủi ro lâm sàng / sản phẩm                              | Cách MVP phản hồi                        |
| ---------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------- |
| Hồ sơ dài và phân tán                                | Bác sĩ mất thời gian tái dựng bối cảnh bệnh nhân        | Patient and Encounter Workspace          |
| AI output đọc có vẻ đúng nhưng có thể sai            | Claim thiếu bằng chứng có thể bị tin quá mức            | Claim-level support status               |
| Nguồn bằng chứng không rõ                            | Bác sĩ khó kiểm chứng generated statement               | Citation Evidence Panel                  |
| AI output có thể bị hiểu nhầm là kết luận chính thức | Tăng rủi ro over-trust hoặc automation bias             | Draft → Review → Approve/Reject workflow |
| Không có review trail                                | Khó biết ai tạo, sửa, approve hoặc reject summary       | Audit log và review history              |
| Đánh giá model khó                                   | ROUGE/BERTScore không đủ chứng minh clinical usefulness | Multi-layer evaluation strategy          |

---

## 3. Định vị sản phẩm

### 3.1 Bản chất sản phẩm

Hệ thống là một **AI-assisted clinical documentation workflow**. Nó hỗ trợ bác sĩ tạo và review draft summaries từ dữ liệu lâm sàng đã có, đồng thời giữ khả năng truy vết về nguồn bằng chứng.

Nguyên tắc thiết kế trung tâm là:

> **Trust through verification — tạo niềm tin thông qua khả năng kiểm chứng.**

Mỗi claim quan trọng trong summary nên có khả năng được kiểm tra ngược lại bằng nguồn dữ liệu nếu có thể. Nếu hệ thống không đủ bằng chứng để hỗ trợ một claim, nó phải làm lộ rõ sự không chắc chắn thay vì che giấu trong một câu văn nghe có vẻ chắc chắn.

### 3.2 Hệ thống là gì và không phải là gì

| Hệ thống không phải                     | Hệ thống là                                                            |
| --------------------------------------- | ---------------------------------------------------------------------- |
| Công cụ chẩn đoán                       | Trợ lý tài liệu lâm sàng                                               |
| Công cụ khuyến nghị điều trị            | Công cụ hỗ trợ tạo draft summary                                       |
| Hệ thống ra quyết định lâm sàng tự động | Workflow có bác sĩ review                                              |
| Chatbot y tế chung chung                | Workflow có cấu trúc: patient → document → summary → citation → review |
| Medical device production-ready         | Production-style MVP prototype                                         |
| Công cụ thay thế bác sĩ                 | Công cụ hỗ trợ bác sĩ review và kiểm chứng thông tin                   |

### 3.3 Ranh giới sản phẩm

Hệ thống chỉ cung cấp **hỗ trợ tài liệu lâm sàng ở dạng draft**. Hệ thống không chẩn đoán, không khuyến nghị điều trị, không kê đơn, và không tự động phê duyệt hành động lâm sàng. Mọi summary do AI tạo ra đều cần được bác sĩ review trước khi sử dụng trong bất kỳ workflow lâm sàng nào.

---

## 4. Nền tảng nghiên cứu

Clinical text summarization là một hướng nghiên cứu quan trọng vì các hệ thống EHR/HIS-style thường chứa khối lượng lớn dữ liệu bệnh nhân, bao gồm cả dữ liệu có cấu trúc và dữ liệu phi cấu trúc. Bối cảnh lâm sàng của một bệnh nhân có thể nằm trong nhiều nguồn khác nhau: chẩn đoán, đơn thuốc, kết quả xét nghiệm, imaging reports, discharge notes, progress notes và các narrative records khác.

Tuy nhiên, medical summarization khác với general text summarization ở bốn điểm quan trọng:

1. **Generation gap** — hệ thống có tạo được summary ngắn gọn, dễ đọc và đúng trọng tâm không?
2. **Grounding gap** — các claim quan trọng trong summary có truy ngược được về nguồn bằng chứng không?
3. **Workflow gap** — AI output có đi qua review, edit, approve/reject và audit không?
4. **Evaluation gap** — dự án có phân biệt được functional validation, open benchmark evaluation, real EHR benchmark và human evaluation không?

Nhiều prototype summarization thường dừng ở:

```text
input note → model output → ROUGE score
```

Dự án này có cách tiếp cận rộng hơn. Nó coi summarization là một **documentation lifecycle problem**: summary chỉ là một phần của một workflow lớn hơn gồm citation, safety flags, doctor review, auditability và multi-layer evaluation.

Các mô hình encoder-decoder như BART/Pegasus có giá trị như summarization baselines. Các LLM như Gemini có thể hỗ trợ generation hoặc controlled input normalization. Các BERT-style models có thể hỗ trợ semantic evaluation, ví dụ BERTScore hoặc claim-source similarity. Tuy nhiên, không mô hình nào tự nó chứng minh được clinical readiness. Trong dự án này, model output luôn phải được hiểu trong mối quan hệ với source grounding, human review và ranh giới đánh giá.

---

## 5. Research Gaps mà MVP hướng tới

| Research/Product gap                           | Vì sao quan trọng                                               | Cách MVP xử lý                                                 |
| ---------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------- |
| Sinh summary nhưng không kiểm chứng được       | Summary đọc mượt vẫn có thể thiếu bằng chứng hoặc gây hiểu nhầm | Citation-grounded claim workflow                               |
| Metric tự động không đủ cho y tế               | ROUGE/BERTScore không đo đầy đủ factuality và safety            | Kết hợp citation metrics + human evaluation                    |
| Prototype không gắn với workflow thực tế       | Model-only demo không cho thấy bác sĩ review output thế nào     | Doctor Workspace + HITL Review                                 |
| Hallucination bị che giấu trong văn bản tự tin | Claim thiếu bằng chứng có thể bị người dùng tin nhầm            | Unsupported claim flags + Safety Panel                         |
| Output không có accountability                 | Không rõ ai tạo, sửa, approve hoặc reject summary               | Audit logs + review history                                    |
| Rủi ro overclaim dataset                       | Open dataset dễ bị hiểu nhầm là real EHR validation             | Evidence ladder + allowed-claim boundaries                     |
| Rủi ro privacy khi dùng external LLM           | Dữ liệu lâm sàng có thể yêu cầu governance nghiêm ngặt          | External provider disabled by default trừ khi được cấu hình rõ |

---

## 6. Người dùng mục tiêu và Jobs-to-be-Done

### 6.1 Bảng người dùng chính

| User                | Job-to-be-done                                                                        |
| ------------------- | ------------------------------------------------------------------------------------- |
| Doctor / Clinician  | Review source-backed draft summaries and approve only after verification              |
| Nurse               | Xem approved summary hoặc limited clinical context, không approve AI summary          |
| Clinical Admin      | Theo dõi safety signals, review activity, quality metrics và rejection trends         |
| IT Admin            | Quản lý ingestion, provider readiness, system health và demo configuration            |
| Auditor             | Truy vết ai đã generate, view, edit, approve hoặc reject summary                      |
| AI Safety Reviewer  | Kiểm tra unsupported, conflicting hoặc high-risk claims                               |
| Evaluation Reviewer | Chấm factuality, completeness, readability, citation usefulness và hallucination risk |

### 6.2 Persona chi tiết

#### Persona 1 — Doctor / Clinician

**Goal:** Nắm nhanh tình trạng bệnh nhân trước khám, bàn giao hoặc review ca bệnh.
**Pain:** Hồ sơ dài, nhiều nguồn, mất thời gian đọc.
**Needs:** Summary ngắn gọn, có citation, có warning nếu claim yếu.
**Key actions:** Generate summary, click citation, edit, approve, reject.

#### Persona 2 — Nurse

**Goal:** Xem thông tin đã được bác sĩ approve hoặc các điểm cần chú ý khi bàn giao.
**Pain:** Không nên có quyền approve clinical summary.
**Needs:** View-only access, approved summaries, limited citations.

#### Persona 3 — Clinical Admin / Quality Reviewer

**Goal:** Theo dõi chất lượng summary, rejection reasons, unsupported claims và audit trends.
**Needs:** Dashboard metrics, safety overview, review statistics.

#### Persona 4 — IT Admin

**Goal:** Quản lý ingestion, system health, provider config, demo seed data.
**Needs:** Data import status, provider readiness, logs, system configuration.

#### Persona 5 — Auditor

**Goal:** Xem audit trail và review history.
**Needs:** Read-only logs, filtering by user/action/resource.

#### Persona 6 — Evaluation Reviewer

**Goal:** Chấm điểm generated summaries theo factual correctness, completeness, readability và citation usefulness.
**Needs:** Human evaluation form and model comparison output.

---

## 7. Phạm vi MVP

### 7.1 In scope

| Module             | MVP requirement                                                                                             |
| ------------------ | ----------------------------------------------------------------------------------------------------------- |
| Data ingestion     | Mock/FHIR-like import, structured EHR import, demo seed                                                     |
| Patient workflow   | Patient list, patient detail, documents/chunks                                                              |
| Summary generation | Deterministic, Gemini, BART/Pegasus baseline support                                                        |
| Citation           | Claim-to-source citation, citation source viewer                                                            |
| Safety             | Unsupported claim flag, conflict/missing data rules                                                         |
| HITL               | Start review, edit, approve, reject, review history                                                         |
| Role-based UI      | doctor, nurse, clinical_admin, it_admin, auditor, ai_safety_reviewer, evaluation_reviewer                   |
| Monitoring         | Metrics dashboard, audit logs                                                                               |
| Evaluation center  | Functional validation, structured EHR validation, open benchmark status, real benchmark pending, human eval |
| Documentation      | PRD, User Flow, Evaluation Plan, Survey Plan, Research Gaps                                                 |

### 7.2 Trạng thái triển khai hiện tại

| Component                        | Status                                                                   |
| -------------------------------- | ------------------------------------------------------------------------ |
| PRD và User Flow                 | Completed for Week 1                                                     |
| FastAPI backend                  | Implemented                                                              |
| Demo seed data                   | Implemented                                                              |
| Unified Demo Console             | Implemented as early workflow feasibility prototype                      |
| Citation-grounded summary flow   | Implemented / demo-ready                                                 |
| HITL review workflow             | Implemented                                                              |
| Gemini provider integration      | Implemented, requires API key and explicit external-provider flags       |
| BART/Pegasus evaluation track    | Partially implemented / prepared for optional local model execution      |
| MultiClinSum benchmark pipeline  | Planned / partially prepared depending local data and model availability |
| MIMIC-IV real benchmark          | Future / pending credentialed access                                     |
| Human evaluation with clinicians | Designed / planned                                                       |

### 7.3 Out of scope

| Out-of-scope item                     | Reason                                                               |
| ------------------------------------- | -------------------------------------------------------------------- |
| Diagnosis recommendation              | Vượt quá phạm vi an toàn và regulatory boundary của MVP              |
| Treatment recommendation              | Clinical decision-making phải do clinician kiểm soát                 |
| Automated clinical approval           | AI output không được trở thành official khi chưa có clinician review |
| Production SSO/OAuth                  | Future hardening                                                     |
| Real-time HIS/EMR integration         | Cần hospital sandbox và governance                                   |
| EMR write-back                        | Cần clinical approval và institutional governance                    |
| Medical image diagnosis               | Ngoài phạm vi summarization                                          |
| Certified medical device readiness    | Vượt quá phạm vi MVP và internship                                   |
| Real EHR benchmark claim trong Week 1 | Cần credentialed access tới real EHR note-level datasets             |

---

## 8. Chiến lược dữ liệu

### 8.1 Luận điểm về dataset strategy

Dự án cố ý tách các loại dataset theo loại bằng chứng mà chúng có thể cung cấp. Một rủi ro phổ biến trong các prototype medical AI là sử dụng một dataset thuận tiện rồi overclaim ý nghĩa của nó. MVP này tránh điều đó bằng cách tách rõ:

```text
functional workflow validation
structured EHR mapping validation
open clinical summarization benchmark
messy input normalization stress test
future real EHR note-level benchmark
human evaluation
```

Cách tách này giúp mỗi dataset chỉ được dùng cho loại claim mà nó thực sự có thể hỗ trợ.

### 8.2 Bảng vai trò dataset

| Dataset / source                 | Vai trò trong dự án                           | Có thể validate                                                                                      | Không thể validate                                                                   | Trạng thái                     |
| -------------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------ |
| Mock / de-identified demo data   | Functional workflow validation                | UI/API/DB flow, summary lifecycle, HITL review, audit logging                                        | Model quality hoặc clinical performance thật                                         | Implemented                    |
| MIMIC-III demo structured DB     | Structured EHR-style validation               | Patient, admission, diagnosis, lab, medication mapping                                               | Note-level summarization performance, vì demo DB không có clinical note rows hữu ích | Partial / optional             |
| MultiClinSum                     | Primary open clinical summarization benchmark | Pegasus/BART summarization trên clinical case report/reference summary pairs bằng ROUGE và BERTScore | Real hospital EHR note performance                                                   | Planned / next evaluation step |
| MTS-Dialog                       | Auxiliary dialogue-to-note proxy evaluation   | Doctor-patient dialogue to clinical note section generation                                          | Full medical record summarization hoặc real EHR benchmark performance                | Optional auxiliary             |
| ACI-BENCH                        | Optional full-visit dialogue-to-note proxy    | Full visit dialogue to clinical note behavior                                                        | Real EHR discharge note summarization                                                | Optional auxiliary             |
| BIOMEDNLP/mtsamples_clean        | Messy input normalization stress test         | Robustness của section detection, normalization, chunking và Gemini-assisted preprocessing           | Supervised summarization benchmark nếu không có reliable reference summaries         | Planned                        |
| MIMIC-IV-Ext-BHC / MIMIC-IV-Note | Future real EHR note-level benchmark          | Real EHR note summarization, đặc biệt hospital course summarization                                  | Chưa dùng được trong Week 1 do credentialed access                                   | Future / pending access        |
| Human evaluation samples         | Clinical usefulness and safety perception     | Factual correctness, completeness, readability, citation usefulness, hallucination risk              | Large-scale clinical validation nếu thiếu expert reviewers và governed data          | Planned                        |

### 8.3 Ranh giới quan trọng của dataset

Mock hoặc de-identified demo data có thể validate rằng workflow của hệ thống chạy end-to-end, nhưng không thể chứng minh chất lượng clinical summarization.

MultiClinSum phù hợp làm primary open clinical summarization benchmark vì nó có cặp clinical document/reference summary để đánh giá Pegasus/BART. Tuy nhiên, không nên gọi MultiClinSum là real EHR benchmark vì clinical case reports không tương đương với raw hospital EHR notes hoặc discharge summaries.

MTS-Dialog hữu ích cho dialogue-to-note behavior, nhưng là auxiliary proxy dataset chứ không thay thế main summarization benchmark.

BIOMEDNLP/mtsamples_clean nên được xem là messy input normalization stress test. Dataset này giúp kiểm tra hệ thống có xử lý được medical transcription có format không đồng nhất hay không, nhưng không nên xem là supervised summarization benchmark chính nếu không có paired reference summaries đáng tin cậy.

MIMIC-IV-Ext-BHC và MIMIC-IV-Note là hướng phù hợp hơn cho real EHR note-level benchmarking trong tương lai, sau khi có credentialed access.

---

## 9. Chiến lược AI và mô hình

### 9.1 Vai trò của từng provider/model

| Provider / model           | Vai trò                                                                | Ghi chú                                       |
| -------------------------- | ---------------------------------------------------------------------- | --------------------------------------------- |
| Deterministic summarizer   | Stable workflow baseline                                               | Hữu ích để test không cần external dependency |
| BART                       | Abstractive summarization baseline                                     | Dùng cho Layer C open benchmark evaluation    |
| Pegasus                    | Abstractive summarization baseline                                     | Dùng để so sánh với BART trong Layer C        |
| BERT / BioBERT / BERTScore | Semantic evaluation / similarity support                               | Không phải main abstractive summary generator |
| Gemini                     | Real LLM provider và controlled difficult-case normalization assistant | Disabled by default nếu chưa explicit config  |
| Human reviewer             | Final review and usefulness/safety assessment                          | Cần cho Layer E                               |

### 9.2 Nguyên tắc provider thống nhất

Mọi generation provider phải đi qua cùng một workflow chuẩn hóa:

```text
provider output
→ sections
→ claims
→ citations
→ safety flags
→ draft summary
→ doctor review
```

Thiết kế này giúp UI và safety workflow không bị phụ thuộc vào một model cụ thể.

### 9.3 Chính sách external LLM

Gemini nên bị disabled by default đối với dữ liệu lâm sàng restricted hoặc identifiable, trừ khi data governance đã được xác nhận. Trong demo và MVP validation, hệ thống nên dùng mock, synthetic hoặc de-identified data.

Nếu Gemini được dùng cho input normalization, vai trò của nó phải được kiểm soát:

```text
messy raw document
→ classify / normalize / extract source-backed sections
→ validate JSON schema
→ preserve raw text as source of truth
```

Gemini không được tự thêm clinical facts, không được chẩn đoán, và không được khuyến nghị điều trị.

---

## 10. Functional Requirements

### FR-01 — Patient List and Detail

Hệ thống cho phép người dùng có quyền xem danh sách bệnh nhân và mở patient detail records.

### FR-02 — Clinical Data Import

Hệ thống hỗ trợ import mock/FHIR-like clinical data và structured EHR-style demo data.

### FR-03 — Summary Generation

Hệ thống cho phép doctor tạo draft patient summary bằng provider được chọn.

### FR-04 — Citation-based Summary

Hệ thống liên kết các clinical claims quan trọng với supporting evidence từ source documents, chunks hoặc structured records nếu có thể.

### FR-05 — Safety Panel

Hệ thống hiển thị citation coverage, unsupported claims, missing information, weak citations và conflicts nếu có.

### FR-06 — HITL Review

Hệ thống cho phép doctor start review, edit, approve hoặc reject summaries.

### FR-07 — Audit Logging

Hệ thống ghi audit log cho các hành động nhạy cảm như generation, citation view, edit, approve, reject, import và metrics access.

### FR-08 — Admin Monitoring

Hệ thống cung cấp dashboard metrics về summary volume, approval/rejection, citation coverage, safety flags và audit activity.

### FR-09 — Human Evaluation

Hệ thống cho phép evaluation reviewers chấm generated summaries theo factual correctness, completeness, conciseness, readability, citation usefulness và hallucination risk.

### FR-10 — Evaluation Center

Hệ thống cung cấp control center hiển thị golden path readiness, provider readiness, functional validation, benchmark status, human evaluation và demo checklist.

---

## 11. Non-functional Requirements

| Category        | Requirement                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------------- |
| Safety          | Không có autonomous clinical decision-making                                                   |
| Traceability    | Các supported clinical claims nên truy vết được về evidence                                    |
| Security        | Role-based access và audit logs                                                                |
| Privacy         | Không expose raw PHI trong logs; external LLM disabled by default                              |
| Usability       | Doctor có thể verify evidence nhanh chóng                                                      |
| Maintainability | Provider abstraction và modular service layer                                                  |
| Evaluation      | Functional, structured EHR, open benchmark, real benchmark và human evaluation được tách riêng |
| Reliability     | Có failure handling rõ cho model/provider errors                                               |
| Accountability  | Approve/reject/edit actions phải truy vết được                                                 |
| Transparency    | Unsupported hoặc uncertain claims phải được hiển thị rõ                                        |

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
And the summary is not marked approved automatically
```

### US-002 — Verify claim citation

As a doctor, I want to click a citation next to a claim so that I can verify the source evidence.

**Acceptance criteria**

```gherkin
Given a summary claim has a citation
When the doctor clicks the citation badge
Then the source evidence panel opens
And the source text or structured record is displayed
And the source belongs to the same patient
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

| Feature                 |   Doctor |    Nurse | Clinical Admin | IT Admin |   Auditor | AI Safety Reviewer | Evaluation Reviewer |
| ----------------------- | -------: | -------: | -------------: | -------: | --------: | -----------------: | ------------------: |
| View patient list       |      Yes |  Limited |        Limited |       No | Read-only |            Limited |                  No |
| Generate summary        |      Yes |       No |             No |       No |        No |                 No |                  No |
| View citation           |      Yes |  Limited |            Yes |       No | Read-only |                Yes |                 Yes |
| Edit summary            |      Yes |       No |             No |       No |        No |                 No |                  No |
| Approve/reject summary  |      Yes |       No |             No |       No |        No |                 No |                  No |
| View dashboard          |  Limited |       No |            Yes |      Yes | Read-only |                Yes |             Limited |
| View audit logs         |  Limited |       No |            Yes |      Yes |       Yes |          Read-only |                  No |
| Import data             |       No |       No |             No |      Yes |        No |                 No |                  No |
| Submit human evaluation | Optional | Optional |       Optional |       No |        No |           Optional |                 Yes |

Role-based UI không chỉ là tính năng giao diện. Đây là một cơ chế safety và accountability. Hệ thống phải ngăn người dùng không có quyền biến AI draft output thành approved clinical documentation.

---

## 14. Evaluation Strategy

Evaluation design của dự án là một **multi-layer evaluation strategy**. Mục đích là tránh overclaim bằng cách tách rõ workflow validation, structured data validation, open benchmark evaluation, future real EHR benchmarking và human evaluation.

### 14.1 Các tầng đánh giá

| Layer                                                     | Dataset / source                                 | Câu hỏi đánh giá                                                                        | Claim được phép nói                                                               | Claim không được phép nói                                        | Trạng thái               |
| --------------------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------ |
| Layer A — Functional Workflow Validation                  | Mock / de-identified demo data                   | Product workflow có chạy end-to-end không?                                              | Hệ thống có thể chạy patient review, draft summary, HITL, audit và dashboard flow | Model có clinical performance thật                               | Implemented / demo-ready |
| Layer B — Structured EHR Validation                       | MIMIC-III demo DB hoặc structured EHR-style data | Hệ thống có biểu diễn được patient, encounter, diagnosis, lab và medication data không? | Hệ thống map được structured EHR-style records                                    | Note-level summarization quality                                 | Partial / optional       |
| Layer C.1 — Primary Open Clinical Summarization Benchmark | MultiClinSum                                     | Pegasus/BART có sinh summary so sánh được với reference summary không?                  | Open clinical summarization benchmark performance bằng ROUGE/BERTScore            | Real hospital EHR benchmark performance                          | Planned / next step      |
| Layer C.2 — Auxiliary Dialogue-to-Note Proxy Evaluation   | MTS-Dialog                                       | Hệ thống có thể evaluate dialogue-to-note section generation không?                     | Dialogue-to-note proxy performance                                                | Full medical record summarization hoặc real EHR performance      | Optional                 |
| Layer C.3 — Optional Full-Visit Dialogue-to-Note Proxy    | ACI-BENCH                                        | Hệ thống có thể evaluate full-visit dialogue-to-note generation không?                  | Visit-dialogue-to-note proxy performance                                          | Real EHR note-level benchmark performance                        | Optional                 |
| Normalization Stress Test                                 | BIOMEDNLP/mtsamples_clean                        | Hệ thống có normalize được messy clinical transcription inputs không?                   | Input normalization và chunking robustness                                        | Supervised summarization benchmark performance                   | Planned                  |
| Layer D — Future Real EHR Note-Level Benchmark            | MIMIC-IV-Ext-BHC / MIMIC-IV-Note                 | Model có summarize được real EHR notes không?                                           | Future real EHR note-level benchmark evidence                                     | Current performance claim                                        | Future / pending access  |
| Layer E — Human Evaluation                                | Selected generated summaries                     | Output có hữu ích, an toàn, dễ đọc và kiểm chứng được với human reviewers không?        | Human-perceived quality and safety signals                                        | Large-scale clinical validation nếu thiếu governed expert review | Planned                  |

### 14.2 Chiến lược metric

| Câu hỏi đánh giá                                    | Metric / method                                                     | Vì sao dùng                                                                             | Giới hạn                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Generated summary có overlap với reference không?   | ROUGE-1, ROUGE-2, ROUGE-L                                           | Metric summarization phổ biến cho lexical overlap                                       | Có thể bỏ sót paraphrase đúng nghĩa                           |
| Generated summary có gần nghĩa với reference không? | BERTScore                                                           | Dùng contextual embeddings để so sánh semantic similarity                               | Không đảm bảo clinical correctness đầy đủ                     |
| Hệ thống có chạy ổn định không?                     | success rate, failure count, latency                                | Đánh giá execution readiness                                                            | Không đo clinical quality                                     |
| Claims có được grounded không?                      | citation coverage, unsupported claim count, claim-source similarity | Đo evidence traceability                                                                | Automatic grounding checks có thể bỏ sót lỗi lâm sàng tinh vi |
| Output có reviewable và useful không?               | Human evaluation                                                    | Đánh giá factuality, completeness, readability, citation usefulness, hallucination risk | Cần reviewer có rubric rõ                                     |
| LLM có thể hỗ trợ đánh giá quality không?           | Optional LLM-as-Judge                                               | Hữu ích cho qualitative triage                                                          | Không phải clinical ground truth và có thể bias               |

### 14.3 Vai trò model trong evaluation

| Model / tool               | Vai trò trong dự án                                                                             |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| Pegasus / BART             | Summarization generation baselines cho Layer C benchmark evaluation                             |
| BERT / BioBERT / BERTScore | Semantic evaluation hoặc claim-source similarity support, không phải main abstractive generator |
| Gemini                     | Product LLM provider và controlled difficult-case input normalization assistant                 |
| Deterministic summarizer   | Stable baseline để test workflow và evaluation pipeline                                         |
| Human reviewer             | Final review layer cho usefulness, safety perception và clinical plausibility                   |

### 14.4 Cách diễn giải kết quả đánh giá

Dự án tách rõ những gì có thể validate hiện tại và những gì cần dữ liệu/quy trình tương lai. Week 1 có thể claim product definition, workflow design, safety boundary và evaluation planning. Nếu demo console đã sẵn sàng, Week 1 cũng có thể cho thấy early functional feasibility.

Week 1 không nên claim real EHR benchmark performance, clinical validation hoặc production readiness.

---

## 15. Risks and Mitigation

| Risk                                            | Severity | Mitigation                                                               |
| ----------------------------------------------- | -------: | ------------------------------------------------------------------------ |
| Model hallucinate clinical fact                 |     High | Citation-required claims, unsupported flag, doctor review                |
| Citation yếu hoặc sai                           |     High | Citation confidence, source viewer, human review                         |
| User over-trust AI output                       |     High | Draft status, safety label, approval workflow                            |
| Dataset misinterpretation / benchmark overclaim |     High | Evidence ladder và allowed-claim table                                   |
| External LLM data privacy risk                  |     High | Disabled by default, de-identified demo data only unless approved        |
| LLM normalization thêm facts                    |     High | Strict JSON schema, source_text requirement, raw text as source of truth |
| Role misuse                                     |   Medium | Role-based UI + backend permission checks                                |
| Metrics bị hiểu sai                             |   Medium | Tách functional/proxy/real benchmark claims                              |
| Real EHR benchmark unavailable                  |   Medium | Future Layer D status, no overclaim                                      |
| Human evaluation sample nhỏ                     |   Medium | Report as preliminary, not clinical validation                           |

---

## 16. Roadmap

| Phase   | Outcome                                      |
| ------- | -------------------------------------------- |
| Phase 1 | Database and persistence foundation          |
| Phase 2 | API and ingestion alignment                  |
| Phase 3 | Deterministic summary + claims + citations   |
| Phase 4 | Doctor Golden Path UI                        |
| Phase 5 | HITL review workflow                         |
| Phase 6 | Audit, metrics and dashboard                 |
| Phase 7 | BART/Pegasus/Gemini provider integration     |
| Phase 8 | Evaluation center and multi-layer validation |
| Phase 9 | Final demo hardening and report              |
| Future  | Real EHR benchmark and clinical validation   |

---

## 17. Future Work

1. Acquire credentialed MIMIC-IV-Ext-BHC/MIMIC-IV-Note access for true EHR note benchmark.
2. Run Layer C benchmark with MultiClinSum using Pegasus/BART and ROUGE/BERTScore.
3. Add MTS-Dialog as auxiliary dialogue-to-note evaluation.
4. Use BIOMEDNLP/mtsamples_clean to test messy input normalization.
5. Improve claim-level factuality verification.
6. Add stronger medication/allergy/lab validation.
7. Implement SMART on FHIR sandbox integration.
8. Replace mock RBAC with production SSO/OAuth.
9. Add prompt/model regression testing before release.
10. Run human evaluation with clinicians, medical students, or domain-aware reviewers.

---

## 18. References

* Aali, A. et al. (2025) *MIMIC-IV-Ext-BHC: Labeled Clinical Notes Dataset for Hospital Course Summarization*. PhysioNet. Available at: https://physionet.org/content/labelled-notes-hospital-course/
* Bednarczyk, L. et al. (2025) *Scientific Evidence for Clinical Text Summarization Using Large Language Models*. Journal of Medical Internet Research. Available at: https://www.jmir.org/2025/1/e68998/
* Croxford, E. et al. (2025) *Evaluating clinical AI summaries with large language models*. npj Digital Medicine. Available at: https://www.nature.com/articles/s41746-025-02005-2
* FDA (2026) *Clinical Decision Support Software: Guidance for Industry and Food and Drug Administration Staff*. Available at: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
* HL7 (2024) *SMART App Launch Implementation Guide*. Available at: https://build.fhir.org/ig/HL7/smart-app-launch/
* Johnson, A. et al. (2024) *MIMIC-IV-Note: Deidentified free-text clinical notes*. PhysioNet. Available at: https://physionet.org/content/mimic-iv-note/
* NIST (2024) *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. Available at: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
* Tang, L. et al. (2023) *Evaluating large language models on medical evidence summarization*. npj Digital Medicine. Available at: https://pmc.ncbi.nlm.nih.gov/articles/PMC10449915/
* WHO (2021) *Ethics and governance of artificial intelligence for health*. Available at: https://www.who.int/publications/i/item/9789240029200
* A Survey on Medical Document Summarization. Available at: https://arxiv.org/abs/2212.01669
* Domain-Specific Language Model Pretraining for Biomedical Natural Language Processing. Available at: https://arxiv.org/abs/2007.15779



