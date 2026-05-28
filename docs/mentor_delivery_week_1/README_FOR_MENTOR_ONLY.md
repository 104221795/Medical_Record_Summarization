# README Dành Cho Mentor — Delivery Week 1

## Tên dự án

**Medical Record Summarization MVP: Hệ thống hỗ trợ tóm tắt bệnh án có citation và kiểm duyệt bởi bác sĩ**

GitHub Repository:
https://github.com/104221795/Medical_Record_Summarization

YouTube Demo Link:
*Sẽ được bổ sung sau khi hoàn thiện video demo MVP.*

---

## 1. Mục đích của bản nộp tuần 1

Bản nộp tuần 1 này bao gồm cả **tài liệu định hướng nghiên cứu/sản phẩm** và **prototype triển khai sớm** cho dự án Medical Record Summarization MVP.

Mục tiêu chính của dự án là thiết kế và xây dựng một hệ thống **hỗ trợ tóm tắt hồ sơ bệnh án** theo hướng an toàn hơn, có khả năng truy xuất nguồn thông tin, hỗ trợ bác sĩ kiểm duyệt và phục vụ đánh giá chất lượng đầu ra.

Dự án **không được định vị là hệ thống ra quyết định y khoa tự động**. Hệ thống không thực hiện:

* khuyến nghị chẩn đoán;
* khuyến nghị điều trị;
* kê đơn thuốc;
* tự động phê duyệt xuất viện;
* chẩn đoán hình ảnh y tế.

Thay vào đó, hệ thống tập trung vào:

* tóm tắt dữ liệu hồ sơ bệnh án đã có;
* gắn citation cho các claim quan trọng;
* flag các thông tin thiếu bằng chứng hoặc có rủi ro;
* yêu cầu bác sĩ kiểm duyệt trước khi phê duyệt;
* ghi nhận audit log và hỗ trợ monitoring.

---

## 2. Các tài liệu nên review trước

Trong tuần 1, các tài liệu mentor nên review trước nằm trong thư mục:

```text
docs/mentor_delivery/
├── 01_PRD_V1_MEDICAL_RECORD_SUMMARIZATION.md
├── 02_USER_FLOW_V1.md
├── 03_EVALUATION_PLAN_V1.md
├── 04_RESEARCH_BACKGROUND_AND_GAPS.md
├── 05_SURVEY_PLAN.md
├── 06_GOLDEN_PATH_UI_V1.md
├── 07_HALLUCINATION_MITIGATION_V1.md
└── 08_ROLE_BASED_UI.md
```

Thứ tự đọc được đề xuất:

1. `01_PRD_V1_MEDICAL_RECORD_SUMMARIZATION.md`
   Tài liệu PRD chính, bao gồm tổng quan sản phẩm, vấn đề, người dùng mục tiêu, user stories, yêu cầu chức năng, chiến lược dữ liệu, chiến lược AI, đánh giá, rủi ro và hướng phát triển.

2. `02_USER_FLOW_V1.md`
   Tài liệu mô tả luồng người dùng chính, bao gồm Doctor Golden Path, citation flow, safety panel, HITL review, admin monitoring, evaluation reviewer flow và role-based access.

3. `04_RESEARCH_BACKGROUND_AND_GAPS.md`
   Tài liệu nền tảng nghiên cứu, giải thích vì sao bài toán quan trọng, các khoảng trống nghiên cứu và cách hệ thống đề xuất xử lý các khoảng trống đó.

4. `03_EVALUATION_PLAN_V1.md`
   Tài liệu thiết kế đánh giá, tách rõ functional validation, structured EHR validation, BART/Pegasus proxy evaluation, real EHR benchmark pending và human evaluation.

5. `05_SURVEY_PLAN.md`
   Kế hoạch khảo sát nhằm xác thực vấn đề, nhu cầu người dùng, yếu tố tạo niềm tin và kỳ vọng về workflow.

Các file còn lại cung cấp thêm chi tiết về UI, hallucination mitigation và phân quyền theo vai trò.

