# Báo cáo bàn giao Week 5 — Hoàn thiện P0, P1 và P2

> **Ranh giới sử dụng:** Đây là demo-ready local staging PoC trên dữ liệu
> mock/đã khử định danh. AI-generated summary luôn là bản nháp chỉ dành cho
> clinician review. Các kết quả dưới đây là proxy evaluation; không chứng minh
> an toàn lâm sàng, hiệu quả lâm sàng, hiệu năng healthcare thực tế hoặc
> production HIS/EMR integration.

## 1. Executive Summary

Week 5 đã chuyển dự án từ “PoC có nhiều thành phần tốt” thành một gói bàn giao
có thể demo, kiểm tra và giải thích end-to-end:

- P0 hoàn tất phần tự động hóa evidence cho local Docker Compose staging,
  health/readiness, tests, frontend build, Docker build và portable Flow 2.1.
- P1 hoàn tất post-hoc data-diversity analysis trên đúng 50 records, xây failure
  taxonomy, phân tích hai retrieval-gate cases và tạo blinded human-review pack.
- P2 hoàn tất metric-correlation analysis, reference-distance proxy, historical
  flow comparison và retrieval-threshold sensitivity mà không chạy lại model.
- Demo/runbook, human-evaluation protocol và case study đã được chuẩn hóa để
  reviewer hiểu nhanh điều hệ thống làm được, chưa làm được và bằng chứng ở đâu.

Không thêm provider, không chạy lại benchmark nặng và không thay đổi các metric
đã ghi nhận. Feature scope nên được freeze trước final demonstration.

## 1.1 Reviewer Summary

| Hạng mục | Trạng thái |
| --- | --- |
| Overall | Demo-ready local staging PoC |
| P0 | Automated evidence capture hoàn tất; UI screenshots, video và SharePoint là thao tác thủ công còn lại |
| P1 | Diversity/failure/gate analysis và blinded 12-case human-review package đã hoàn tất |
| P2 | Correlation, historical flow comparison và threshold sensitivity đã hoàn tất |
| Runtime | Docker Compose app/db/Redis/RQ worker hoạt động; `/health` và `/ready` HTTP 200 |
| Flow 2.1 | No-gate: 50 records x 5 providers, 250/250 outputs; gated: 50 evaluated, 48 generated và 2 intentionally blocked/provider |
| Human evaluation | Protocol/package ready; chưa có và không giả lập điểm reviewer thật |
| Safety | Draft-only, clinician-review-only, proxy evaluation |
| Next action | Ghi hình demo, chụp UI evidence, mời reviewer thật và đóng gói artifact đã kiểm tra PHI/secrets |

## 2. Phạm vi P0–P2

| Priority | Mục tiêu | Kết quả |
| --- | --- | --- |
| P0 | Làm final PoC chạy lặp lại được và có evidence | Hoàn tất phần code/tự động; phần cần thao tác người dùng được liệt kê rõ |
| P1 | Đi sâu data diversity, failure analysis, gate behavior và human review | Hoàn tất post-hoc analysis và review package |
| P2 | Kiểm tra quan hệ metric, flow trade-off, edit proxy và gate threshold | Hoàn tất với interpretation boundaries |

## 3. P0 — Demo readiness và evidence

### 3.1 Trạng thái kiểm chứng ngày 2026-06-22

| Check | Kết quả |
| --- | --- |
| Backend full suite hiện tại | 172 passed, 0 failed; 2 dependency deprecation warnings |
| Backend lightweight verification | 37 passed, 0 failed; 2 dependency deprecation warnings |
| Frontend production build | Passed; Vite transformed 1,866 modules |
| Docker build | Passed |
| Docker Compose | App healthy; PostgreSQL healthy; Redis và RQ worker running |
| `/health` | HTTP 200 |
| `/ready` | HTTP 200; overall `degraded` chỉ do local vector store chưa cấu hình remote, các check bắt buộc pass |
| Runtime image | 122,268,908 bytes, khoảng 122.27 MB |
| Portable Admin Flow 2.1 | 5 providers, 250 completed outputs, BERTScore ở cả 5 providers, proxy warning hiện diện |

