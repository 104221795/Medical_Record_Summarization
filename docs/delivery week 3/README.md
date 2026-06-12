# Báo cáo tiến độ Delivery Week 3 - Medical Record Summarization MVP

**Người thực hiện:** Sơn  
**Dự án:** Citation-grounded Medical Record Summarization MVP  
**Thời điểm cập nhật:** 12/06/2026  
**Trạng thái:** PoC end-to-end đã tiến bộ rõ rệt: benchmark theo nhiều flow đã chạy được, provider đã mở rộng ngoài BART/Pegasus, RAG/evidence-first pipeline đã được đưa vào trung tâm đánh giá, doctor/admin UI đã được nâng cấp để demo kỹ thuật dễ hiểu hơn.

## Project Links

| Hạng mục | Link |
| --- | --- |
| GitHub repository | `[https://github.com/104221795/Medical_Record_Summarization]` |
| YouTube demo | `[https://www.youtube.com/watch?v=CDP3WvtH0ko]` |
| Local React demo | `http://127.0.0.1:5173` |
| Local API docs | `http://127.0.0.1:8080/docs` |
| Local admin evaluation | `http://127.0.0.1:5173/admin/evaluation` |
| Local benchmark results | `http://127.0.0.1:5173/admin/evaluation/benchmark` |

> Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes.

## I. Tổng Quan Tiến Độ Week 3

Trong Week 2, dự án đã chuyển từ PRD/workflow sang một MVP có thể chạy được với backend, frontend, provider selection, dataset governance và benchmark dashboard. Week 3 tiếp tục đẩy dự án sang một mức trưởng thành hơn: không chỉ "generate được summary", mà còn bắt đầu đo được chất lượng theo nhiều flow, nhiều provider, nhiều metric và nhiều failure pattern.

Tiến độ quan trọng nhất của tuần này là hệ thống đã bắt đầu chứng minh được hướng đi RAG/evidence-first là phù hợp hơn cho bài toán Medical Record Summarization. Thay vì chỉ đưa nguyên văn note vào BART/Pegasus, hệ thống đã có pipeline lấy evidence, xây clinical context có cấu trúc, kiểm tra citation/unsupported claims, sau đó mới đưa sang provider để sinh draft summary. Đây là nền tảng đúng hơn cho bài toán y tế vì summary không thể chỉ "nghe hay"; nó phải truy vết được bằng chứng.

Week 3 cũng đã hoàn thiện tốt hơn phần demo kỹ thuật: benchmark có thể chạy theo stage, so sánh model trong cùng điều kiện, có dashboard admin để quan sát kết quả, có failure analysis theo record, có human evaluation rubric, và doctor UI đã chuyển dần sang evidence-first review workspace.

## II. Những Kết Quả Nổi Bật Trong Tuần

### 1. Benchmark Đã Mở Rộng Từ Một Flow Sang Nhiều Flow

Tuần này hệ thống không còn chỉ có một kiểu benchmark thô `source_note -> model -> metrics`. Các flow đã được phân biệt rõ hơn:

| Flow | Tên | Mô tả | Vai trò hiện tại |
| --- | --- | --- | --- |
| Flow 1 | Raw Summarization | `source_note -> summarizer -> metrics` | Baseline ban đầu để biết model tóm tắt trực tiếp hoạt động ra sao |
| Flow 1.5 | Clinical Context Builder | `source_note -> structured clinical context -> summarizer -> metrics` | Giảm missing diagnosis/medication/timeline bằng cách sắp xếp input theo section lâm sàng |
| Flow 2 | RAG Grounded | `source_note -> chunk -> MiniLM -> retrieve evidence -> summarizer -> citation metrics` | Flow quan trọng nhất để chứng minh vì sao cần RAG |
| Flow 2.1 | RAG Best Models | `retrieved evidence -> strict prompt -> qwen/llama/gemini/BART/Pegasus comparison` | Flow thử nghiệm provider mới trên evidence-first context |

Điểm đáng chú ý là Flow 2 và Flow 2.1 đã đưa retrieval/evidence vào trung tâm benchmark. Điều này giúp đánh giá sát mục tiêu sản phẩm hơn: Medical Record Summarization không chỉ cần summary giống reference theo ROUGE, mà cần grounded summary có evidence rõ ràng.

### 2. Benchmark Theo Stage Đã Hoạt Động

Benchmark không còn chạy một lần duy nhất rồi đọc kết quả thủ công. Hệ thống đã chuyển sang cách chạy theo stage để kiểm soát rủi ro, thời gian và khả năng debug:

| Stage | Mục đích | Quy mô |
| --- | --- | --- |
| Smoke test | Kiểm tra pipeline/provider không crash | 1-3 records |
| Small controlled run | So sánh provider nhanh | 20 records |
| Stage 1 | Controlled benchmark nhỏ | 50 records |
| Stage 2 | Medium benchmark | 200 records |
| Future Stage 3 | Larger proxy benchmark | 500+ records |
| Future Stage 4 | Cross-dataset evaluation | MultiClinSum + MTS-Dialog + MEDIQA-Sum |

