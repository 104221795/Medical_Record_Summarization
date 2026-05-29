# 03 — Evaluation Plan v1.0: Chiến lược đánh giá bốn tầng

**Loại tài liệu:** Chiến lược đánh giá dành cho mentor
**Phiên bản:** v1.0

---

## 1. Mục đích tài liệu

Tài liệu này xác định chiến lược đánh giá cho hệ thống **Medical Record Summarization MVP**. Nguyên tắc chính là tránh đánh giá quá mức năng lực của mô hình khi hiện tại chưa có bộ dữ liệu benchmark EHR note-level thật.

Chiến lược đánh giá được chia thành bốn tầng:

```text
Layer A — Functional validation với dữ liệu mock/demo
Layer B — Structured EHR validation với MIMIC-III demo database
Layer C — BART/Pegasus proxy medical text evaluation
Layer D — Real EHR note-level benchmark, pending MIMIC-IV-Ext-BHC / MIMIC-IV-Note
```

Việc chia tầng này giúp dự án phân biệt rõ giữa:

* kiểm thử hệ thống có hoạt động end-to-end hay không;
* kiểm thử khả năng xử lý dữ liệu EHR có cấu trúc;
* đánh giá mô hình trên các dataset medical text proxy;
* và benchmark thật trên clinical notes khi có quyền truy cập dataset phù hợp.

---

## 2. Nguyên tắc đánh giá

| Nguyên tắc                                  | Ý nghĩa                                                                                             |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Tách workflow validation khỏi model quality | Mock/demo data có thể chứng minh hệ thống chạy đúng flow, nhưng không chứng minh chất lượng mô hình |
| Không overclaim                             | Proxy dataset không được gọi là real EHR benchmark                                                  |
| Đánh giá traceability                       | Citation coverage và citation quality là các chỉ số quan trọng                                      |
| Giữ human review                            | Automatic metrics không đủ để đánh giá chất lượng clinical summary                                  |
| Tôn trọng data governance                   | Restricted clinical datasets không được commit hoặc gửi ra bên ngoài nếu chưa được phê duyệt        |
| So sánh provider một cách công bằng         | Deterministic, BART, Pegasus và Gemini cần được đánh giá trong điều kiện dữ liệu rõ ràng            |

---

## 3. Layer A — Functional Validation

### Mục đích

Kiểm tra hệ thống sản phẩm có hoạt động end-to-end hay không.

### Dataset

Dữ liệu mock/de-identified demo.

### Layer này chứng minh điều gì?

| Hạng mục kiểm tra             | Ý nghĩa                      |
| ----------------------------- | ---------------------------- |
| Patient list hoạt động        | UI/API integration hoạt động |
| Patient detail load được      | Data retrieval hoạt động     |
| Summary generation hoạt động  | Provider pipeline hoạt động  |
| Draft status được enforce     | Safety workflow hoạt động    |
| Claims/citations render được  | Citation UX hoạt động        |
| HITL approve/reject hoạt động | Doctor workflow hoạt động    |
| Audit logs tồn tại            | Traceability hoạt động       |
| Dashboard cập nhật            | Monitoring hoạt động         |

### Layer này không chứng minh điều gì?

Layer này **không chứng minh**:

* chất lượng mô hình summarization;
* clinical validity;
* real EHR benchmark performance;
* khả năng tổng quát hóa của mô hình trên dữ liệu bệnh án thật.

Do đó, functional validation chỉ nên được hiểu là kiểm thử workflow và khả năng vận hành của MVP.

---

## 4. Layer B — Structured EHR Validation

### Mục đích

Kiểm tra hệ thống có thể làm việc với dữ liệu EHR có cấu trúc, thay vì chỉ chạy trên mock records.

### Dataset

MIMIC-III Clinical Database Demo.

### Vai trò của dataset

MIMIC-III demo database phù hợp để kiểm thử:

* patient ingestion;
* admissions/encounters;
* diagnoses;
* labs;
* medications;
* structured citations;
* monitoring dashboard.

Tuy nhiên, dataset này **không phù hợp để train mô hình note summarization** nếu `NOTEEVENTS` không có clinical narrative rows.

### Metrics/checks