---

## 3. Định hướng hiện tại của dự án

Dự án được phát triển theo hướng **production-style MVP prototype**, không chỉ là một notebook chạy mô hình tóm tắt văn bản.

Hệ thống hiện được chia thành hai hướng chính:

### Track A — Product MVP

Track này tập trung vào workflow sản phẩm end-to-end:

```text
EHR / mock / de-identified data
→ ingestion
→ database
→ clinical documents / structured records
→ summary generation
→ claims
→ citations
→ safety checks
→ doctor review
→ audit logs
→ monitoring dashboard
```

### Track B — Research and Evaluation

Track này đáp ứng yêu cầu đánh giá BART/Pegasus và đánh giá chất lượng summarization:

```text
medical text dataset
→ BART / Pegasus / Gemini / deterministic summarization
→ automatic metrics
→ citation metrics
→ human evaluation
→ final comparison report
```

Do đó, dự án không chỉ chứng minh rằng mô hình có thể sinh summary, mà còn đặt summary vào một workflow có kiểm soát, có citation, có human review và có monitoring.

---

## 4. Tiến độ triển khai vượt yêu cầu ban đầu

Bên cạnh PRD và User Flow, một prototype MVP đã được chuẩn bị sớm để chứng minh tính khả thi của hướng triển khai.

Repository hiện bao gồm:

* FastAPI backend;
* SQLAlchemy database persistence;
* Alembic migration setup;
* data models cho patient, encounter, document, summary, claim, citation, review, audit log và model run;
* FHIR-like ingestion design;
* Doctor Golden Path UI;
* Citation Evidence Panel;
* Safety Panel;
* Human-in-the-loop review workflow: edit, approve, reject;
* Admin metrics và audit dashboard;
* Evaluation & Demo Control Center;
* Deterministic summary provider;
* BART/Pegasus baseline provider adapters và evaluation scripts;
* Gemini provider integration vào persisted draft summary workflow;
* thiết kế human evaluation;
* định hướng role-based UI;
* chiến lược safety và hallucination mitigation.

Phần source code được gửi kèm như bằng chứng cho tiến độ triển khai sớm. Tuy nhiên, trọng tâm review của tuần 1 vẫn là **PRD, User Flow, research framing và evaluation design**.

---

## 5. Ý tưởng MVP chính

Nguyên tắc thiết kế cốt lõi của MVP là:

> AI-generated summary có thể hỗ trợ bác sĩ review hồ sơ nhanh hơn, nhưng các claim y khoa quan trọng cần có nguồn chứng minh và cần được con người kiểm duyệt trước khi phê duyệt.

Vì vậy, output của AI luôn được xem là:

```text
draft
```

không phải kết luận y khoa chính thức.

Luồng người dùng chính:

```text
Doctor selects patient
→ reviews patient context
→ generates draft summary
→ checks claim-level citations
→ reviews safety warnings
→ edits if needed
→ approves or rejects summary
→ system stores audit log and review history
```

---

## 6. Người dùng mục tiêu

Hệ thống được thiết kế xoay quanh nhiều vai trò khác nhau.

| Role                | Trách nhiệm chính                                               |
| ------------------- | --------------------------------------------------------------- |
| Doctor              | Tạo, review, chỉnh sửa, approve hoặc reject summary             |
| Nurse               | Xem approved summary và thông tin hỗ trợ trong phạm vi cho phép |
| Clinical Admin      | Theo dõi chất lượng, metrics và hiệu quả workflow               |
| IT Admin            | Quản lý ingestion, cấu hình hệ thống, provider status và setup  |
| Auditor             | Xem audit logs và review history ở chế độ read-only             |
| AI Safety Reviewer  | Theo dõi unsupported claims, citation quality và safety issues  |
| Evaluation Reviewer | Chấm điểm human evaluation cho generated summaries              |

Trong MVP hiện tại, role-based access được mô phỏng bằng lightweight mock role mechanism. Production SSO/OAuth và hardened RBAC được xem là future work.