Điểm tốt là các model có thể được so sánh trong cùng điều kiện: cùng dataset input, cùng limit, cùng output schema, cùng metric pipeline, cùng artifact format. Đây là yêu cầu quan trọng để tránh so sánh cảm tính giữa các provider.

### 3. Provider Đã Mở Rộng Ngoài BART Và Pegasus

Week 2 tập trung nhiều vào deterministic, BART và Pegasus. Week 3 đã mở rộng provider layer theo hướng thực tế hơn:

| Provider | Backend/Model | Vai trò |
| --- | --- | --- |
| Deterministic | `deterministic_sentence_baseline` | Fast extractive baseline, kiểm tra pipeline |
| BART | `facebook/bart-large-cnn` | Local Hugging Face summarization baseline |
| Pegasus XSum | `google/pegasus-xsum` | General single-summary baseline, kết quả thường yếu hơn cho clinical context |
| Pegasus CNN/DailyMail | `google/pegasus-cnn_dailymail` | General summarization baseline |
| Pegasus PubMed | `google/pegasus-pubmed` | Medical/scientific Pegasus checkpoint, phù hợp hơn XSum nhưng không luôn thắng |
| Qwen2.5 | `ollama/qwen2.5:3b` | Local LLM testing provider, phù hợp strict RAG prompt hơn BART/Pegasus trong nhiều case |
| Llama3.2 | `ollama/llama3.2:3b` | Local LLM testing provider cho evidence-first generation |
| Gemini 2.5 Flash Lite | `gemini/gemini-2.5-flash-lite` | Optional cloud provider qua gateway, chỉ dùng khi có key/governance |
| Gemini governed provider | `gemini` | Optional structured provider, không đưa vào official comparison nếu chưa có completed benchmark rõ ràng |

Việc bổ sung Qwen2.5 và Llama3.2 là một cải tiến đáng kể, vì hai model local chat này phản ứng tốt hơn với prompt dạng strict clinical extraction/RAG so với BART/Pegasus vốn được train cho summarization tổng quát. Điều này không có nghĩa Qwen/Llama đã clinical-ready, nhưng cho thấy hướng LLM + evidence-first prompt đáng đầu tư tiếp.

### 4. LLM Gateway Đã Được Tập Trung Hóa

Một điểm technical quan trọng là provider mới không được nối thẳng rải rác vào từng script, mà được đưa qua LLM Gateway:

```text

benchmark / doctor workflow
        |
        v
LLM Gateway
        |
        +-- Ollama: qwen2.5:3b
        +-- Ollama: llama3.2:3b
        +-- Gemini 2.5 Flash Lite

```

Gateway giúp chuẩn hóa:

- model alias nội bộ;
- timeout;
- temperature thấp cho medical summarization;
- max tokens;
- local context window;
- output cleaning;
- error handling để một provider lỗi không làm crash toàn bộ benchmark.

Đây là bước đúng hướng nếu sau này cần thay provider hoặc chạy qua enterprise gateway như LiteLLM proxy.

## III. RAG Là Hướng Phù Hợp Nhất Cho Bài Toán Này

### 1. Vì Sao Raw Summarization Chưa Đủ

Flow 1 raw summarization có giá trị làm baseline, nhưng không đủ cho bài toán Medical Record Summarization vì:

- note bệnh án có thể dài hơn context window của BART/Pegasus;
- model dễ bỏ sót diagnosis/medication/timeline;
- model có thể sinh câu nghe hợp lý nhưng không có evidence;
- ROUGE tốt không đồng nghĩa clinical correctness;
- bác sĩ cần biết claim nào lấy từ đâu, không chỉ đọc summary cuối.

### 2. Vì Sao Clinical Context Builder Giúp Tốt Hơn

Flow 1.5 đã thêm bước sắp xếp context thành các section:

```text
[Patient Snapshot]
[Diagnosis Evidence]
[Medication Evidence]
[Timeline Evidence]
[Diagnostics Evidence]
[Assessment Evidence]
[Plan Evidence]
[Unknown / Missing Evidence]
```

Cách này giúp model ít bị lẫn giữa timeline và plan, ít tự suy diễn medication/diagnosis hơn, và giúp bác sĩ đọc output dễ hơn. Đây là cải tiến rất có giá trị cho doctor workflow hiện tại.

### 3. Vì Sao RAG Là Lựa Chọn Tốt

Flow 2 RAG Grounded là hướng mạnh nhất vì nó đưa evidence retrieval vào trước generation:

```text
source_note
  -> chunk
  -> MiniLM embedding
  -> retrieve evidence
  -> structured clinical context
  -> summarizer
  -> citation metrics + failure analysis
```

Điểm outstanding của hướng RAG:

- giảm nguy cơ model đọc lan man toàn bộ note;
- ép model tập trung vào evidence liên quan;
- tạo điều kiện cho citation coverage;
- hỗ trợ unsupported claim detection;
- giúp bác sĩ kiểm tra câu summary dựa trên source evidence;
- phù hợp hơn cho hồ sơ bệnh án dài có nhiều encounter/document;
- là kiến trúc gần production hơn so với raw summarization.

