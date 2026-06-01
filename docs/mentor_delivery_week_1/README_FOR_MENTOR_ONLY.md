# Mentor README — Week 1 Delivery

## 1. Project Overview

**Project:** Medical Record Summarization MVP
**Positioning:** Citation-grounded clinical documentation assistant with clinician review
**Week 1 focus:** PRD, User Flow, safety boundary, research framing and evaluation strategy

Dự án này xây dựng một **production-style MVP prototype** cho hệ thống hỗ trợ tóm tắt bệnh án. Hệ thống không phải medical device, không phải autonomous clinician, không phải diagnosis system, không phải treatment recommendation system, và không phải production HIS/EMR integration.

Hệ thống được định vị là một **clinical documentation support prototype**: AI-generated summaries luôn ở trạng thái **draft** cho đến khi được bác sĩ có thẩm quyền review, edit, approve hoặc reject.

Core safety boundary:

> Dự án chỉ đánh giá những gì có thể được đánh giá hợp lệ ở mức dữ liệu hiện tại, đồng thời giữ các claim về real EHR note-level benchmark cho giai đoạn tương lai khi có credentialed datasets phù hợp.

---

## 2. Week 1 Executive Summary

Week 1 tập trung vào việc xác định **product scope** và **clinical workflow** cho một hệ thống tóm tắt bệnh án có kiểm soát. Đóng góp chính của Week 1 không chỉ là mô tả một AI model tạo summary, mà là thiết kế một **controlled clinical documentation lifecycle**:

```text
source clinical data
→ draft AI summary
→ claim/citation verification
→ unsupported claim visibility
→ doctor review
→ approve/reject
→ audit log
→ evaluation and monitoring
```

Luận điểm trung tâm của dự án:

> Medical summarization không chỉ là bài toán sinh văn bản. Trong y tế, summarization là bài toán về trust, verification, accountability và workflow integration.

Vì vậy, hệ thống tập trung vào:

* citation-grounded draft summaries;
* unsupported claim flags;
* doctor-in-the-loop review;
* auditability;
* role-based responsibilities;
* multi-layer evaluation strategy.

---

## 3. What Week 1 Delivers

Week 1 deliverables được chia thành ba nhóm.

### 3.1 Required Week 1 Deliverables

| Deliverable          | Purpose                                                                                            | Status    |
| -------------------- | -------------------------------------------------------------------------------------------------- | --------- |
| PRD                  | Xác định product scope, user, requirements, data strategy, evaluation direction và risk boundaries | Completed |
| User Flow / Workflow | Mô tả Doctor Golden Path, citation verification, HITL review, audit và role-based flow             | Completed |

### 3.2 Supporting Research / Design Documents

| Document                                 | Purpose                                                                |
| ---------------------------------------- | ---------------------------------------------------------------------- |
| Evaluation Plan                          | Giải thích multi-layer evaluation strategy và giới hạn claim           |
| Research Background and Gaps             | Làm rõ research motivation, gaps và contribution                       |
| Survey Plan                              | Xác thực problem perception, trust requirement và workflow assumptions |
| Golden Path UI                           | Mô tả UI flow theo hướng clinical workflow                             |
| Hallucination Mitigation Plan            | Xác định safety risks, hallucination types và mitigation strategy      |
| Role-Based UI                            | Làm rõ permission boundaries và accountability                         |
| Dataset Strategy and Research Evaluation | Phân tầng dataset, allowed claims và benchmark logic                   |
| Hybrid Input Normalization               | Giải thích hướng xử lý messy clinical input                            |

### 3.3 Early Prototype / Ahead-of-Schedule Work

Nếu repo hiện có `/demo-console`, backend, citation flow, HITL review, audit log hoặc Evaluation Center, các phần này nên được hiểu là **early workflow feasibility evidence**, không phải claim rằng hệ thống đã production-ready.

---

## 4. What This Project Is Not Claiming

Week 1 **không claim**:

* hệ thống đã đạt real EHR benchmark performance;
* hệ thống đã được clinical validation;
* hệ thống có khả năng chẩn đoán;
* hệ thống có khả năng khuyến nghị điều trị;
* BART/Pegasus đã được clinically validated;
* MultiClinSum là real EHR benchmark;
* mock/de-identified demo data chứng minh clinical model performance;
* hệ thống đã sẵn sàng production deployment;
* hệ thống đã đạt chuẩn certified medical device.

---

## 5. Recommended Review Order

Mentor nên review theo thứ tự sau:

1. `01_PRD_V1_MEDICAL_RECORD_SUMMARIZATION.md`
2. `02_USER_FLOW_V1.md`
3. `03_EVALUATION_PLAN_V1.md`
4. `04_RESEARCH_BACKGROUND_AND_GAPS.md`
5. `09_DATASET_STRATEGY_AND_RESEARCH_EVALUATION.md`
6. `10_HYBRID_INPUT_NORMALIZATION_AND_EVALUATION.md`
7. `07_HALLUCINATION_MITIGATION_V1.md`
8. `06_GOLDEN_PATH_UI_V1.md`
9. `08_ROLE_BASED_UI.md`
10. `05_SURVEY_PLAN.md`

