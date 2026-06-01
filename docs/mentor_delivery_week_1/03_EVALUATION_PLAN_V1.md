# 03 — Evaluation Plan v1.1: Chiến lược đánh giá nhiều tầng cho Medical Record Summarization MVP

**Loại tài liệu:** Chiến lược đánh giá dành cho mentor
**Phiên bản:** v1.1
**Mục tiêu:** Làm rõ hệ thống được đánh giá như thế nào, dataset nào chứng minh được điều gì, và giới hạn nào không được overclaim.

---

## 1. Mục đích tài liệu

Tài liệu này xác định chiến lược đánh giá cho hệ thống **Medical Record Summarization MVP**. Nguyên tắc cốt lõi là: **không một dataset, metric hay demo đơn lẻ nào đủ để chứng minh chất lượng của một hệ thống tóm tắt bệnh án**.

Trong bối cảnh clinical AI, cần phân biệt rõ các loại bằng chứng khác nhau:

```text
workflow có chạy được không
≠ model có tóm tắt tốt không
≠ output có factual không
≠ summary có hữu ích cho bác sĩ không
≠ hệ thống đã được validate trên real EHR notes
```

Vì vậy, chiến lược đánh giá của dự án được thiết kế theo hướng **multi-layer evaluation strategy**. Mỗi layer trả lời một câu hỏi đánh giá khác nhau và chỉ được dùng để đưa ra những claim phù hợp với loại dữ liệu/metric của layer đó.

Các tầng đánh giá chính gồm:

```text
Layer A — Functional Workflow Validation
Layer B — Structured EHR Validation
Layer C — Open Clinical Summarization Benchmark
Layer D — Future Real EHR Note-Level Benchmark
Layer E — Human Evaluation
```

Ngoài ra, dự án có một nhánh riêng cho **Normalization Stress Test** nhằm kiểm tra khả năng xử lý input bệnh án messy trước khi chunking và citation.

---

## 2. Nguyên tắc đánh giá

| Nguyên tắc                                  | Ý nghĩa                                                                                                                                     |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Tách workflow validation khỏi model quality | Mock/demo data có thể chứng minh hệ thống chạy đúng flow, nhưng không chứng minh chất lượng mô hình                                         |
| Tách open benchmark khỏi real EHR benchmark | MultiClinSum/MTS-Dialog là open/proxy benchmark, không phải real hospital EHR note-level benchmark                                          |
| Không overclaim                             | Mỗi dataset chỉ được dùng cho loại claim mà nó có thể hỗ trợ                                                                                |
| Đánh giá traceability                       | Citation coverage, unsupported claim count và claim-source similarity là chỉ số quan trọng vì hệ thống định vị theo hướng citation-grounded |
| Giữ human review                            | Automatic metrics như ROUGE/BERTScore không đủ để kết luận clinical usefulness                                                              |
| Tôn trọng data governance                   | Restricted clinical datasets không được commit, chia sẻ hoặc gửi ra external LLM nếu chưa có governance                                     |
| So sánh provider có kiểm soát               | Deterministic, BART, Pegasus và Gemini phải được đánh giá trong cùng điều kiện dữ liệu rõ ràng                                              |
| Diễn giải metric cẩn trọng                  | Metric cao không đồng nghĩa với clinical validation                                                                                         |

---

## 3. Tổng quan Evaluation Layers