Kết luận kỹ thuật của Week 3: RAG/evidence-first nên là hướng chính cho bài toán này. BART/Pegasus vẫn nên giữ làm baseline, nhưng không nên là kiến trúc trung tâm cho doctor-facing workflow nếu không có retrieval/citation layer.

## IV. Metrics Và Evaluation Đã Được Cải Thiện

### 1. Metrics Không Còn Chỉ Là ROUGE

Week 2 chủ yếu dùng ROUGE-1/2/L. Week 3 đã bổ sung và chuẩn hóa thêm các nhóm metric phục vụ clinical NLP:

| Metric | Vai trò |
| --- | --- |
| ROUGE-1 | Lexical overlap cấp unigram |
| ROUGE-2 | Phrase overlap cấp bigram |
| ROUGE-L | Longest common subsequence, useful cho summary similarity |
| BERTScore | Semantic similarity, tốt hơn ROUGE khi wording khác reference |
| Citation coverage | Tỷ lệ claim có evidence |
| Unsupported claim rate | Tỷ lệ claim không có đủ evidence |
| Faithfulness/factuality proxy | Proxy đánh giá groundedness |
| Missing diagnosis rate | Tín hiệu bỏ sót diagnosis |
| Missing medication rate | Tín hiệu bỏ sót medication |
| Timeline completeness | Đánh giá timeline có đủ không |
| Hallucinated clinical entity count | Đếm entity lâm sàng không có evidence |
| Critical information omission rate | Đánh giá bỏ sót thông tin quan trọng |
| Latency average/P50/P95 | Đánh giá runtime thực tế |

BERTScore được đưa vào như optional metric. Điều này đúng vì BERTScore cần dependency/model evaluator riêng, thường như `roberta-large`, và không phải môi trường nào cũng có sẵn cache.

### 2. BERTScore Được Đưa Vào Pipeline

BERTScore không thay thế ROUGE, nhưng bổ sung semantic signal. Trong medical summarization, cùng một ý có thể được viết bằng nhiều cách khác nhau; ROUGE có thể đánh thấp nếu wording khác reference. BERTScore giúp giảm vấn đề này.

Tuy nhiên, báo cáo vẫn cần ghi rõ:

- BERTScore không chứng minh clinical safety.
- BERTScore không phát hiện đầy đủ hallucination.
- BERTScore cần đi cùng citation/factuality/human review.

### 3. Failure Analysis Được Hoàn Thiện Hơn

Failure analysis đã được mở rộng theo hướng thực dụng:

- hallucinated content;
- incomplete summary;
- missing diagnosis;
- missing medication;
- missing timeline;
- retrieval-related failure;
- source data limitation;
- unsupported claim;
- critical omission.

Dashboard/failure view đã hướng tới per-record review:

- lọc theo model;
- lọc theo failure type;
- xem input note;
- xem reference summary;
- xem generated summary;
- xem retrieved evidence;
- so sánh side-by-side giữa deterministic/BART/Pegasus/Qwen/Llama;
- export case for review.

Đây là cải tiến quan trọng vì benchmark không chỉ nên trả về một bảng điểm. Với Clinical NLP, những record lỗi cụ thể thường có giá trị hơn điểm trung bình.

## V. Human Evaluation Và HITL Workflow

Week 3 đã củng cố hướng Human-in-the-Loop:

| Thành phần | Trạng thái |
| --- | --- |
| Doctor review workflow | Có start review, edit, approve, reject |
| Reject reason | Có reason/comment phục vụ analysis |
| Review history | Có tracking theo summary |
| Audit trail | Có audit log cho sensitive actions |
| Human evaluation rubric | Đã có hướng/template rõ hơn |
| Training signal | Review/edit/reject có thể trở thành signal cải thiện prompt/retrieval |

Human evaluation rubric nên tiếp tục chuẩn hóa theo các tiêu chí:

| Tiêu chí | Câu hỏi đánh giá |
| --- | --- |
| Clinical correctness | Summary có đúng với source không? |
| Completeness | Có bỏ sót diagnosis/medication/timeline quan trọng không? |
| Evidence grounding | Claim quan trọng có citation không? |
| Unsupported claim handling | Claim thiếu evidence có được flag rõ không? |
| Readability | Bác sĩ có đọc nhanh được không? |
| Safety | Output có tránh recommendation không được phép không? |
| Usefulness | Summary có giúp giảm thời gian review không? |

Điểm tốt của Week 3 là human evaluation không còn chỉ là ý tưởng. Nó đã được nối vào workflow approve/reject/edit và có thể phát triển thành training signal cho Week 4.

## VI. Backend Improvements Trong Tuần

### 1. Provider Layer Và Gateway

Backend đã được cải tiến để hỗ trợ nhiều provider hơn, đồng thời tránh hardcode logic rời rạc:

- thêm provider catalog rõ hơn;
- thêm Qwen2.5 và Llama3.2 qua Ollama;
- thêm Gemini 2.5 Flash Lite ở dạng optional;
- giữ Gemini là optional governed provider;
- thêm LLM Gateway để gom model routing;
- chuẩn hóa model alias;
- error handling để provider fail không crash toàn bộ benchmark;
- giữ safety gate cho BART/Pegasus qua env `RUN_REAL_BASELINES=1`.