Lý do: PRD và User Flow là deliverables chính. Các tài liệu còn lại giải thích chiều sâu nghiên cứu, safety logic và evaluation boundary.

---

## 6. Evidence Ladder

Dự án không xem mọi dataset là bằng chứng cho cùng một claim. Mỗi loại dữ liệu chỉ hỗ trợ một mức evidence nhất định.

| Level         | Evidence source                  | What it validates                                                                            | What it does not validate                           |
| ------------- | -------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| A             | Mock/de-identified demo data     | Product workflow, UI/API routing, citation display, review status, audit events              | Clinical model performance                          |
| B             | MIMIC-III demo structured data   | Structured EHR ingestion and mapping for patients, encounters, labs, diagnoses, medications  | Note-level summarization quality                    |
| C.1           | MultiClinSum                     | Primary open clinical summarization benchmark with source/reference pairs                    | Real hospital EHR note performance                  |
| C.2           | MTS-Dialog                       | Auxiliary dialogue-to-note section proxy evaluation                                          | Full medical record summarization                   |
| C.3           | ACI-BENCH                        | Optional full-visit dialogue-to-note proxy evaluation                                        | Real EHR discharge-note benchmark                   |
| Normalization | BIOMEDNLP/mtsamples_clean        | Messy clinical transcription normalization and chunking robustness                           | Main supervised summarization benchmark performance |
| D             | MIMIC-IV-Ext-BHC / MIMIC-IV-Note | Future real EHR note-level benchmark after credentialed access                               | Available in Week 1                                 |
| E             | Human evaluation                 | Perceived usefulness, factuality review, readability, citation usefulness, safety perception | Fully automated clinical validation                 |

---

## 7. Current Layer C Strategy

| Layer                     | Dataset                   | Role                                                                                            |
| ------------------------- | ------------------------- | ----------------------------------------------------------------------------------------------- |
| Layer C.1                 | MultiClinSum              | Primary open clinical summarization benchmark for Pegasus/BART evaluation                       |
| Layer C.2                 | MTS-Dialog                | Auxiliary dialogue-to-note section proxy evaluation                                             |
| Layer C.3                 | ACI-BENCH                 | Optional auxiliary full-visit dialogue-to-note proxy evaluation                                 |
| Normalization stress test | BIOMEDNLP/mtsamples_clean | Messy medical transcription normalization only; not the main supervised summarization benchmark |

Older references to OPI/D2N/CHQ as the main Layer C strategy should be treated as historical or optional context. Week 1 now uses the clearer MultiClinSum/MTS-Dialog/ACI-BENCH split.

---

## 8. What Current Results Mean / Do Not Mean

### 8.1 Current results can mean

Nếu deterministic evaluation, importer hoặc dry-run đã chạy, các kết quả đó có thể cho thấy:

* processed MultiClinSum path có thể tạo source/reference pairs cho small proxy evaluation run;
* deterministic baseline runner có thể generate local outputs không cần model downloads;
* ROUGE metrics có thể được tính và ghi ra JSON/CSV/Markdown artifacts;
* optional BERTScore đã được thiết kế như semantic metric nếu dependency/model có sẵn;
* BART/Pegasus có thể được kiểm tra bằng readiness hoặc dry-run path trước khi tải model thật.

### 8.2 Current results do not mean

Các kết quả hiện tại **không có nghĩa là**:

* MultiClinSum là real EHR benchmark;
* MTS-Dialog là real EHR benchmark;
* mtsamples_clean là main supervised summarization benchmark;
* mock/de-identified data chứng minh clinical model performance;
* BART/Pegasus đã được clinically validated;
* hệ thống sẵn sàng real EMR writeback;
* hệ thống có khả năng chẩn đoán hoặc khuyến nghị điều trị.

---

## 9. Week 1 Mentor Narrative



> Week 1 tập trung vào việc thiết kế một hướng MVP thận trọng về mặt clinical AI. Summary do AI tạo ra chỉ là draft; các claim quan trọng cần citation hoặc phải được flag nếu thiếu bằng chứng; doctor review vẫn là bắt buộc. Evaluation được chia thành nhiều tầng để tránh overclaim: mock data dùng để validate workflow, MIMIC-III demo dùng cho structured EHR mapping, MultiClinSum dùng cho open clinical summarization benchmark, MTS-Dialog là auxiliary dialogue-to-note dataset, mtsamples_clean dùng để stress test input normalization, còn real EHR benchmark được giữ cho giai đoạn tương lai với MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.

---

## 10. Mentor Q&A

