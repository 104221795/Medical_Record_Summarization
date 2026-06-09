# Demo Video Script - Medical Record Summarization MVP

**Mục tiêu:** quay video nộp mentor/supervisor, trình bày rõ flow end-to-end của MVP/prototype.  
**Thời lượng gợi ý:** 10-14 phút.  
**Ngôn ngữ:** tiếng Việt, có thể đọc gần như nguyên văn.  
**Trọng tâm:** workflow, data, citation grounding, HITL, auditability, benchmark/evaluation.  

> Safety framing bắt buộc: Đây là MVP/prototype, không phải clinical product. Kết quả benchmark hiện tại là proxy/open benchmark, không chứng minh clinical safety hoặc real EHR performance.

## 0. Chuẩn Bị Trước Khi Quay

### Terminal 1 - Backend

```powershell
cd D:\MyNewDesktop\clin-summ
.\.venv\Scripts\Activate.ps1

$env:RAG_DATABASE_URL = "sqlite:///./var/clin_summ.db"
$env:HF_HOME = "D:\hf_cache"
$env:HF_HUB_CACHE = "D:\hf_cache\hub"
$env:HF_DATASETS_CACHE = "D:\hf_cache\datasets"
$env:TRANSFORMERS_CACHE = "D:\hf_cache\hub"
$env:RAG_EMBEDDING_PROVIDER = "sentence_transformers"
$env:RAG_SENTENCE_TRANSFORMERS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
python -m uvicorn backend.app.main:app --reload --port 8080
```

### Terminal 2 - Frontend

```powershell
cd D:\MyNewDesktop\clin-summ\frontend
npm run dev
```

### URLs Cần Mở Sẵn

```text
React app:
http://127.0.0.1:5173

API docs:
http://127.0.0.1:8080/docs

Admin benchmark dashboard:
http://127.0.0.1:5173/admin/evaluation/benchmark

Static evaluation fallback:
http://127.0.0.1:8080/evaluation-demo
```

### Nếu UI Chưa Cập Nhật

1. Restart backend.
2. Restart frontend dev server.
3. Nhấn `Ctrl + F5`.
4. Kiểm tra endpoint:

```powershell
$headers = @{
  "X-Tenant-ID" = "sandbox"
  "X-User-ID" = "clinical-admin-demo"
  "X-Role-Code" = "clinical_admin"
}

$r = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/api/v1/evaluation/benchmark/results" `
  -Headers $headers

$r.models | Where-Object { $_.model_provider -eq "pegasus_pubmed" }
```

Expected: có row `pegasus_pubmed`, `google/pegasus-pubmed`, `200/200`, ROUGE-L khoảng `0.2108`.

## 1. Opening - Giới Thiệu Dự Án

**Thời lượng:** 45-60 giây  
**Màn hình:** mở Home page hoặc README/report.  

### Thao Tác

1. Mở `http://127.0.0.1:5173`.
2. Show Home page.
3. Chuyển nhanh qua About page nếu cần.

### Lời Thoại Gợi Ý

```text
Đây là project Medical Record Summarization MVP. Mục tiêu là tạo một draft summary từ patient record hoặc clinical documents, nhưng khác với một model demo thông thường, hệ thống này được thiết kế theo hướng Clinical AI workflow.

AI summary ở đây không phải final clinical decision. Nó luôn là draft, cần bác sĩ review, kiểm tra citation, chỉnh sửa, approve hoặc reject. Hệ thống cũng ghi audit log và có dashboard đánh giá model/evaluation.
```

### Điểm Cần Nhấn Mạnh

- Đây là MVP/prototype.
- Không diagnosis/treatment/prescription recommendation.
- Không claim clinical performance.
- Focus là citation-grounded summarization + HITL + auditability.

## 2. Architecture Và Tech Stack

**Thời lượng:** 60-90 giây  
**Màn hình:** mở report Week 2 hoặc README architecture section.  

### Thao Tác

1. Mở `docs/delivery week 2/README.md`.
2. Show phần `Technology Stack Hiện Tại`.
3. Show Mermaid architecture diagram nếu trình Markdown render được.