| Layer                                                     | Dataset / source                                 | Câu hỏi đánh giá                                                       | Claim được phép nói                                                                         | Claim không được phép nói                                                    | Trạng thái               |
| --------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------ |
| Layer A — Functional Workflow Validation                  | Mock / de-identified demo data                   | Workflow sản phẩm có chạy end-to-end không?                            | Hệ thống có thể chạy patient review, draft summary, citation, HITL, audit và dashboard flow | Model có clinical performance thật                                           | Implemented / demo-ready |
| Layer B — Structured EHR Validation                       | MIMIC-III demo DB hoặc structured EHR-style data | Hệ thống có xử lý được dữ liệu EHR có cấu trúc không?                  | Hệ thống map được patient, encounter, diagnosis, labs, medications                          | Note-level summarization quality                                             | Partial / optional       |
| Layer C.1 — Primary Open Clinical Summarization Benchmark | MultiClinSum                                     | Pegasus/BART có sinh summary so sánh được với reference summary không? | Open clinical summarization benchmark performance                                           | Real hospital EHR benchmark performance                                      | Planned / next step      |
| Layer C.2 — Auxiliary Dialogue-to-Note Proxy Evaluation   | MTS-Dialog                                       | Model có xử lý được dialogue-to-note section task không?               | Dialogue-to-note proxy performance                                                          | Full medical record summarization hoặc real EHR performance                  | Optional auxiliary       |
| Layer C.3 — Optional Full-Visit Dialogue-to-Note Proxy    | ACI-BENCH                                        | Model có xử lý được full visit dialogue-to-note task không?            | Visit-dialogue-to-note proxy performance                                                    | Real EHR discharge-note benchmark                                            | Optional                 |
| Normalization Stress Test                                 | BIOMEDNLP/mtsamples_clean                        | Hệ thống có xử lý được clinical text messy không?                      | Input normalization và chunking robustness                                                  | Supervised summarization benchmark performance nếu thiếu reference summaries | Planned                  |
| Layer D — Future Real EHR Note-Level Benchmark            | MIMIC-IV-Ext-BHC / MIMIC-IV-Note                 | Model có tóm tắt được real EHR notes không?                            | Future real EHR note-level benchmark evidence                                               | Current performance claim                                                    | Future / pending access  |
| Layer E — Human Evaluation                                | Selected generated summaries                     | Output có useful, factual, readable và verifiable không?               | Human-perceived quality and safety signals                                                  | Large-scale clinical validation nếu thiếu governed expert review             | Planned                  |

---

## 4. Layer A — Functional Workflow Validation

### 4.1 Mục đích

Layer A kiểm tra hệ thống sản phẩm có hoạt động end-to-end hay không. Đây là tầng kiểm chứng **workflow readiness**, không phải tầng kiểm chứng chất lượng mô hình.

### 4.2 Dataset

Dữ liệu mock/de-identified demo.

### 4.3 Layer này chứng minh điều gì?

| Hạng mục kiểm tra              | Ý nghĩa                                    |
| ------------------------------ | ------------------------------------------ |
| Patient list hoạt động         | UI/API integration hoạt động               |
| Patient detail load được       | Data retrieval hoạt động                   |
| Source documents hiển thị được | Doctor có thể review dữ liệu gốc           |
| Summary generation hoạt động   | Provider pipeline hoạt động                |
| Draft status được enforce      | AI output không tự động trở thành official |
| Claims/citations render được   | Citation UX hoạt động                      |
| Safety panel hiển thị warning  | Unsupported/weak claims được làm visible   |
| HITL approve/reject hoạt động  | Doctor workflow hoạt động                  |
| Audit logs tồn tại             | Traceability hoạt động                     |
| Dashboard cập nhật             | Monitoring hoạt động                       |

### 4.4 Layer này không chứng minh điều gì?

Layer A **không chứng minh**:

* chất lượng mô hình summarization;
* clinical factuality;
* real EHR benchmark performance;
* khả năng tổng quát hóa trên dữ liệu bệnh án thật;
* độ an toàn lâm sàng trong môi trường production.

Do đó, Layer A chỉ nên được diễn giải là: **MVP workflow có thể chạy được và có các safety gates cơ bản**.

---

## 5. Layer B — Structured EHR Validation

### 5.1 Mục đích

Layer B kiểm tra hệ thống có thể xử lý dữ liệu EHR có cấu trúc, thay vì chỉ chạy trên mock records.

### 5.2 Dataset

MIMIC-III Clinical Database Demo hoặc dữ liệu structured EHR-style tương đương.

### 5.3 Vai trò của dataset

MIMIC-III demo database phù hợp để kiểm thử:

* patient ingestion;
* admissions/encounters;
* diagnoses;
* labs;
* medications;
* structured citations;
* monitoring dashboard.

Tuy nhiên, dataset này **không phù hợp để train hoặc benchmark mô hình note summarization** nếu không có clinical narrative rows hữu ích trong `NOTEEVENTS`.

### 5.4 Metrics/checks

| Nhóm kiểm tra      | Nội dung kiểm tra                                                                       |
| ------------------ | --------------------------------------------------------------------------------------- |
| Import             | patients, admissions, diagnoses, labs, prescriptions được import                        |
| Mapping            | records được map vào internal patient/encounter/condition/observation/medication tables |
| Structured summary | hệ thống tạo được structured patient context                                            |
| Citation           | claims có thể cite diagnosis/lab/medication sources                                     |
| Dashboard          | counts và audit logs được cập nhật                                                      |

### 5.5 Cách diễn giải đúng

> Structured EHR validation validates ingestion and structured evidence mapping, but not note-level summarization benchmark performance.

Bản tiếng Việt:

> Structured EHR validation giúp kiểm tra khả năng ingestion và evidence mapping đối với dữ liệu EHR có cấu trúc, nhưng không chứng minh hiệu năng benchmark cho bài toán note-level summarization.