### 1. Is this a diagnosis system?

No. Hệ thống không chẩn đoán, không khuyến nghị điều trị và không kê đơn. Nó chỉ hỗ trợ tạo draft clinical documentation summaries từ dữ liệu đã có.

### 2. What makes this different from a chatbot?

Khác biệt chính là hệ thống có structured workflow: patient context, source documents, draft summary, claim-level citation, safety panel, HITL review, audit log và evaluation center. Chatbot thường chỉ sinh text; hệ thống này quản lý lifecycle của clinical documentation output.

### 3. What happens if AI hallucinates?

Claim thiếu bằng chứng sẽ được flag là unsupported hoặc insufficient evidence. High-risk claims cần citation hoặc doctor review. Summary không được xem là final cho đến khi doctor approve.

### 4. Why use MultiClinSum?

MultiClinSum có source/reference summary pairs phù hợp cho Pegasus/BART evaluation bằng ROUGE và BERTScore. Nó là lựa chọn chính cho Layer C vì mentor requirement có BERT/Pegasus và evaluation.

### 5. Why not call MultiClinSum a real EHR benchmark?

Vì MultiClinSum là open clinical summarization benchmark, không phải credentialed real EHR note-level benchmark như MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note. Nó hữu ích cho proxy/open benchmark, nhưng không chứng minh production EHR performance.

### 6. Why keep MTS-Dialog as auxiliary?

MTS-Dialog kiểm tra dialogue-to-note-section behavior. Task này liên quan đến clinical documentation nhưng khác với source-note-to-summary evaluation, nên nó nằm ở Layer C.2 thay vì thay thế MultiClinSum.

### 7. Why use mtsamples_clean for normalization only?

mtsamples_clean chứa medical transcription-style text có format không đồng nhất. Nó hữu ích để test section detection, difficult-case routing và safe normalization, nhưng không phải main supervised summarization benchmark nếu không có reliable reference summaries.

### 8. What does BERT do here?

BERT-style models được dùng cho semantic evaluation, đặc biệt là BERTScore hoặc claim-source similarity. BERT không phải main generator trong summarization pipeline.

### 9. What do Pegasus and BART do here?

Pegasus và BART là abstractive summarization baselines cho Layer C benchmark evaluation. Real model loading nên bị tắt mặc định, trừ khi người dùng bật rõ bằng `--allow-model-downloads` hoặc `RUN_REAL_BASELINES=1`.

### 10. What does Gemini do here?

Gemini có thể đóng vai trò product LLM provider hoặc controlled difficult-case input normalization assistant. Khi dùng cho normalization, Gemini chỉ được classify/normalize/extract source-backed sections; không được tự thêm facts, chẩn đoán hoặc recommend treatment.

### 11. Why is LLM-assisted normalization controlled?

Vì messy clinical text có thể hưởng lợi từ LLM, nhưng LLM cũng có rủi ro hallucination. Raw text phải luôn là source of truth, normalized sections phải giữ `source_text`, và Gemini chỉ nên được gọi cho difficult cases khi explicit allowed và có giới hạn số lần gọi.

### 12. What remains future work?

Future work gồm credentialed MIMIC-IV-Ext-BHC/MIMIC-IV-Note evaluation, clinician-led human evaluation, stronger citation/factuality scoring, production RBAC/SSO, EMR/FHIR writeback governance và broader clinical safety testing.

---

## 11. Current Local Validation Commands

Targeted Week 1 tests:

```powershell
python -m pytest backend/tests/test_multiclinsum_importer.py backend/tests/test_mtsamples_importer.py backend/tests/test_mts_dialog_importer.py backend/tests/test_summarization_baseline_runner.py backend/tests/test_semantic_metrics.py -q
```

MultiClinSum import with auto-detected zip:

```powershell
python -m backend.app.evaluation.datasets.multiclinsum_importer --limit 20
```

Deterministic proxy baseline:

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model deterministic `
  --limit 5 `
  --include-bertscore
```

Pegasus readiness dry-run:

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model pegasus `
  --limit 3 `
  --dry-run
```

Real Pegasus should only be run intentionally:

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model pegasus `
  --limit 3 `
  --allow-model-downloads `
  --include-bertscore
```

---

## 12. Week 2  Next Steps (dự định tuần tiếp theo)

1. Finalize MultiClinSum importer and run small Layer C.1 evaluation.
2. Run deterministic baseline first, then Pegasus/BART dry-run.
3. Run Pegasus/BART real smoke test only with explicit model download permission.
4. Add or refine MTS-Dialog importer as Layer C.2 auxiliary evaluation.
5. Use mtsamples_clean for normalization stress test.
6. Add human evaluation form/report if not already complete.
7. Continue avoiding any real EHR benchmark claim until credentialed MIMIC-IV-Ext-BHC/MIMIC-IV-Note access is available.