### Lời Thoại Gợi Ý

```text
Về technical stack, frontend hiện dùng React, Vite và React Router. Backend là FastAPI, Pydantic, SQLAlchemy và Alembic. Database có thể chạy SQLite cho local quick check hoặc PostgreSQL cho setup gần production hơn.

Retrieval layer dùng sentence-transformers, default hiện tại là all-MiniLM-L6-v2. Provider layer gồm deterministic baseline, BART, Pegasus PubMed, Pegasus CNN/DailyMail, Pegasus XSum và Gemini ở dạng optional governed provider.

Điểm quan trọng là BART/Pegasus không dùng transformers pipeline cũ nữa, mà dùng AutoTokenizer, AutoModelForSeq2SeqLM và model.generate trực tiếp.
```

### Điểm Cần Nhấn Mạnh

- Stack đã có frontend/backend/database/evaluation.
- Provider layer tách khỏi UI workflow.
- Gemini optional, không fake benchmark.

## 3. Data Demo Và Evaluation Data

**Thời lượng:** 90 giây  
**Màn hình:** mở report hoặc file explorer.  

### Thao Tác

1. Show `data/processed/governance/benchmark_set.jsonl`.
2. Show một record mẫu hoặc đoạn trong report.
3. Show `docs/delivery week 2/README.md` phần Dataset Governance.

### Lời Thoại Gợi Ý

```text
Em tách data thành hai nhóm. Demo data dùng để chứng minh workflow end-to-end: patient list, patient detail, generate summary, citation panel, review, approve/reject và audit log. Data này không dùng để claim model performance.

Evaluation data hiện dùng MultiClinSum làm open/proxy benchmark. Sau preprocessing và governance, em có benchmark_set.jsonl với 25,902 benchmark-ready records.

Raw input ban đầu của MultiClinSum có thể là cặp file fulltext và summary. Importer ghép fulltext thành source_note và summary thành reference_summary, sau đó normalize về schema JSONL chuẩn gồm note_id, patient_id, encounter_id, source_note, reference_summary, dataset, split và metadata.

Sau đó governance layer thêm quality_score và route record vào benchmark_set, warning_set hoặc rejected_set. Chỉ benchmark_set mới được đưa vào model evaluation.
```

### Điểm Cần Nhấn Mạnh

- Demo data != evaluation data.
- MultiClinSum là proxy/open benchmark, không phải real EHR.
- MIMIC-IV-Note/BHC vẫn pending credentialed access.

## 4. Login Và Role-Based UI

**Thời lượng:** 45-60 giây  
**Màn hình:** React app login.  

### Thao Tác

1. Mở `/login`.
2. Login với role Doctor hoặc Admin.
3. Show sidebar thay đổi theo role.

### Lời Thoại Gợi Ý

```text
Frontend hiện có role-based UI. Doctor và Admin có navigation khác nhau. Đây vẫn là demo auth/prototype, chưa phải production SSO, nhưng đủ để chứng minh workflow theo vai trò.

Doctor tập trung vào patient workflow, summary generation và review evidence. Admin tập trung vào monitoring, dataset governance, benchmark results và audit logs.
```

### Điểm Cần Nhấn Mạnh

- Demo auth không phải production auth.
- Role-aware navigation đã có.

## 5. Doctor Flow - Patient Context

**Thời lượng:** 60-90 giây  
**Màn hình:** `/doctor/patients` và patient detail.  

### Thao Tác

1. Click Doctor -> Patients.
2. Mở một patient.
3. Show patient profile, encounter timeline, documents, summary history.

### Lời Thoại Gợi Ý

```text
Đây là Doctor workspace. Bác sĩ có thể xem danh sách bệnh nhân, mở patient detail, xem encounter timeline, source documents và summary history.

Mục tiêu là trước khi generate summary, người dùng vẫn thấy clinical context và evidence gốc, không chỉ thấy output của model.
```

### Điểm Cần Nhấn Mạnh