---

## 6. Layer C — Open Clinical Summarization Benchmark

### 6.1 Mục đích

Layer C đáp ứng yêu cầu đánh giá BART/Pegasus bằng các dataset có cặp **source document/reference summary** hoặc cặp **dialogue/reference note** phù hợp cho benchmark mở.

Layer C không được gọi là real EHR benchmark. Nó là tầng **open clinical summarization benchmark / proxy evaluation**.

---

### 6.2 Layer C.1 — MultiClinSum: Primary Open Clinical Summarization Benchmark

#### Vai trò

MultiClinSum là dataset chính cho yêu cầu BART/Pegasus evaluation trong giai đoạn hiện tại.

#### Vì sao chọn MultiClinSum?

MultiClinSum phù hợp hơn các dataset chỉ có raw text vì nó cung cấp các cặp:

```text
clinical case report / clinical document
→ reference summary
```

Điều này cho phép hệ thống chạy:

```text
source document
→ Pegasus/BART generated summary
→ compare with reference summary
→ ROUGE/BERTScore/report
```

#### Layer này có thể chứng minh

* mô hình Pegasus/BART có thể chạy trên clinical summarization benchmark mở;
* generated summaries có thể được so sánh với reference summaries;
* evaluation pipeline có thể xuất ROUGE, BERTScore, latency, success rate;
* dự án có năng lực đánh giá model output beyond mock data.

#### Layer này không chứng minh

* model hoạt động tốt trên hospital EHR notes thật;
* model đã được clinical validation;
* summary đủ an toàn để dùng trong real clinical workflow;
* hệ thống đã sẵn sàng production.

#### Metrics

| Metric         | Mục đích              | Giới hạn                                                      |
| -------------- | --------------------- | ------------------------------------------------------------- |
| ROUGE-1        | unigram overlap       | lexical, không đủ đo factuality                               |
| ROUGE-2        | bigram overlap        | nhạy với phrasing                                             |
| ROUGE-L        | sequence overlap      | không đảm bảo đúng lâm sàng                                   |
| BERTScore      | semantic similarity   | tốt hơn lexical overlap nhưng không phải clinical correctness |
| Latency        | thời gian sinh output | không đo chất lượng                                           |
| Success rate   | tỷ lệ chạy thành công | không đo factuality                                           |
| Summary length | độ dài output         | không đo usefulness                                           |

---

### 6.3 Layer C.2 — MTS-Dialog: Auxiliary Dialogue-to-Note Proxy Evaluation

#### Vai trò

MTS-Dialog là dataset phụ cho task:

```text
doctor-patient dialogue
→ clinical note section
```

#### Vì sao chỉ là auxiliary?

MTS-Dialog hữu ích vì nó gần với bài toán clinical documentation, nhưng task của nó là dialogue-to-note section, không phải full medical record summarization. Do đó, nó không thay thế MultiClinSum trong vai trò benchmark chính.

#### Có thể chứng minh

* model có thể xử lý clinical dialogue input;
* model có thể sinh note section từ hội thoại;
* evaluation pipeline có thể mở rộng sang dialogue-to-note proxy task.

#### Không thể chứng minh

* full record summarization performance;
* real EHR benchmark performance;
* hospital note summarization quality.

---

### 6.4 Layer C.3 — ACI-BENCH: Optional Full-Visit Dialogue-to-Note Proxy

ACI-BENCH có thể được dùng như dataset phụ nếu muốn mở rộng sang full-visit dialogue-to-note generation.

Dataset này hữu ích cho hướng clinical documentation từ hội thoại, nhưng vẫn không phải real EHR note-level benchmark.

---

## 7. Normalization Stress Test — BIOMEDNLP/mtsamples_clean

### 7.1 Mục đích

Ngoài benchmark summarization, hệ thống cần kiểm tra khả năng xử lý input messy. Trong thực tế, clinical documents có thể chứa:

* heading không chuẩn;
* mixed narrative;
* abbreviation;
* copied-forward text;
* format không đồng nhất;
* section bị thiếu hoặc gộp.

BIOMEDNLP/mtsamples_clean phù hợp để stress test:

```text
messy clinical transcription
→ rule-based section detection
→ difficult-case detection
→ optional Gemini-assisted normalization
→ chunking
→ citation-ready representation
```

### 7.2 Layer này có thể chứng minh

* hệ thống có phát hiện được input khó không;
* rule-based chunking fallback như thế nào;
* Gemini-assisted normalization có thể hỗ trợ section normalization ra sao;
* tỷ lệ Narrative-only có giảm không;
* chunk metadata có cải thiện không.