| Nhóm kiểm tra | Nội dung kiểm tra                                                                                  |
| ------------- | -------------------------------------------------------------------------------------------------- |
| Import        | patients, admissions, diagnoses, labs, prescriptions được import                                   |
| Mapping       | structured records được map vào internal patient/encounter/condition/observation/medication tables |
| Summary       | structured patient summary được tạo                                                                |
| Citation      | claims có thể cite diagnosis/lab/medication sources                                                |
| Dashboard     | counts và audit logs được cập nhật                                                                 |

### Cách diễn đạt trong báo cáo

> Structured EHR validation was performed using the MIMIC-III demo database. This validates ingestion and structured evidence workflows, but not note-level summarization benchmark performance.

Bản tiếng Việt:

> Structured EHR validation được thực hiện bằng MIMIC-III demo database. Layer này giúp kiểm tra khả năng ingestion và evidence mapping đối với dữ liệu EHR có cấu trúc, nhưng không chứng minh hiệu năng benchmark cho bài toán note-level summarization.

---

## 5. Layer C — BART/Pegasus Proxy Medical Text Evaluation

### Mục đích

Đáp ứng yêu cầu đánh giá BART/Pegasus bằng các medical/clinical text summarization datasets hiện có.

### Dataset candidates

| Dataset              | Vai trò                                          |
| -------------------- | ------------------------------------------------ |
| OPI/Open-I           | Proxy cho radiology-style report summarization   |
| D2N/dialogue-to-note | Proxy cho clinical conversation-to-note          |
| CHQ/MeQSum           | Proxy cho consumer health question summarization |

### Giới hạn quan trọng

Các dataset này **không tương đương** với real EHR discharge-note summarization.

Chúng được sử dụng như:

```text
proxy medical text summarization benchmarks
```

không phải:

```text
real EHR note-level benchmark
```

Vì vậy, kết quả trên Layer C chỉ dùng để so sánh baseline BART/Pegasus/Gemini/deterministic trong bối cảnh proxy medical text, không nên được diễn giải thành hiệu năng thực tế trên discharge summaries hoặc clinical notes thật.

### Models

| Model         | Vai trò                                             |
| ------------- | --------------------------------------------------- |
| BART          | Baseline abstractive summarization model            |
| Pegasus       | Baseline abstractive summarization model            |
| Deterministic | Stable baseline/control                             |
| Gemini        | Optional real LLM provider nếu data policy cho phép |

### Metrics

| Metric                  | Mục đích                                         |
| ----------------------- | ------------------------------------------------ |
| ROUGE-1                 | unigram overlap                                  |
| ROUGE-2                 | bigram overlap                                   |
| ROUGE-L                 | sequence overlap                                 |
| BERTScore               | semantic similarity, optional                    |
| Latency                 | so sánh hiệu năng/thời gian phản hồi             |
| Summary length          | kiểm tra độ dài và mức độ compression            |
| Citation coverage       | tỷ lệ generated claims/sentences có source match |
| Citation similarity     | độ mạnh trung bình của matched evidence          |
| Unsupported claim count | proxy cho hallucination risk                     |

---

## 6. Layer D — Real EHR Note-level Benchmark

### Mục đích

Thực hiện benchmark thật cho bài toán clinical note summarization khi có quyền truy cập dataset phù hợp.

### Preferred dataset

**MIMIC-IV-Ext-BHC** là lựa chọn ưu tiên vì dataset này cung cấp các cặp input-target đã được gán nhãn cho bài toán **Brief Hospital Course summarization**.

### Fallback dataset

**MIMIC-IV-Note discharge summaries** có thể được dùng làm fallback. Nếu dùng dataset này, hệ thống cần extract phần **Brief Hospital Course** làm target summary và dùng phần discharge content còn lại làm input.

### Trạng thái hiện tại

```text
Pending credentialed access.
```

### Quy tắc báo cáo

Nếu chưa có dataset này, hệ thống phải hiển thị rõ:

```text
Real EHR note-level benchmark: Pending credentialed dataset.
No benchmark performance claim is made from mock/demo data.
```

Bản tiếng Việt:

```text
Real EHR note-level benchmark: Đang chờ quyền truy cập dataset hợp lệ.
Không đưa ra claim về benchmark performance dựa trên mock/demo data.
```

---