---

## 7. Các chức năng chính của hệ thống

### 7.1 Doctor Workspace

Doctor UI hỗ trợ:

* danh sách bệnh nhân;
* chi tiết bệnh nhân;
* overview về encounter và clinical documents;
* tạo summary;
* lựa chọn provider;
* hiển thị claims và citations;
* citation source panel;
* safety panel;
* edit / approve / reject workflow;
* review history.

### 7.2 Citation-Based Summary

Mỗi clinical claim quan trọng nên rơi vào một trong hai nhóm:

* có citation liên kết tới nguồn dữ liệu;
* hoặc được flag là unsupported, conflicting, unchecked hoặc insufficiently evidenced.

Citation workflow là phần cốt lõi của dự án vì nó cho phép người dùng kiểm tra lại nguồn gốc của các thông tin trong summary.

### 7.3 Hallucination Mitigation

Dự án giảm rủi ro hallucination thông qua:

* citation-required clinical claims;
* unsupported claim detection;
* missing-data policy;
* safety panel;
* doctor review trước khi approve;
* audit logs;
* evaluation metrics.

Hệ thống nên ưu tiên nói rằng dữ liệu không có sẵn, thay vì tự suy luận thông tin chưa được chứng minh.

### 7.4 Human-in-the-Loop Review

Generated summary luôn bắt đầu ở trạng thái:

```text
draft
```

Sau đó bác sĩ có thể:

```text
start review
→ edit
→ approve
→ reject
```

Approved summary sẽ bị khóa khỏi việc chỉnh sửa thông thường. Rejected summary cần có lý do từ chối.

### 7.5 Monitoring và Audit

Admin Dashboard hỗ trợ theo dõi:

* số lượng summary;
* thống kê approve/reject;
* citation coverage;
* unsupported claim count;
* review metrics;
* audit log visibility;
* MVP readiness indicators.

### 7.6 Evaluation & Demo Control Center

Evaluation & Demo Control Center là trang tổng hợp để hỗ trợ final demo, bao gồm:

* golden path readiness;
* provider readiness;
* citation/safety status;
* HITL review status;
* monitoring summary;
* functional validation;
* trạng thái real EHR benchmark pending;
* human evaluation form/status;
* final demo checklist.

---

## 8. Chiến lược dữ liệu

Chiến lược dữ liệu của dự án được tách theo mục đích sử dụng.

| Data Source                    | Mục đích                                    | Vai trò hiện tại                                            |
| ------------------------------ | ------------------------------------------- | ----------------------------------------------------------- |
| Mock/de-identified demo data   | Functional validation và UI demo            | Available                                                   |
| MIMIC-III demo database        | Structured EHR workflow validation          | Phù hợp cho patient/encounter/diagnosis/lab/medication flow |
| OPI / D2N / CHQ style datasets | BART/Pegasus proxy medical text evaluation  | Hữu ích cho proxy evaluation                                |
| MIMIC-IV-Ext-BHC               | Real EHR note-level summarization benchmark | Pending credentialed access                                 |
| MIMIC-IV-Note                  | Fallback cho real clinical note dataset     | Pending credentialed access                                 |

Điểm cần làm rõ:

MIMIC-III demo database hữu ích để validate structured EHR ingestion và workflow, nhưng chưa đủ để train hoặc benchmark đầy đủ cho bài toán clinical note summarization vì bản demo không có đủ clinical note text cho note-to-summary benchmark training.

Do đó, real EHR note-level benchmark vẫn đang ở trạng thái pending cho đến khi có quyền truy cập hợp lệ vào MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.

---

## 9. Chiến lược đánh giá

Evaluation plan được chia thành nhiều tầng.

### Layer A — Functional Validation

Mục đích:

```text
Chứng minh product workflow chạy end-to-end.
```

Dataset:

```text
Mock/de-identified demo data.
```

Các bước kiểm tra:

* data seeding;
* patient list;
* patient detail;
* document loading;
* summary generation;
* citation display;
* safety panel;
* edit / approve / reject;
* audit log;
* metrics dashboard;
* Evaluation Center status.

### Layer B — Structured EHR Validation

Mục đích:

```text
Validate hệ thống trên dữ liệu EHR có cấu trúc.
```

Dataset:

```text
MIMIC-III demo database.
```

Các bước kiểm tra:

* patient ingestion;
* admission/encounter ingestion;
* diagnosis mapping;
* lab observation mapping;
* medication mapping;
* structured citation support;
* dashboard monitoring.

### Layer C — BART/Pegasus Proxy Medical Text Evaluation

Mục đích:

```text
Đáp ứng yêu cầu đánh giá BART/Pegasus bằng các medical text summarization datasets sẵn có.
```

Metrics:

* ROUGE-1;
* ROUGE-2;
* ROUGE-L;
* optional BERTScore;
* latency;
* generated summary length;
* citation coverage nếu áp dụng được.

Layer này được xem là proxy medical text evaluation, không phải final real EHR benchmark performance.

### Layer D — Real EHR Note-Level Benchmark

Mục đích:

```text
Đánh giá chất lượng summarization trên clinical notes thật đã được de-identified.
```

Target datasets:

* MIMIC-IV-Ext-BHC;
* MIMIC-IV-Note.

Trạng thái:

```text
Pending credentialed dataset access.
```

Hệ thống sẽ không đưa ra claim về model quality chỉ dựa trên mock data.

### Layer E — Human Evaluation

Mục đích:

```text
Thu thập đánh giá của con người về chất lượng summary và citation usefulness.
```

Tiêu chí:

* factual correctness;
* completeness;
* conciseness;
* readability;
* citation usefulness;
* hallucination risk;
* comments.

---

## 10. Research gaps mà dự án xử lý

Dự án được thiết kế để xử lý các khoảng trống nghiên cứu và sản phẩm sau:

| Gap                                                   | Cách dự án xử lý                                                                            |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Clinical summaries thường thiếu traceable evidence    | Claim-level citation và source evidence panel                                               |
| Automatic metrics chưa đủ để đánh giá clinical safety | Bổ sung human evaluation và citation metrics                                                |
| LLM có thể tạo unsupported clinical facts             | Safety panel và unsupported claim flagging                                                  |
| AI output có thể bị tin quá mức                       | Draft-only output và doctor approval workflow                                               |
| Research prototypes thường thiếu workflow integration | Doctor UI, HITL review, audit logs và dashboard                                             |
| Real EHR data bị hạn chế truy cập                     | Tách mock validation, structured EHR validation, proxy evaluation và pending real benchmark |

---

## 11. Safety boundaries

Hệ thống không triển khai:

* diagnosis recommendation;
* treatment recommendation;
* prescription;
* autonomous discharge approval;
* medical image diagnosis.

Tất cả AI-generated summaries phải ở trạng thái draft cho đến khi được bác sĩ review.

Mỗi clinical claim quan trọng cần có citation hoặc được flag rõ ràng.

MVP này nên được hiểu là:

```text
clinical documentation support
```

không phải:

```text
clinical decision automation
```

---

## 12. Cấu trúc repository

Repository được tổ chức như sau:

```text
backend/app/
  main.py                  FastAPI application setup
  routers/                 API endpoints
  services/                Business logic and workflow services
  repositories/            Database query/write layer
  models/                  SQLAlchemy ORM models
  db/                      DB session, base metadata, seed utilities

backend/ui/
  doctor/                  Doctor Golden Path UI
  admin/                   Admin metrics and audit dashboard
  citation/                Citation demo UI

src/
  data/                    Dataset loading and normalization
  models/                  Deterministic, BART, Pegasus baseline providers
  evaluation/              Evaluation utilities where applicable

scripts/
  baseline and evaluation command-line utilities

docs/
  product, research, technical, and mentor-delivery documentation

data/evaluation/
  mock/de-identified sample data for testing and demo

deploy/k8s/
  Kubernetes deployment manifests for future deployment work
```