- UI không che source evidence.
- Workflow bắt đầu từ patient context, không bắt đầu từ prompt trống.

## 6. Generate Summary

**Thời lượng:** 90 giây  
**Màn hình:** `/doctor/generate-summary`.  

### Thao Tác

1. Click `Generate Summary`.
2. Chọn patient.
3. Chọn provider, tốt nhất demo bằng `deterministic` để ổn định.
4. Click generate.
5. Show draft preview.

### Lời Thoại Gợi Ý

```text
Ở bước generate summary, bác sĩ chọn patient và provider. Provider có thể là deterministic baseline, BART, Pegasus PubMed hoặc các provider khác nếu environment đã bật.

Trong demo em thường chọn deterministic để đảm bảo chạy nhanh và ổn định. Output sinh ra luôn là draft. Hệ thống không cho coi đây là final summary.

Sau khi generate, backend lưu model_run, summary, sections, claims và metadata liên quan.
```

### Điểm Cần Nhấn Mạnh

- Provider selection đã có.
- Draft only.
- Deterministic dùng cho demo ổn định.
- BART/Pegasus cần model/cache setup và `RUN_REAL_BASELINES=1`.

## 7. Review & Evidence - Citation Grounding

**Thời lượng:** 2 phút  
**Màn hình:** `/doctor/review` hoặc click `Review Evidence`.  

### Thao Tác

1. Mở Review & Evidence.
2. Load summary nếu cần.
3. Show left evidence/source panel.
4. Show center editable summary.
5. Show right citation/claim review panel.
6. Click citation hoặc unsupported claim tab.

### Lời Thoại Gợi Ý

```text
Đây là phần quan trọng nhất của Clinical AI workflow. Summary không đứng một mình. Mỗi claim quan trọng cần được match với citation hoặc bị flag là unsupported, insufficient evidence hoặc conflicting.

Bác sĩ có thể đọc source evidence, xem claim status, kiểm tra citation và chỉnh sửa summary trước khi approve.

Điểm thiết kế ở đây là hệ thống không cố ẩn uncertainty. Nếu evidence yếu hoặc thiếu, claim được đưa vào phần Needs Review để bác sĩ xử lý.
```

### Điểm Cần Nhấn Mạnh

- Citation grounding.
- Unsupported claims visible.
- Human review bắt buộc.
- Không autonomous clinical approval.

## 8. HITL Review - Edit / Approve / Reject

**Thời lượng:** 90 giây  
**Màn hình:** Review action bar.  

### Thao Tác

1. Click `Start Review`.
2. Edit summary text nhẹ nếu cần.
3. Click save/edit nếu có.
4. Approve hoặc Reject.
5. Nếu reject, chọn reason và comment.
6. Show outcome panel hoặc review history.

### Lời Thoại Gợi Ý

```text
HITL workflow cho phép bác sĩ start review, edit draft, approve hoặc reject. Nếu reject thì cần lý do như unsupported claim, wrong citation, missing critical info hoặc poor readability.

Các action này được persist và tạo audit log. Như vậy hệ thống có traceability, không chỉ generate text rồi bỏ qua quy trình lâm sàng.
```

### Điểm Cần Nhấn Mạnh

- Review actions persisted.
- Approve/reject có reason.
- Auditability.

## 9. Doctor Audit / Patient History

**Thời lượng:** 45-60 giây  
**Màn hình:** `/doctor/audit` hoặc Patient History.  

### Thao Tác

1. Mở Patient History.
2. Mở Audit History.
3. Show provider/status/review metadata nếu có.

### Lời Thoại Gợi Ý

```text
Doctor cũng có thể xem lại lịch sử summary và audit history. Điều này giúp workflow có trace, biết summary nào được generate bằng provider nào, ai review, trạng thái hiện tại là gì.
```

## 10. Admin Dashboard - Monitoring

**Thời lượng:** 90 giây  
**Màn hình:** `/admin/dashboard`.  

### Thao Tác

1. Chuyển sang Admin role.
2. Mở Admin Dashboard.
3. Show summary generated, approvals, rejections.
4. Show provider readiness chart.
5. Show dataset readiness chart.
6. Show latest benchmark status.