### 7.3 Layer này không chứng minh

* Pegasus/BART summarization benchmark performance;
* real EHR note performance;
* clinical correctness của summary.

### 7.4 Suggested metrics

| Metric                     | Ý nghĩa                                           |
| -------------------------- | ------------------------------------------------- |
| Narrative-only rate        | tỷ lệ tài liệu bị fallback hoàn toàn về Narrative |
| Section detection coverage | tỷ lệ section nhận diện được                      |
| JSON valid rate            | tỷ lệ output normalization hợp schema             |
| LLM fallback rate          | tỷ lệ Gemini lỗi và fallback rule-based           |
| Needs-review count         | số section/claim cần human review                 |
| Chunk count                | số chunk sinh ra sau normalization                |
| Manual review sample       | đánh giá thủ công một số case khó                 |

---

## 8. Layer D — Future Real EHR Note-Level Benchmark

### 8.1 Mục đích

Layer D là benchmark thật cho bài toán clinical note summarization khi có quyền truy cập dataset phù hợp.

### 8.2 Preferred dataset

**MIMIC-IV-Ext-BHC** là lựa chọn ưu tiên vì dataset này cung cấp các cặp input-target đã được gán nhãn cho bài toán **Brief Hospital Course summarization**.

### 8.3 Fallback dataset

**MIMIC-IV-Note discharge summaries** có thể được dùng làm fallback. Nếu dùng dataset này, hệ thống cần extract phần **Brief Hospital Course** làm target summary và dùng phần discharge content còn lại làm input.

### 8.4 Trạng thái hiện tại

```text
Pending credentialed access.
```

### 8.5 Quy tắc báo cáo

Nếu chưa có dataset này, hệ thống phải hiển thị rõ:

```text
Real EHR note-level benchmark: Pending credentialed dataset.
No real EHR benchmark performance claim is made from mock/demo data or open proxy datasets.
```

Bản tiếng Việt:

```text
Real EHR note-level benchmark: Đang chờ quyền truy cập dataset hợp lệ.
Không đưa ra claim về benchmark performance trên EHR notes thật dựa trên mock/demo data hoặc proxy datasets.
```

---

## 9. Layer E — Human Evaluation

### 9.1 Mục đích

Layer E đánh giá chất lượng đầu ra vượt ra ngoài automatic metrics.

Automatic metrics như ROUGE hoặc BERTScore có thể hỗ trợ so sánh model output với reference summary, nhưng chưa đủ để đánh giá đầy đủ clinical summary quality, đặc biệt với các tiêu chí như factual correctness, usefulness, citation usefulness, readability và hallucination risk.

### 9.2 Sample size

| Bối cảnh                     |               Cỡ mẫu khuyến nghị |
| ---------------------------- | -------------------------------: |
| Internship MVP               |                  10–30 summaries |
| Stronger internal validation |                  30–50 summaries |
| Clinical pilot               | 50+ clinician-reviewed summaries |

### 9.3 Rubric

| Tiêu chí            |      Thang điểm | Ý nghĩa                                               |
| ------------------- | --------------: | ----------------------------------------------------- |
| Factual correctness |             1–5 | Summary có được source hỗ trợ không?                  |
| Completeness        |             1–5 | Summary có bao phủ thông tin quan trọng không?        |
| Conciseness         |             1–5 | Summary có đủ ngắn gọn và đúng trọng tâm không?       |
| Readability         |             1–5 | Summary có rõ ràng cho clinical review không?         |
| Citation usefulness |             1–5 | Citation có giúp kiểm chứng thông tin không?          |
| Hallucination risk  | low/medium/high | Summary có vẻ thêm thông tin không được hỗ trợ không? |

### 9.4 Human evaluator types

| Evaluator                  | Mục đích sử dụng                        |
| -------------------------- | --------------------------------------- |
| Medical/healthcare student | preliminary domain-aware review         |
| Clinician nếu có           | stronger clinical validation            |
| Product/AI reviewer        | usability và workflow feedback          |
| Non-domain reviewer        | chỉ dùng cho readability và UI feedback |

### 9.5 Giới hạn

Human evaluation trong MVP không đồng nghĩa với clinical validation quy mô lớn. Nó là bước đánh giá định tính/định lượng ban đầu về usefulness, trust, readability và reviewability.

---

## 10. Functional Validation Test Cases