---

## 13. Cách chạy local demo

Local demo hiện được thiết kế cho development và mentor review.

### Bước 1 — Tạo môi trường

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-mlops.txt -r requirements-guardrails-onnx.txt
```

### Bước 2 — Setup local database

```powershell
$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

### Bước 3 — Chạy backend

```powershell
python -m uvicorn backend.app.main:app --reload --port 8080
```

### Bước 4 — Mở các trang demo

```text
OpenAPI:
http://127.0.0.1:8080/docs

Doctor UI:
http://127.0.0.1:8080/doctor-demo

Admin Dashboard:
http://127.0.0.1:8080/admin/dashboard

Evaluation & Demo Control Center:
http://127.0.0.1:8080/evaluation-demo

Citation Demo:
http://127.0.0.1:8080/citation-demo
```

---

## 14. Demo flow đề xuất

Video YouTube demo sẽ đi theo flow sau:

```text
1. Giới thiệu vấn đề: bác sĩ phải review nhiều dữ liệu bệnh án phân tán.
2. Giải thích hệ thống: trợ lý tóm tắt bệnh án có citation và doctor review.
3. Mở Doctor UI.
4. Chọn mock doctor role.
5. Mở patient list.
6. Chọn patient.
7. Generate draft summary.
8. Hiển thị claim-level citations.
9. Click citation để xem evidence.
10. Hiển thị safety panel và unsupported claim handling.
11. Start review.
12. Edit / approve / reject summary.
13. Mở Admin Dashboard.
14. Hiển thị metrics và audit log.
15. Mở Evaluation & Demo Control Center.
16. Giải thích functional validation và human evaluation design.
17. Giải thích trạng thái real EHR benchmark pending.
18. Tổng kết limitation và future work.
```

---

## 15. Pending items và future work

Dự án hiện là demo-ready MVP prototype, chưa phải production medical AI system.

Các phần pending hoặc future work bao gồm:

* credentialed real EHR benchmark bằng MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note;
* clinical expert evaluation;
* production SSO/OAuth;
* hardened RBAC;
* full HIS/EMR integration;
* SMART on FHIR integration;
* production security review;
* production audit retention policy;
* advanced retrieval evaluation;
* stronger wrong-patient retrieval tracking;
* broader clinical safety testing;
* real-world pilot với governed de-identified data.

---

## 16. Các câu hỏi mong muốn nhận feedback từ mentor

Em mong muốn nhận feedback từ mentor về các điểm sau:

1. Scope PRD hiện tại có phù hợp với kỳ vọng của internship evaluation không?
2. User Flow đã đủ rõ cho main clinical workflow chưa?
3. Việc tách product MVP, proxy model evaluation và pending real EHR benchmark như hiện tại đã rõ chưa?
4. Citation-first và doctor-in-the-loop workflow có phù hợp với định hướng của dự án không?
5. Trong tuần tiếp theo, em nên ưu tiên UI demo polish, BART/Pegasus evaluation, real structured EHR import hay survey/user validation?
6. Evaluation strategy hiện tại có chấp nhận được trong bối cảnh chưa có credentialed real EHR note data không?
7. Có rủi ro scope hoặc logic nào cần chỉnh trước final demo không?

---

## 17. Tóm tắt

Bản nộp tuần 1 cung cấp định hướng sản phẩm có cơ sở nghiên cứu và prototype triển khai sớm cho Medical Record Summarization MVP.

Dự án được xây dựng trên quan điểm rằng medical summarization không nên chỉ dừng ở việc sinh text. Một workflow an toàn và có giá trị hơn cần bao gồm:

```text
summary generation
+ citation evidence
+ unsupported claim detection
+ doctor review
+ audit logs
+ monitoring
+ evaluation
```

Repository hiện tại thể hiện tiến độ theo hướng đó, đồng thời tách rõ phần đã hoàn thành trong MVP với phần còn pending cho real EHR benchmark validation.