## 7. Human Evaluation

### Mục đích

Đánh giá chất lượng đầu ra vượt ra ngoài các automatic metrics.

Automatic metrics như ROUGE hoặc BERTScore có thể hỗ trợ so sánh mô hình, nhưng chưa đủ để đánh giá đầy đủ clinical summary quality, đặc biệt với các tiêu chí như factual correctness, usefulness, citation usefulness và hallucination risk.

### Sample size

| Bối cảnh                     |               Cỡ mẫu khuyến nghị |
| ---------------------------- | -------------------------------: |
| Internship MVP               |                  10–30 summaries |
| Stronger internal validation |                  30–50 summaries |
| Clinical pilot               | 50+ clinician-reviewed summaries |

### Rubric

| Tiêu chí            |      Thang điểm | Ý nghĩa                                               |
| ------------------- | --------------: | ----------------------------------------------------- |
| Factual correctness |             1–5 | Summary có được source hỗ trợ không?                  |
| Completeness        |             1–5 | Summary có bao phủ thông tin quan trọng không?        |
| Conciseness         |             1–5 | Summary có đủ ngắn gọn và đúng trọng tâm không?       |
| Readability         |             1–5 | Summary có rõ ràng cho clinical review không?         |
| Citation usefulness |             1–5 | Citation có giúp kiểm chứng thông tin không?          |
| Hallucination risk  | low/medium/high | Summary có vẻ thêm thông tin không được hỗ trợ không? |

### Human evaluator types

| Evaluator                  | Mục đích sử dụng                        |
| -------------------------- | --------------------------------------- |
| Medical/healthcare student | preliminary domain-aware review         |
| Clinician nếu có           | stronger clinical validation            |
| Product/AI reviewer        | usability và workflow feedback          |
| Non-domain reviewer        | chỉ dùng cho readability và UI feedback |

---

## 8. Functional Validation Test Cases

| ID     | Test case                | Expected result                |
| ------ | ------------------------ | ------------------------------ |
| FV-001 | Seed demo data           | demo patient records available |
| FV-002 | Open patient list        | patients displayed             |
| FV-003 | Generate summary         | draft summary created          |
| FV-004 | Click citation           | evidence panel opens           |
| FV-005 | Unsupported claim exists | appears in safety panel        |
| FV-006 | Start review             | status under_review            |
| FV-007 | Edit summary             | status edited                  |
| FV-008 | Approve summary          | status approved, audit created |
| FV-009 | Reject summary           | status rejected with reason    |
| FV-010 | Open dashboard           | metrics visible                |

---

## 9. Safety Evaluation Cases

| Case                       | Expected behavior                           |
| -------------------------- | ------------------------------------------- |
| Missing allergy data       | System must not claim no allergy            |
| One lab value only         | System must not claim trend                 |
| Diagnosis absent           | System must not invent diagnosis            |
| Medication missing         | System must not invent medication           |
| Weak citation              | Claim marked insufficient_evidence          |
| Wrong patient source       | Citation blocked or not returned            |
| Critical unsupported claim | Approval blocked or requires resolution     |
| External LLM disabled      | Gemini not called unless explicitly enabled |

---

## 10. MVP Readiness Gates

| Gate                                    |                            Target |
| --------------------------------------- | --------------------------------: |
| AI summaries start as draft             |                              100% |
| No auto-approval                        |                              100% |
| Audit logs for sensitive actions        |           100% for tested actions |
| Citation source belongs to same patient |                              100% |
| Functional validation                   |                              Pass |
| Human evaluation form                   |                         Available |
| Real EHR benchmark status               | Clearly marked pending if missing |
| No fake benchmark metrics               |                              100% |

---

## 11. Evaluation Report Structure

Final report nên bao gồm:

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

Bản tiếng Việt đề xuất:

> Hệ thống được đánh giá theo nhiều tầng. Mock data chỉ được sử dụng để kiểm thử chức năng end-to-end. MIMIC-III demo database được sử dụng để kiểm tra structured EHR ingestion và evidence mapping. BART/Pegasus được đánh giá trên các medical text summarization proxy datasets hiện có. Benchmark thật cho bài toán EHR note-level summarization vẫn đang chờ quyền truy cập hợp lệ vào MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.