### 2. Hugging Face Loading Được Sửa Ổn Định Hơn

Transformers pipeline `pipeline("summarization")` từng không tương thích với version hiện tại. Backend/script đã chuyển sang hướng trực tiếp:

```text
AutoTokenizer.from_pretrained(...)
AutoModelForSeq2SeqLM.from_pretrained(...)
model.generate(...)
```

Điều này production-clean hơn vì:

- kiểm soát tokenizer/model rõ hơn;
- dễ log generation params;
- dễ xử lý BART/Pegasus chung một pathway;
- giảm phụ thuộc vào high-level pipeline API.

### 3. Pegasus Diagnostic

Pegasus đã được xử lý cẩn thận hơn thay vì skip tự động khi thấy warning. Diagnostic rule phân biệt:

- static positional embedding warning có thể chấp nhận trong một số checkpoint;
- missing task-critical weights thì không chấp nhận;
- generation smoke test phải chạy được;
- output không được empty;
- checkpoint được chọn theo reliability policy.

Điều này giúp benchmark công bằng hơn và tránh loại Pegasus sai lý do.

### 4. Cache Và Local Model Governance

Cache paths được chuẩn hóa theo D drive:

```powershell
HF_HOME=D:\hf_cache
HF_HUB_CACHE=D:\hf_cache\hub
HF_DATASETS_CACHE=D:\hf_cache\datasets
TRANSFORMERS_CACHE=D:\hf_cache\hub
OLLAMA_MODELS=D:\ollama_models
```

Điểm tốt là hệ thống tránh tải model về C drive, giúp kiểm soát disk usage tốt hơn và dễ demo trên máy local.

### 5. Provider Readiness Và Retrieval Quality Gate

Provider readiness đã được nâng cấp theo hướng thật hơn:

- kiểm tra Ollama có chạy không;
- kiểm tra qwen2.5/llama3.2 có trong `ollama list` không;
- test prompt/warmup latency;
- kiểm tra Gemini key nếu bật Gemini;
- kiểm tra cache Hugging Face;
- retrieval quality gate trước summarization.

Retrieval quality gate nên kiểm tra:

- diagnosis evidence có không;
- medication evidence có không;
- timeline evidence có không;
- evidence có đúng patient/encounter không;
- nếu retrieval yếu thì flag review thay vì ép model generate.

## VII. Frontend/UI Improvements

### 1. Admin Evaluation Dashboard

Admin dashboard đã được cải thiện để phục vụ demo benchmark:

- phân biệt benchmark results và evaluation purpose tốt hơn;
- hiển thị model comparison;
- hiển thị ROUGE/BERTScore status;
- hiển thị clinical proxy metrics;
- hiển thị failure analysis theo model;
- đọc artifacts từ output folder;
- hỗ trợ nhìn nhanh prediction files và benchmark stages.

Điểm tốt là mentor có thể xem hệ thống theo góc nhìn kỹ thuật: model nào chạy, dataset nào dùng, artifact nào sinh ra, metric nào có/không có.

### 2. Failure Analysis Dashboard

Per-record failure analysis được định hướng như một công cụ đánh giá thật, không chỉ là bảng số liệu:

- input note;
- generated summary;
- reference summary;
- retrieved evidence;
- citations;
- model outputs side by side;
- failure labels;
- export case for review.

Đây là phần giúp giải thích được "vì sao model fail", thay vì chỉ nói "ROUGE thấp".

### 3. Doctor Dashboard Và Doctor Workflow

Doctor UI đã được cải tiến nhiều:

- dashboard rõ workflow hơn;
- Generate Summary gọn hơn, chia vùng Patient/Provider/Draft;
- provider selection compact hơn;
- Draft Preview hiện gần action hơn;
- Review & Evidence có 3 panel rõ: source evidence, generated summary, citation/claim review;
- citation hover/click highlight evidence và linked claim;
- unsupported claims được giữ visible;
- action bar của bác sĩ gọn hơn;
- metadata header rõ hơn;
- generated summary có scroll/accordion để tránh quá dài;
- UI dùng terminology evidence-first thay vì mô tả mơ hồ.

Điểm quan trọng là doctor UI hiện đúng hướng hơn: bác sĩ không chỉ nhận summary, mà có thể kiểm evidence, claim status và lý do vì sao summary bị flag.

## VIII. Current Flow Interpretation

Một điểm cần nói rõ trong report/demo:

Doctor `Generate Summary` hiện tại không phải Flow 1 raw thuần. Với các provider text/gateway, backend đang build evidence pack và structured clinical context trước khi gọi provider. Vì vậy doctor workflow hiện gần với Flow 1.5/evidence-first clinical context.

Tuy nhiên, full MiniLM + Qdrant Flow 2 vẫn nên được xem là benchmark/RAG architecture path. Không nên nói doctor page đã hoàn toàn là production RAG nếu chưa wire full Qdrant retrieval vào doctor generation endpoint.