| ID     | Test case                | Expected result                       |
| ------ | ------------------------ | ------------------------------------- |
| FV-001 | Seed demo data           | demo patient records available        |
| FV-002 | Open patient list        | patients displayed                    |
| FV-003 | Open patient detail      | patient context and documents visible |
| FV-004 | Generate summary         | draft summary created                 |
| FV-005 | Click citation           | evidence panel opens                  |
| FV-006 | Unsupported claim exists | appears in safety panel               |
| FV-007 | Start review             | status under_review                   |
| FV-008 | Edit summary             | status edited                         |
| FV-009 | Approve summary          | status approved, audit created        |
| FV-010 | Reject summary           | status rejected with reason           |
| FV-011 | Open dashboard           | metrics visible                       |
| FV-012 | Open audit log           | audit events visible                  |

---

## 11. Safety Evaluation Cases

| Case                       | Expected behavior                                |
| -------------------------- | ------------------------------------------------ |
| Missing allergy data       | System must not claim no allergy                 |
| One lab value only         | System must not claim trend                      |
| Diagnosis absent           | System must not invent diagnosis                 |
| Medication missing         | System must not invent medication                |
| Weak citation              | Claim marked insufficient_evidence               |
| Wrong patient source       | Citation blocked or not returned                 |
| Critical unsupported claim | Approval blocked or requires explicit resolution |
| External LLM disabled      | Gemini not called unless explicitly enabled      |
| Conflicting evidence       | Conflict displayed instead of silently resolved  |
| Source unavailable         | Claim marked needs review                        |

---

## 12. MVP Readiness Gates

| Gate                                    |                                 Target |
| --------------------------------------- | -------------------------------------: |
| AI summaries start as draft             |                                   100% |
| No auto-approval                        |                                   100% |
| Audit logs for sensitive actions        |                100% for tested actions |
| Citation source belongs to same patient |                                   100% |
| Functional validation                   |                                   Pass |
| Human evaluation form                   | Available or planned with clear status |
| Real EHR benchmark status               |      Clearly marked pending if missing |
| No fake benchmark metrics               |                                   100% |
| External LLM disabled unless configured |                                   100% |
| Unsupported high-risk claims visible    |                   100% in tested cases |

---

## 13. Metric Interpretation Guide

| Metric / method         | What it means                                          | What it does not mean                          |
| ----------------------- | ------------------------------------------------------ | ---------------------------------------------- |
| ROUGE                   | Generated summary overlaps with reference wording      | Summary is clinically correct                  |
| BERTScore               | Generated summary is semantically similar to reference | Summary is safe for clinical use               |
| Citation coverage       | Claims have attached evidence                          | Evidence is clinically sufficient in all cases |
| Unsupported claim count | Potential hallucination risk is visible                | All hallucinations are detected                |
| Human evaluation        | Reviewer-perceived quality and usefulness              | Full clinical validation                       |
| LLM-as-Judge            | Optional qualitative triage                            | Clinical ground truth                          |

---

## 14. Evaluation Report Structure

Final report nên bao gồm:

1. Evaluation overview
2. Dataset strategy and allowed claims
3. Functional validation results
4. Structured EHR validation results
5. MultiClinSum Layer C.1 benchmark results
6. Optional MTS-Dialog Layer C.2 results
7. Normalization stress test results
8. Human evaluation results
9. Real EHR benchmark pending status
10. Safety and citation results
11. Limitations
12. Future work

---

## 15. Recommended Mentor-facing Statement

> Hệ thống được đánh giá theo nhiều tầng để tránh overclaim. Mock/de-identified data chỉ được sử dụng để kiểm thử workflow end-to-end. MIMIC-III demo database được dùng để kiểm tra structured EHR ingestion và evidence mapping. MultiClinSum được định vị là primary open clinical summarization benchmark cho Pegasus/BART evaluation bằng ROUGE và BERTScore. MTS-Dialog là auxiliary dialogue-to-note proxy dataset. mtsamples_clean được dùng riêng để stress test messy input normalization. Benchmark thật cho bài toán EHR note-level summarization vẫn đang chờ quyền truy cập hợp lệ vào MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.

---

## 16. Week 1 Interpretation

Trong Week 1, dự án có thể claim:

* đã xác định product scope;
* đã thiết kế workflow chính;
* đã xác định safety boundary;
* đã tách rõ các tầng evaluation;
* đã có hướng dataset strategy phù hợp với hạn chế truy cập dữ liệu;
* đã tránh overclaim từ mock data hoặc open proxy datasets.

Trong Week 1, dự án không claim:

* real EHR benchmark performance;
* clinical validation;
* production readiness;
* certified medical-device readiness;
* diagnosis/treatment accuracy;
* full model training completion.