Evidence index:

```text
artifacts/demo_evidence/2026-06-22/EVIDENCE_SUMMARY.md
docs/demo/FINAL_DEMO_AND_PRESENTATION_RUNBOOK.md
docs/demo/DEMO_EVIDENCE_PACKAGE.md
```

Kết quả Week 4 `165 passed` và deployment-focused `19 passed` vẫn là historical
delivery evidence riêng. Current Week 5 verification được ghi riêng là
`172 passed` cho full suite và `37 passed` cho lightweight suite.

### 3.2 Điều đã được harden

- Artifact resolver ưu tiên `RAG_EVALUATION_ARTIFACT_ROOT`, sau đó dùng
  repository-relative `artifacts/evaluation`; đường dẫn D-drive chỉ là legacy fallback.
- Docker Compose mount portable evaluation artifacts read-only cho Admin pages.
- Staging readiness kiểm tra database, artifacts, providers, jobs và configuration.
- Local demo account có bootstrap path riêng, không commit password.
- Runtime image giữ lightweight boundary, không đóng gói Torch, Transformers,
  sentence-transformers, BERTScore, MLflow, CUDA hoặc NVIDIA packages.

### 3.3 Việc P0 còn cần con người thực hiện

- Chụp doctor workflow, evidence panel, audit trail và Admin Flow 2.1.
- Ghi video 12–15 phút theo runbook.
- Kiểm tra video/artifact không chứa PHI, password hoặc token.
- Upload và kiểm tra quyền SharePoint nếu chương trình yêu cầu.

Đây không phải thiếu implementation; đây là các bước evidence capture không thể
được thay bằng dữ liệu giả.

## 4. P1 — Data diversity, provider failures và human review

### 4.1 Diversity design

50 records được phân tích theo:

- source length;
- diagnosis density;
- medication density;
- timeline complexity;
- retrieval quality;
- heuristic difficulty.

Difficulty score kết hợp percentile rank của bốn đặc trưng nguồn và retrieval
warning/failure, sau đó chia gần cân bằng:

| Difficulty | Records | Mean source tokens |
| --- | ---: | ---: |
| Easy | 17 | 512.8235 |
| Medium | 16 | 565.8125 |
| Hard | 17 | 636.4706 |

Qwen2.5 không có quan hệ omission đơn điệu theo difficulty: omission proxy là
`0.5577` ở easy, `0.3796` ở medium và `0.3849` ở hard. Vì vậy source complexity
và output risk cần được xem là hai chiều khác nhau; không được mặc định
“record khó hơn luôn tạo output tệ hơn”.

### 4.2 Kết quả provider ở run 50/50 no-gate

| Provider | ROUGE-L | BERTScore F1 | Citation coverage | Factuality proxy | Timeline completeness | Hallucinated entity count | Critical omission |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Deterministic | 0.1737 | 0.7952 | 0.9147 | 0.9071 | 0.6667 | 0.00 | 0.3688 |
| BART | 0.0757 | 0.8010 | 0.1307 | 0.7585 | 0.0645 | 0.00 | 0.9583 |
| Pegasus | 0.1495 | 0.8232 | 0.3800 | 0.7626 | 0.1290 | 0.02 | 0.9236 |
| Qwen2.5 | 0.2122 | 0.8391 | 0.8884 | 0.8713 | 0.4785 | 0.48 | 0.4460 |
| Llama3.2 | 0.1863 | 0.8149 | 0.8620 | 0.8413 | 0.4570 | 1.30 | 0.5108 |

Diễn giải:

- Qwen2.5 là generative provider mạnh nhất trong proxy run này theo ROUGE-L,
  BERTScore và cân bằng grounding tổng thể.
- Deterministic có citation coverage, factuality proxy, timeline completeness
  và omission proxy tốt nhất; đây là smoke/control provider đáng tin cậy nhất.