Cách nói chính xác:

> Doctor workflow currently uses an evidence-first structured clinical context path. Full MiniLM + Qdrant RAG benchmark has been implemented as the technical evaluation path and is the recommended direction for production integration.

## IX. Benchmark Artifacts Và Output Organization

Các output benchmark quan trọng hiện nằm dưới:

```text
D:\clin_summ_outputs
```

Các folder chính:

```text
D:\clin_summ_outputs\medium_benchmark_bart_pegasus
D:\clin_summ_outputs\rag_grounded_benchmark
D:\clin_summ_outputs\rag_best_models
```

Artifacts quan trọng:

```text
evaluation_run_manifest.json
dataset_manifest.json
model_comparison.csv
per_record_metrics.csv
all_predictions.jsonl
deterministic_predictions.jsonl
bart_predictions.jsonl
pegasus_predictions.jsonl
qwen2.5_predictions.jsonl
llama3.2_predictions.jsonl
failure_analysis.md
EVALUATION_REPORT.md
run.log
```

Run manifest cần tiếp tục lưu:

- dataset version;
- dataset path;
- model checkpoint;
- provider name;
- prompt/template version;
- retrieval config;
- embedding model;
- cache path;
- generation params;
- commit hash;
- runtime environment;
- start/end time;
- record limit;
- output folder.

Đây là yếu tố rất quan trọng để benchmark có thể reproducible.

## X. Kết Quả Đánh Giá Định Lượng Week 3

### 1. Flow 2 - Retrieval-Grounded Benchmark Optimized

Run chính cho Flow 2 sử dụng:

```text
Input: governed MultiClinSum benchmark records
Records: 50
Embedding: sentence-transformers/all-MiniLM-L6-v2
Vector store: Qdrant (memory)
Retrieval strategy: section-aware source-note queries + balanced clinical context packing
```

Retrieval metrics:

| Metric | Result |
| --- | ---: |
| Average chunks per record | 4.12 |
| Average retrieved chunks | 4.96 |
| Average context tokens | 753.70 |
| Recall@5 proxy | 0.9512 |
| MRR proxy | 0.9600 |
| nDCG@5 proxy | 0.8919 |

Model comparison:

| Model | Records | ROUGE-L | BERTScore F1 | Citation coverage | Unsupported claim rate | Faithfulness proxy | Latency p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic | 50 | 0.1625 | 0.7858 | **0.9237** | **0.0000** | **0.9018** | 0.0 |
| BART | 50 | 0.1388 | 0.8229 | 0.3047 | **0.0000** | 0.7592 | 33,423.85 |
| Pegasus XSum | 50 | 0.0973 | **0.8276** | 0.5200 | 0.0600 | 0.7266 | 19,533.30 |
| Pegasus PubMed | 50 | **0.1733** | 0.8236 | 0.6429 | 0.4573 | 0.6067 | 94,318.55 |
| Pegasus CNN/DailyMail | 50 | 0.1490 | 0.8271 | 0.4083 | **0.0000** | 0.7922 | 69,205.05 |

Interpretation:

- Retrieval quality đã khá tốt trong proxy setup: Recall@5 0.9512, MRR 0.9600, nDCG@5 0.8919.
- Deterministic context baseline đạt citation coverage và faithfulness proxy cao nhất vì nó thiên về extractive/evidence-bound output.
- Pegasus PubMed có ROUGE-L cao nhất trong nhóm Pegasus/BART của run này, nhưng latency rất cao và unsupported claim rate cũng cao.
- BART/Pegasus vẫn hữu ích làm baseline, nhưng không đủ tốt nếu thiếu prompt/context/grounding chặt.
- Kết quả này củng cố nhận định: retrieval-grounded context giúp đo được citation quality và failure pattern tốt hơn raw summarization.

### 2. Flow 2.1 - RAG Best Models Benchmark

Run Flow 2.1 là kết quả nổi bật nhất trong Week 3, vì nó so sánh các provider mới với BART/Pegasus trong cùng điều kiện RAG/evidence-first:

```text
Records: 20
Embedding: sentence-transformers/all-MiniLM-L6-v2
Vector store: Qdrant (memory)
LLM Gateway: http://localhost:4000
Providers: BART, Pegasus, Qwen2.5, Llama3.2
Gemini: optional, not included in this no-gemini official snapshot
```

Retrieval metrics:

| Metric | Result |
| --- | ---: |
| Average chunks per record | 3.55 |
| Average retrieved chunks | 3.15 |
| Average context tokens | 733.15 |
| Recall@5 proxy | 0.9275 |
| MRR proxy | 0.9750 |
| nDCG@5 proxy | 0.8533 |

Model comparison:

| Model | Records | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore F1 | Citation coverage | Faithfulness proxy | Hallucinated entity avg | Critical omission |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BART | 20 | 0.1138 | 0.0140 | 0.0793 | 0.8074 | 0.1483 | 0.7873 | 1.75 | 0.9722 |
| Pegasus CNN/DailyMail | 20 | 0.1663 | 0.0716 | 0.1380 | 0.8174 | 0.3167 | 0.8142 | 0.95 | 0.8542 |
| Qwen2.5 | 20 | **0.3758** | 0.1810 | **0.2607** | **0.8583** | **0.8747** | 0.8715 | **0.10** | 0.5486 |
| Llama3.2 | 20 | 0.3735 | **0.1826** | 0.2603 | 0.8559 | 0.8576 | **0.8817** | 0.35 | **0.4375** |

Failure pattern comparison:

| Model | No major proxy failure | Hallucinated content | Missing diagnosis | Missing medication | Missing timeline | Retrieval-related failure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BART | 0 | 19 | 5 | 1 | 12 | 11 |
| Pegasus CNN/DailyMail | 3 | 11 | 5 | 2 | 10 | 9 |
| Qwen2.5 | **11** | **2** | **3** | 2 | 5 | 5 |
| Llama3.2 | 9 | 6 | 4 | 2 | **3** | **3** |

Outstanding findings:

- Qwen2.5 và Llama3.2 vượt BART/Pegasus rõ ràng trong Flow 2.1.
- Qwen2.5 đạt ROUGE-L 0.2607, cao hơn BART 0.0793 và Pegasus 0.1380 trong cùng 20-record RAG run.
- Qwen2.5 đạt BERTScore F1 0.8583, cao nhất trong run.
- Llama3.2 đạt faithfulness proxy 0.8817 và critical omission thấp nhất trong nhóm.
- Citation coverage của Qwen2.5/Llama3.2 trên 0.85, trong khi BART chỉ 0.1483.
- Hallucinated content giảm mạnh: BART 19 cases, Pegasus 11 cases, Qwen2.5 chỉ 2 cases, Llama3.2 6 cases.
- Kết quả này là bằng chứng kỹ thuật mạnh rằng RAG + strict clinical prompt + local chat LLM phù hợp hơn cho doctor-facing draft generation so với BART/Pegasus raw-style summarization.

### 3. Flow 1.5 - Clinical Context Benchmark

Clinical Context Benchmark kiểm tra tác động của structured context trước khi summarization:

```text
Records: 50
Context mode: Clinical Context Builder
Metrics: ROUGE, BERTScore, citation/factuality proxy, failure categories
```

Model comparison snapshot:

| Model | Records | ROUGE-L | BERTScore F1 | Citation coverage | Faithfulness proxy | Timeline completeness | Latency p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic | 50 | 0.1008 | 0.7877 | 0.5515 | 0.7839 | 0.1237 | 0.0 |
| BART | 50 | **0.2077** | 0.8453 | 0.8500 | 0.7938 | 0.2742 | 41,181.75 |
| Pegasus XSum | 50 | 0.1448 | **0.8471** | **1.0000** | 0.7539 | 0.1720 | 16,060.55 |
| Pegasus PubMed | 50 | 0.1732 | 0.8240 | 0.8126 | 0.6080 | 0.1720 | 93,506.60 |
| Pegasus CNN/DailyMail | 50 | 0.1766 | 0.8328 | 0.9633 | 0.7827 | 0.1452 | 66,673.00 |

Interpretation:

- Clinical Context Builder giúp BART đạt ROUGE-L tốt nhất trong Flow 1.5.
- Pegasus XSum có BERTScore cao nhưng vẫn có nhiều incomplete summary, vì semantic similarity không đủ để đánh giá clinical usefulness.
- Structured context cải thiện citation coverage so với raw-style benchmark, nhưng chưa đủ bằng Flow 2.1 với Qwen/Llama.
- Đây là bằng chứng Flow 1.5 là bước cải thiện tốt, nhưng Flow 2/RAG vẫn là hướng mạnh hơn.

### 4. Ý Nghĩa Của Kết Quả Đánh Giá

Các kết quả trên cho thấy tiến độ Week 3 rất tốt vì hệ thống đã trả lời được ba câu hỏi quan trọng:

1. **Retrieval có đủ tốt để tiếp tục RAG không?**  
   Có. Recall@5 proxy trên các run RAG đạt khoảng 0.9275-0.9512, MRR đạt 0.96-0.975.

2. **RAG có giúp model tốt hơn không?**  
   Có tín hiệu rõ. Khi dùng RAG/evidence-first context, Qwen2.5 và Llama3.2 vượt BART/Pegasus đáng kể ở ROUGE-L, BERTScore, citation coverage và hallucination reduction.

3. **BART/Pegasus có nên bỏ không?**  
   Không nên bỏ. BART/Pegasus vẫn rất quan trọng làm baseline. Nhưng chúng không nên là lựa chọn trung tâm cho doctor-facing workflow nếu không có RAG/context builder và citation validation.

## XI. Outstanding Results 

Những điểm nổi bật nhất của Week 3:

1. **Dự án đã vượt khỏi demo model đơn giản.** Hệ thống hiện là PoC có backend, frontend, provider gateway, benchmark, dashboard, HITL review và audit. Đây không còn là một notebook hoặc prompt demo, mà là một prototype có workflow và artifacts đo lường.