### Lời Thoại Gợi Ý

```text
Admin dashboard dùng để theo dõi operational status: số summary, approval/rejection, provider readiness, dataset readiness và latest benchmark status.

Ở đây em cũng hiển thị benchmark-ready records hiện tại là 25,902 từ governed MultiClinSum set.
```

### Điểm Cần Nhấn Mạnh

- Admin view là read-only monitoring.
- Không expose raw PHI.
- Dataset readiness và provider readiness tách biệt.

## 11. Dataset Governance Page

**Thời lượng:** 60-90 giây  
**Màn hình:** `/admin/datasets`.  

### Thao Tác

1. Open Dataset Governance.
2. Show MultiClinSum, Synthea/SyntheticMass, MTS-Dialog/MEDIQA-Sum, MIMIC-IV.
3. Mention benchmark/warning/rejected sets.

### Lời Thoại Gợi Ý

```text
Dataset governance page giải thích rõ vai trò từng dataset. MultiClinSum là primary open proxy benchmark cho summarization. Synthea hoặc SyntheticMass phù hợp hơn cho ingestion/FHIR validation. MTS-Dialog và MEDIQA-Sum là future cross-dataset benchmark. MIMIC-IV-Note hoặc MIMIC-IV-BHC là future real EHR benchmark và cần credentialed access.

Điểm quan trọng là hệ thống không trộn demo data với evaluation data và không gọi proxy benchmark là real EHR performance.
```

## 12. Evaluation Overview

**Thời lượng:** 90 giây  
**Màn hình:** `/admin/evaluation`.  

### Thao Tác

1. Open Evaluation page.
2. Show best official model.
3. Show ROUGE leaderboard chart.
4. Show records evaluated chart.
5. Show provider domain fit.
6. Show failure pattern summary.

### Lời Thoại Gợi Ý

```text
Evaluation overview cho thấy kết quả proxy benchmark theo model. Hiện tại BART đang có ROUGE-L tốt nhất trong medium run, còn Pegasus PubMed có domain fit tốt hơn cho medical/scientific text nhưng chưa vượt BART trong kết quả hiện tại.

Dashboard cũng không fake Gemini. Gemini chỉ được xem là official nếu có completed benchmark records và governance config rõ ràng.
```

### Điểm Cần Nhấn Mạnh

- BART best current ROUGE-L.
- Pegasus PubMed có 200/200 predictions.
- Gemini không fake.

## 13. Benchmark Results

**Thời lượng:** 2 phút  
**Màn hình:** `/admin/evaluation/benchmark`.  

### Thao Tác

1. Open Benchmark Results.
2. Show selected output directory.
3. Show Pegasus PubMed card.
4. Show ROUGE chart.
5. Show prediction files.
6. Show benchmark folder discovery.
7. Show model comparison table.

### Lời Thoại Gợi Ý

```text
Benchmark dashboard đọc artifacts từ D:\clin_summ_outputs\medium_benchmark_bart_pegasus.

Các file chính gồm model_comparison.csv, per_record_metrics.csv, prediction JSONL cho deterministic, BART, Pegasus, Pegasus PubMed, Pegasus CNN/DailyMail, failure_analysis.md và EVALUATION_REPORT.md.

Pegasus PubMed không nằm trong CSV cũ ban đầu, nên backend hiện đã merge thêm kết quả từ pegasus_pubmed_predictions.jsonl. Hiện row này có 200/200 records và ROUGE-L khoảng 0.2108.

Current snapshot: BART có ROUGE-L khoảng 0.2533, Pegasus PubMed khoảng 0.2108, deterministic khoảng 0.2407. Đây là proxy benchmark, không phải clinical performance.
```

### Điểm Cần Nhấn Mạnh

- Output thật, không fake.
- Prediction file availability.
- Proxy evaluation warning.
- Artifacts traceable.

## 14. API Docs Quick Glance

**Thời lượng:** 45 giây  
**Màn hình:** `http://127.0.0.1:8080/docs`.  