- BART/Pegasus vẫn có giá trị làm baseline nhưng yếu trong strict
  citation-first workflow.
- Llama3.2 có output tốt hơn các seq2seq baseline ở nhiều metric nhưng failure
  analysis báo hallucinated-content signal cao hơn.

### 4.3 Failure taxonomy

Ba failure category nổi bật nhất theo provider:

| Provider | Tín hiệu chính |
| --- | --- |
| BART | Retrieval-related 70%; missing timeline 58%; source limitation 52% |
| Deterministic | Không phát hiện major proxy failure 64%; retrieval-related 28%; missing diagnosis 24% |
| Pegasus | Retrieval-related 58%; missing timeline 54%; missing diagnosis 42% |
| Qwen2.5 | Hallucinated content 38%; no-major-failure 38%; missing timeline 28% |
| Llama3.2 | Hallucinated content 84%; retrieval-related 30%; missing timeline 28% |

Các nhãn này là rule/proxy signals để tìm case cần review, không phải chẩn đoán
chất lượng lâm sàng cuối cùng.

### 4.4 Retrieval gate behavior

Gated run đánh giá đủ 50 records nhưng chặn:

- `multiclinsum_ls_en_10012`: Recall@5 `1.0`, MRR `1.0`;
- `multiclinsum_ls_en_10018`: Recall@5 `0.8333`, MRR `1.0`.

Cả hai thiếu extracted `DIAGNOSIS` evidence và bị chặn ở cả năm provider. Đây là
section-aware evidence boundary: generic retrieval score cao vẫn chưa đủ nếu
loại evidence bắt buộc vắng mặt.

No-gate run vẫn được giữ riêng để tạo đủ 250/250 outputs. Nó không phủ nhận gate;
hai run phục vụ hai mục đích đánh giá khác nhau.

### 4.5 Human evaluation

Đã tạo 12-case blinded package, gồm hai gate cases, high-risk/low-risk Qwen cases
và các case có provider disagreement. Score sheet bao phủ factual correctness,
clinical completeness, citation usefulness, readability, conciseness,
hallucination risk, approve/edit/reject, edit minutes và critical errors.

Không có điểm nào được AI tự điền. Trạng thái chính xác là **review package
ready, real reviewer scoring pending**.

## 5. P2 — Metric interpretation và policy sensitivity

### 5.1 BERTScore không thay thế grounding

Phân tích provider-level chỉ có `n=5`, nên chỉ dùng để phát hiện rank
disagreement:

| Quan hệ | Pearson | Spearman |
| --- | ---: | ---: |
| BERTScore vs ROUGE-L | 0.5682 | 0.5000 |
| BERTScore vs citation coverage | 0.2190 | -0.1000 |
| BERTScore vs factuality proxy | -0.0188 | -0.1000 |
| BERTScore vs critical omission | -0.0727 | 0.1000 |

BERTScore cao hơn không đồng nghĩa citation tốt hơn hoặc omission thấp hơn.
Không có kiểm định significance đáng tin cậy với năm provider.

### 5.2 Historical flow comparison

Trên 50 note/provider rows chung:

- Deterministic từ Flow 1 đến Flow 2.1 tăng citation coverage
  `0.0133 → 0.9147` và giảm omission `0.7701 → 0.3688`.
- BART có citation `0.8500` ở Flow 1.5 nhưng giảm còn `0.1307` trong Flow 2.1,
  đồng thời omission là `0.9583`.
- Pegasus có citation gần `0.98` ở Flow 1.5/2 nhưng còn `0.3800` ở Flow 2.1,
  omission là `0.9236`.

Đây là historical comparative evidence, không phải randomized ablation:
prompt, model/configuration và pipeline context giữa các run không hoàn toàn
đồng nhất. Kết luận đúng là provider có tương tác mạnh với flow/prompt; không
phải “RAG luôn cải thiện mọi model”.

### 5.3 Retrieval threshold sensitivity

Post-hoc reclassification cho Qwen2.5:

| Recall@5 cutoff | Eligible | Blocked | Citation | Factuality proxy | Critical omission |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50 | 48 | 2 | 0.8907 | 0.8660 | 0.4587 |
| 0.67 | 44 | 6 | 0.8878 | 0.8685 | 0.4627 |
| 0.80 | 44 | 6 | 0.8878 | 0.8685 | 0.4627 |
| 0.90 | 38 | 12 | 0.9005 | 0.8820 | 0.4167 |
| 1.00 | 38 | 12 | 0.9005 | 0.8820 | 0.4167 |

Cutoff cao hơn có thể tăng proxy quality trên tập còn lại nhưng giảm coverage
từ 48 xuống 38 records. Bảng này không chạy lại retrieval/generation nên chưa
đủ để chọn threshold triển khai.

### 5.4 Edit proxy

`reference_edit_proxy.csv` dùng textual distance giữa output và reference để
sampling. Nó không phải clinician edit distance, không phải edit time và không
được dùng làm bằng chứng workflow efficiency cho đến khi có reviewer thật.

## 6. Evidence-first interpretation: vì sao giữ RAG khi Raw có ROUGE cao hơn?

Benchmark lịch sử cho thấy Raw có ROUGE-L cao hơn Flow 2/2.1 ở deterministic,
BART và Pegasus. Đây là kết quả hợp lý vì source hiện tại chỉ khoảng 500–600
tokens: model Raw có thể nhìn gần như toàn bộ note, trong khi RAG tạo thêm các
điểm có thể mất thông tin như section detection, chunking, embedding, query,
top-k và retrieval gate.

RAG trong dự án không được tối ưu với lời hứa “luôn tăng ROUGE”. Nó được tối ưu
cho evidence-first doctor workflow:

- claim truy ngược được về đúng source chunk;
- retrieval giới hạn theo tenant, patient và encounter;
- unsupported/conflicting evidence vẫn hiện cho bác sĩ;
- missing evidence được coi là unknown, không phải absent;
- hệ thống có thể từ chối generation nếu thiếu evidence bắt buộc;
- review và approval có thể audit.

Deterministic minh họa trade-off này rõ nhất: từ Raw đến Flow 2.1, ROUGE-L giảm
`0.2407 → 0.1737`, nhưng citation coverage tăng `0.0133 → 0.9147`, factuality
proxy tăng `0.8059 → 0.9071`, timeline completeness tăng `0.3064 → 0.6667` và
critical-omission proxy giảm `0.7701 → 0.3688`.

Vì vậy kết luận đúng là:

> Raw phù hợp cho một note ngắn và lexical summarization. RAG phù hợp hơn khi
> mục tiêu là evidence traceability, nhiều tài liệu, patient isolation,
> citation review và safe refusal. Nghiên cứu tiếp theo nên kiểm tra adaptive
> routing thay vì bắt mọi case dùng cùng một flow.

Qdrant không thực hiện chunking. Chunking xảy ra trước và tạo các đơn vị bằng
chứng có section/source span; embedding biểu diễn ngữ nghĩa của từng chunk;
Qdrant lưu và truy hồi các chunk theo similarity cùng patient/encounter filter.
Embedding và Qdrant không thể cứu một chunk bị cắt sai hoặc phân loại sai
section, nên retrieval improvement phải bắt đầu từ normalization/chunking.

Gói nghiên cứu Vinmec được tách riêng để không trộn lẫn PoC benchmark với giả
định triển khai bệnh viện:

- `docs/research/VINMEC_MEDICAL_RECORD_SUMMARIZATION_RESEARCH_ROADMAP.md`:
  phân tích hiện trạng công khai, điều kiện mở rộng, governance và lộ trình
  nghiên cứu.
- `docs/research/VINMEC_PILOT_PROPOSAL.md`: proposal pilot theo P0/P1/P2,
  risk register, human-evaluation design, go/no-go criteria và architecture
  research-only.
- `docs/research/FINAL_RESEARCH_CONCLUSION.md`: kết luận nghiên cứu cuối cùng,
  nhấn mạnh PoC evidence-first, ranh giới proxy evaluation và hướng research
  pilot thay vì production deployment.