2. **Benchmark đã đa flow.** Có thể so sánh raw summarization, clinical context, RAG grounded và RAG best models. Điều này giúp giải thích được "vì sao cần RAG", không chỉ nói model nào cao điểm hơn.

3. **RAG được chứng minh là hướng đúng bằng số liệu.** Flow 2.1 cho thấy Qwen2.5 đạt ROUGE-L 0.2607, BERTScore F1 0.8583 và citation coverage 0.8747; Llama3.2 đạt faithfulness proxy 0.8817. Đây là tín hiệu mạnh rằng evidence-first RAG tốt hơn raw BART/Pegasus cho bài toán này.

4. **Provider layer đã mở rộng có kiểm soát.** Không chỉ BART/Pegasus, hệ thống đã có Qwen2.5, Llama3.2 và Gemini 2.5 Flash Lite optional qua LLM Gateway. Provider mới không được hardcode rải rác mà đi qua gateway chuẩn hóa.

5. **Model comparison công bằng hơn.** Các model được chạy trong cùng dataset/limit/stage/output format, giúp giảm so sánh cảm tính. Flow 2.1 cho phép đặt BART, Pegasus, Qwen và Llama trong cùng điều kiện retrieval context.

6. **Metrics đã tiến gần Clinical NLP hơn.** ROUGE vẫn có, nhưng đã bổ sung BERTScore, citation coverage, unsupported claim rate, factuality proxy, failure categories và latency P50/P95. Điều này làm report đáng tin hơn so với chỉ dùng ROUGE.

7. **Failure analysis đã thực dụng hơn.** Có thể đi vào từng record để xem model sai ở đâu, evidence nào retrieval được, claim nào unsupported. Kết quả Flow 2.1 cho thấy hallucinated content giảm từ 19 cases ở BART xuống 2 cases ở Qwen2.5 trong 20-record run.

8. **Human evaluation đã có đường phát triển rõ.** Review/edit/reject reason có thể trở thành data cho prompt/retrieval improvement. Rubric giúp biến doctor review thành evaluation signal thay vì chỉ là thao tác UI.

9. **Doctor UI đã chuyển sang evidence-first.** Citation review rõ hơn, unsupported claims visible, action workflow tốt hơn. Generate Summary đã gọn hơn, Review & Evidence đã có panel summary scroll/accordion và citation tracing rõ hơn.

10. **PoC end-to-end đã rất tốt cho giai đoạn hiện tại.** Hệ thống có thể demo từ patient context -> generate -> evidence review -> doctor action -> audit/admin evaluation. Đây là một đường demo rất thuyết phục cho mentor vì nó thể hiện cả product workflow và technical evaluation.

## XII. So Sánh Tiến Độ Week 2 -> Week 3

| Hạng mục | Week 2 | Week 3 update | Mức cải thiện |
| --- | --- | --- | --- |
| Benchmark flow | Chủ yếu medium benchmark BART/Pegasus | Có Flow 1, Flow 1.5, Flow 2, Flow 2.1 | Rất lớn |
| Provider | Deterministic, BART, Pegasus, Gemini optional | Thêm Qwen2.5, Llama3.2, Gemini 2.5 Flash Lite qua gateway | Rất lớn |
| Retrieval | all-MiniLM-L6-v2 được chọn, retrieval đủ tốt để bắt đầu benchmark | RAG benchmark dùng MiniLM + Qdrant memory, có Recall@5/MRR/nDCG | Rất lớn |
| Metrics | ROUGE là chính, BERTScore optional/planned | ROUGE + BERTScore computed + citation/factuality/failure metrics | Rất lớn |
| Failure analysis | Có failure categories tổng quát | Có per-model failure counts, hallucination/missing diagnosis/timeline/retrieval failure | Lớn |
| Human evaluation | Có endpoint/template hướng phát triển | Có rubric rõ hơn, review/edit/reject trở thành training signal | Lớn |
| Doctor UI | Workflow chạy được nhưng còn thô | Generate Summary gọn hơn, Review & Evidence evidence-first, citation tracing tốt hơn | Lớn |
| Admin UI | Benchmark dashboard đọc artifacts | Evaluation dashboard hiển thị nhiều flow/provider/metrics hơn | Lớn |
| Backend provider design | Provider còn phân tán hơn | LLM Gateway tập trung hóa local/cloud providers | Rất lớn |
| Production readiness | MVP/prototype chạy được | PoC có evaluation discipline, reproducibility manifest, staged benchmark | Rất lớn |

Nhìn tổng thể, Week 3 là bước nhảy từ "MVP chạy được" sang "PoC có thể chứng minh bằng số liệu". Đây là khác biệt rất quan trọng trong một dự án Clinical NLP, vì mô hình không chỉ cần sinh text, mà cần được đặt trong hệ thống có governance, benchmark, evidence tracing, human review và failure analysis.

Điểm tiến bộ đáng nhấn mạnh nhất là hệ thống đã tự tạo ra một vòng lặp đánh giá:

```text
run benchmark
  -> compare providers
  -> inspect failure cases
  -> improve retrieval/context/prompt
  -> rerun staged benchmark
  -> visualize results in admin dashboard
  -> use doctor review as human evaluation signal
```