### Thao Tác

1. Show OpenAPI docs.
2. Point to major route groups.

### Lời Thoại Gợi Ý

```text
Backend API được expose qua FastAPI OpenAPI docs. Các route chính gồm patients, documents, summaries, review workflow, audit logs, metrics, providers và evaluation.

Điều này giúp project không chỉ là frontend demo mà có API surface rõ ràng để mở rộng.
```

## 15. Current Limitations

**Thời lượng:** 60 giây  
**Màn hình:** report hoặc README limitations.  

### Lời Thoại Gợi Ý

```text
Hiện tại hệ thống vẫn là MVP/prototype. Production SSO/OAuth, HIS/EMR writeback và real EHR benchmark vẫn chưa hoàn thiện.

Benchmark hiện dùng MultiClinSum open/proxy data, chưa phải real EHR benchmark. MIMIC-IV-Note hoặc MIMIC-IV-BHC cần credentialed access và governance approval.

Metric hiện tại chủ yếu là ROUGE và latency. Bước tiếp theo cần chuẩn hóa BERTScore, citation coverage, unsupported claim rate, factuality, faithfulness và human evaluation rubric.
```

### Điểm Cần Nhấn Mạnh

- Nói thẳng hạn chế.
- Không quảng cáo quá đà.
- Next step là metrics/evaluation quality.

## 16. Closing

**Thời lượng:** 45-60 giây  
**Màn hình:** report conclusion hoặc dashboard.  

### Lời Thoại Gợi Ý

```text
Tóm lại, project đã vượt yêu cầu ban đầu của tuần 1. Từ PRD và workflow, em đã phát triển thành một MVP/prototype có frontend, backend, database schema, provider layer, citation grounding, HITL review, auditability, dataset governance và benchmark dashboard.

Giai đoạn tiếp theo em sẽ tập trung vào validation định lượng: chuẩn hóa dataset manifest, mở rộng benchmark lên 500+ records, thêm BERTScore và factuality metrics, đưa citation coverage và unsupported claim rate vào report, và hoàn thiện PoC end-to-end.

Mục tiêu cuối cùng là chứng minh hệ thống không chỉ generate summary, mà còn có thể được đo lường, review và kiểm soát rủi ro theo đúng hướng Clinical AI.
```

## Short Version - Nếu Chỉ Có 5 Phút

1. Opening: Medical Record Summarization MVP, draft only, citation-grounded, HITL.
2. Architecture: React + FastAPI + SQLAlchemy + provider gateway + evaluation artifacts.
3. Doctor flow: patient -> generate summary -> review evidence -> approve/reject.
4. Admin flow: dashboard -> dataset governance -> evaluation -> benchmark results.
5. Data/evaluation: 25,902 MultiClinSum benchmark-ready records, BART/Pegasus PubMed proxy benchmark.
6. Limitations: not clinical product, not real EHR benchmark, next step metrics/factuality/human evaluation.

## Những Câu Nên Tránh Khi Quay

Không nói:

```text
Model này đã đủ an toàn lâm sàng.
Kết quả này chứng minh hiệu quả trên EHR thật.
AI có thể tự approve summary.
Gemini/BART/Pegasus tốt hơn bác sĩ.
```

Nên nói:

```text
Đây là proxy evaluation.
Output là draft cần bác sĩ review.
MultiClinSum là open/proxy benchmark, không phải real EHR.
Real EHR evaluation cần MIMIC-IV credentialed access và governance approval.
```

## Checklist Trước Khi Submit Video

- [ ] Backend chạy ở port 8080.
- [ ] Frontend chạy ở port 5173.
- [ ] Login Doctor được.
- [ ] Generate Summary chạy được với deterministic.
- [ ] Review & Evidence mở được.
- [ ] Approve/reject tạo outcome.
- [ ] Admin Dashboard load được.
- [ ] Benchmark Results hiển thị Pegasus PubMed.
- [ ] Proxy warning được nhắc trong video.
- [ ] Không claim real clinical performance.