## 7. Artifact và reproducibility

```text
scripts/analyze_week5_evaluation.py
scripts/capture_demo_evidence.py

artifacts/evaluation/week5_analysis/
  WEEK5_P1_P2_ANALYSIS.md
  record_strata.csv
  diversity_strata_metrics.csv
  provider_failure_matrix.csv
  metric_correlations.csv
  reference_edit_proxy.csv
  retrieval_gate_case_analysis.csv
  retrieval_threshold_sensitivity.csv
  controlled_flow_comparison.csv
  controlled_flow_deltas.csv
  human_review_cases.jsonl
  human_review_scores.csv
  human_review_blinding_key.csv
  human_review_sample_manifest.json
  analysis_manifest.json

artifacts/evaluation/historical_flow_metrics/
  flow_1_raw_per_record_metrics.csv
  flow_1_5_context_per_record_metrics.csv
  flow_2_rag_per_record_metrics.csv
```

`analysis_manifest.json` ghi rõ generation models không được rerun và liệt kê
interpretation limitations. Các generated clinical-text artifacts được ignore
khỏi Git; chỉ chia sẻ gói đã được duyệt và khử định danh.

Analyzer ưu tiên ba historical-flow CSV repository-relative ở trên; legacy
D-drive chỉ còn là fallback. Vì vậy controlled comparison có thể được tái tạo
trên máy demo khác khi portable artifacts được chuyển cùng gói.

## 8. Acceptance matrix

| Điều kiện | Trạng thái | Bằng chứng |
| --- | --- | --- |
| Local staging chạy end-to-end | Đạt | Docker Compose, health/ready, build logs |
| Flow 2.1 portable trong Admin | Đạt | 5 providers, 250 outputs, BERTScore 5/5 |
| Gated/no-gate tách biệt | Đạt | Hai snapshot và case study riêng |
| Data diversity analysis | Đạt | 50-record strata + provider metrics |
| Provider failure analysis | Đạt | Failure matrix 5 providers |
| Metric interpretation | Đạt | Correlation + explicit boundaries |
| Gate sensitivity | Đạt | 5 post-hoc threshold scenarios |
| Human evaluation package | Đạt | 12 blinded cases + blank score sheet |
| Human/clinician scoring | Chờ reviewer thật | Không được tự động hoặc giả lập |
| UI screenshots/video/SharePoint | Chờ operator | Runbook và checklist đã sẵn sàng |

## 9. Kết luận và quyết định đề xuất

P0, P1 và P2 đã hoàn tất ở mức implementation, automated analysis và delivery
documentation. Dự án hiện có câu chuyện end-to-end đủ mạnh cho final demo:
runtime lặp lại được, doctor review boundary rõ, provider benchmark có kỷ luật,
retrieval gate có failure giải thích được và mọi metric đều có interpretation
boundary.

Quyết định tốt nhất lúc này là:

1. freeze major features;
2. chạy dry-run demo theo runbook;
3. ghi hình và hoàn thiện evidence thủ công;
4. mời reviewer thật chấm blinded package;
5. dùng Vinmec pilot proposal như hướng phát triển nghiên cứu tiếp theo;
6. chỉ cân nhắc public cloud deployment khi có credit/tài nguyên và khi nó phục
   vụ mục tiêu demo cụ thể.

Không nên mô tả dự án là hệ thống vận hành chính thức, đã được xác nhận an
toàn/hiệu quả lâm sàng, đã kiểm chứng trên EHR thực hoặc có quyền tự ra quyết
định lâm sàng.

Kết luận cuối cùng: giá trị của dự án không chỉ là benchmark provider. Giá trị
chính là một workflow clinical NLP có kỷ luật: AI tạo draft, claim có evidence,
retrieval có gate, bác sĩ duyệt cuối cùng, metric proxy được tách khỏi human
validation và hướng mở rộng được đặt trong pilot nghiên cứu có governance.