Vòng lặp này làm cho dự án có khả năng cải thiện liên tục thay vì chỉ thử nhiều model một cách rời rạc.

## XIII. Hạn Chế Hiện Tại

Các hạn chế cần nói rõ để tránh overclaim:

1. **Không claim clinical performance.** Tất cả benchmark hiện là proxy/open/de-identified evaluation.

2. **Real EHR benchmark chưa chạy.** MIMIC-IV-Note/MIMIC-IV-BHC vẫn cần credentialed access và governance approval.

3. **Doctor workflow chưa hoàn toàn dùng full Qdrant RAG production path.** Hiện doctor generation đã evidence-first/structured context, nhưng full MiniLM + Qdrant cần wire chặt hơn vào doctor endpoint.

4. **BERTScore là optional.** Cần đảm bảo dependency/model cache có sẵn nếu muốn tính chính thức trong mọi run.

5. **Human evaluation chưa có nhiều reviewer thật.** Rubric đã có hướng, nhưng cần nhiều đánh giá từ clinician/human reviewer để có số liệu meaningful.

6. **Qwen/Llama/Gemini chỉ là testing providers.** Không được trình bày là clinical-ready.

7. **Metrics vẫn là proxy.** Citation/factuality proxy tốt hơn ROUGE, nhưng vẫn chưa thay thế được clinical review.

## XIV. Roadmap Và Future Improvements

### Priority 1 - Wire Full RAG Into Doctor Workflow

Mục tiêu:

```text
Doctor generation
  -> chunk patient notes
  -> MiniLM embeddings
  -> Qdrant retrieval
  -> clinical context builder
  -> provider generation
  -> citation validation
  -> doctor review
```

Đây là bước quan trọng nhất để đồng nhất benchmark RAG và doctor-facing workflow.

### Priority 2 - Improve Retrieval Quality

Các cải tiến đề xuất:

- section-aware retrieval;
- query theo từng mục diagnosis/medication/timeline/plan;
- reranking;
- patient/encounter scope validation;
- wrong-patient citation prevention;
- conflict evidence visibility;
- retrieval quality gate trước generation.

### Priority 3 - Dataset Diversity

Thêm và normalize:

- MTS-Dialog;
- MEDIQA-Sum;
- synthetic structured EHR cases;
- messy formatting cases;
- stratified subsets theo note length, diagnosis density, medication density, timeline complexity.

### Priority 4 - Human Evaluation At Scale

Hoàn thiện:

- rubric form;
- doctor edit diff;
- approve/reject reason analytics;
- reviewer signature;
- final approved summary lock;
- export human evaluation dataset.

### Priority 5 - Production Safety Layer

Trước real EHR cần:

- PHI-safe logging;
- access control hardening;
- audit export;
- unsupported claim blocking option;
- medical NLI/factuality validation;
- encounter-scope validation;
- conflict resolution workflow.

### Priority 6 - Background Jobs

Heavy generation nên chuyển khỏi synchronous API:

- enqueue job;
- progress status;
- cancel job;
- timeout;
- model warmup;
- model readiness screen;
- cached model status.

## XV. Kết Luận Week 3

Week 3 là một bước tiến rất tốt của dự án. Nếu Week 2 chứng minh hệ thống đã chạy được, thì Week 3 chứng minh hệ thống bắt đầu đo lường và giải thích được kết quả. Đây là khác biệt quan trọng giữa một demo AI bình thường và một Clinical NLP MVP nghiêm túc.

Điểm mạnh lớn nhất hiện tại là dự án đã đi đúng hướng: không chỉ hỏi "model nào tóm tắt hay hơn", mà hỏi "summary này có evidence không, có bỏ sót diagnosis/medication/timeline không, có hallucination không, bác sĩ có review được không, và lỗi nằm ở retrieval hay generation".

RAG/evidence-first hiện nên được xem là hướng chính cho Medical Record Summarization MVP. BART/Pegasus vẫn hữu ích làm baseline, nhưng kiến trúc nên ưu tiên retrieval-grounded summarization với citation validation và human review. Qwen2.5/Llama3.2/Gemini optional provider cho thấy hệ thống có thể mở rộng provider linh hoạt, nhưng mọi output vẫn phải là draft và phải qua doctor review.

Kết luận có thể nói với mentor:

> Trong Week 3, em đã chuyển hệ thống từ một MVP generate summary sang một PoC đánh giá được nhiều flow, nhiều provider và nhiều metric. Kết quả quan trọng nhất là RAG/evidence-first pipeline trở thành hướng kỹ thuật phù hợp nhất cho bài toán Medical Record Summarization, vì nó giúp giảm hallucination, tăng traceability, hỗ trợ citation review và phù hợp hơn với workflow bác sĩ. Hệ thống hiện vẫn là proxy evaluation, chưa claim clinical performance, nhưng đã có nền tảng tốt để tiếp tục mở rộng sang benchmark 500+ records, cross-dataset evaluation và full RAG integration vào doctor workflow.
