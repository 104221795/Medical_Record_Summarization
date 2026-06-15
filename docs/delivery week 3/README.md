# Báo Cáo Tiến Độ Delivery Week 3

## Medical Record Summarization MVP

**Người thực hiện:** Sơn
**Dự án:** Citation-grounded Medical Record Summarization MVP
**Thời điểm cập nhật:** 12/06/2026
**Trạng thái tổng quan:** PoC end-to-end đã chuyển từ mức “generate được summary” sang mức có thể đánh giá, so sánh và giải thích chất lượng theo nhiều flow, nhiều provider, nhiều metric và nhiều failure pattern.

---

## 1. Executive Summary

Trong Week 3, dự án đã đạt một bước tiến quan trọng: hệ thống không còn chỉ là một MVP tạo bản tóm tắt y tế, mà đã phát triển thành một PoC có khả năng đánh giá chất lượng summary theo hướng evidence-grounded. Trọng tâm của tuần này là xây dựng và kiểm chứng pipeline RAG/evidence-first, mở rộng provider ngoài BART/Pegasus, chuẩn hóa benchmark artifacts, cải thiện doctor review workflow và đưa các metric gần hơn với yêu cầu của Clinical NLP.

Kết quả quan trọng nhất là Flow 2.1 cho thấy các mô hình decoder-only instruction-following như Qwen2.5 và Llama3.2 phù hợp hơn với bài toán RAG/evidence-first so với các mô hình encoder-decoder summarization truyền thống như BART/Pegasus. Cụ thể, Qwen2.5 đạt citation coverage 0.8747 và BERTScore F1 0.8583; Llama3.2 đạt faithfulness proxy 0.8817 và critical omission thấp nhất trong nhóm. Trong khi đó, BART/Pegasus vẫn có vai trò baseline, nhưng bộc lộ hạn chế rõ trong citation grounding, timeline completeness và critical information preservation.

Tuy nhiên, toàn bộ kết quả hiện tại vẫn là **proxy evaluation**, chưa chứng minh clinical safety, clinical effectiveness hoặc khả năng triển khai thực tế trên real EHR. Hệ thống vẫn cần full RAG integration vào doctor workflow, dữ liệu đa dạng hơn, human evaluation từ reviewer có chuyên môn và cơ chế governance chặt hơn trước khi có thể đưa ra bất kỳ claim nào về hiệu quả lâm sàng.

---
## 1.1. Key Deliverables Trong Week 3

Các deliverables chính của Week 3 gồm:

* **Multi-flow benchmark framework:** hệ thống đã phân biệt rõ Flow 1, Flow 1.5, Flow 2 và Flow 2.1 để đánh giá raw summarization, clinical context summarization và retrieval-grounded summarization trong các điều kiện khác nhau.
* **Flow 2.1 RAG Best Models benchmark:** đã chạy benchmark so sánh BART, Pegasus CNN/DailyMail, Qwen2.5 và Llama3.2 trên cùng evidence-first setup, kèm ROUGE, BERTScore, citation coverage, faithfulness proxy và failure pattern.
* **Local LLM provider integration:** Qwen2.5 và Llama3.2 đã được tích hợp qua Ollama/LiteLLM Gateway, giúp hệ thống mở rộng ngoài nhóm BART/Pegasus baseline.
* **RAG/evidence-first evaluation pipeline:** MiniLM embedding, chunking, retrieval, evidence packing và citation-oriented metrics đã được đưa vào trung tâm đánh giá.
* **Admin evaluation artifacts:** các output như `model_comparison.csv`, `per_record_metrics.csv`, prediction files, run summary và evaluation report đã được chuẩn hóa để phục vụ dashboard và reproducibility.
* **Doctor review workflow improvement:** doctor-facing UI đã bắt đầu chuyển sang hướng evidence-first review, với trọng tâm là generated draft, source evidence, citation/claim status, unsupported claims và audit trail.
* **HITL evaluation direction:** rubric cho human/doctor review đã được định hình rõ hơn, tạo nền tảng để biến edit/reject/approve action thành evaluation signal cho các tuần tiếp theo.

---

## 1.2. Current Risks And Blockers

Một số rủi ro và điểm nghẽn hiện tại cần được theo dõi trong Week 4:

* **Gemini API availability chưa ổn định:** Gemini 2.5 Flash Lite vẫn phụ thuộc vào external API availability và có thể gặp lỗi high demand/503, nên chưa nên đưa vào official benchmark snapshot nếu run chưa hoàn tất ổn định.
* **Local GPU/VRAM giới hạn:** Qwen2.5 và Llama3.2 chạy được qua Ollama, nhưng máy local sử dụng GPU 4GB VRAM nên cần kiểm soát context length, số retrieved chunks và max output tokens để tránh CUDA out-of-memory.
* **Doctor UI cần tiếp tục tối ưu:** doctor-facing workflow đã đúng hướng evidence-first ở mức prototype, nhưng Generate Summary và Review & Evidence vẫn cần cải thiện thêm về layout density, citation hover/click, evidence traceability và thao tác review cho bác sĩ.
* **Doctor workflow chưa full production RAG:** benchmark RAG đã chạy được, nhưng doctor generation endpoint vẫn cần được wire chặt hơn với full MiniLM + Qdrant retrieval path để đồng nhất giữa evaluation pipeline và product workflow.
* **Human evaluation chưa đủ lớn:** hiện đã có rubric và HITL direction, nhưng vẫn cần nhiều reviewer có chuyên môn hơn để tạo kết quả đánh giá có ý nghĩa hơn.
* **Real EHR datasets cần governance:** các benchmark hiện vẫn là proxy/de-identified evaluation; MIMIC-IV-Note hoặc MIMIC-IV-BHC cần credentialed access và governance approval trước khi dùng cho đánh giá sát thực tế hơn.


## 2. Mục Tiêu Và Trọng Tâm Week 3

Mục tiêu của Week 3 không chỉ là bổ sung thêm model, mà là xây dựng một vòng lặp đánh giá có kiểm soát cho Medical Record Summarization MVP. Cụ thể, tuần này tập trung vào bốn nhóm công việc chính:

1. **Mở rộng benchmark từ single-flow sang multi-flow evaluation**, để phân biệt raw summarization, clinical context summarization và retrieval-grounded summarization.
2. **Kiểm chứng hướng RAG/evidence-first**, nhằm đánh giá liệu retrieval, citation grounding và structured context có phù hợp hơn cho bài toán medical summary hay không.
3. **Mở rộng provider layer**, bao gồm local LLM qua Ollama như Qwen2.5 và Llama3.2, bên cạnh BART/Pegasus baseline.
4. **Cải thiện demo workflow**, gồm admin evaluation dashboard, doctor-facing generation/review workflow, evidence review và audit trail.

Điểm tiến bộ cốt lõi là hệ thống đã bắt đầu trả lời được câu hỏi quan trọng hơn: không phải “model nào viết summary nghe hay hơn”, mà là “summary có bằng chứng không, có bỏ sót thông tin quan trọng không, có hallucination không, bác sĩ có kiểm tra được không, và lỗi nằm ở retrieval hay generation”.

---

## 3. Tiến Độ Kỹ Thuật Chính

### 3.1. Benchmark Đã Được Mở Rộng Thành Nhiều Flow

Trong Week 2, benchmark chủ yếu xoay quanh raw/medium summarization với BART và Pegasus. Sang Week 3, hệ thống đã được tổ chức lại theo nhiều flow rõ ràng hơn:

| Flow     | Tên                      | Mô tả                                                                                   | Vai trò                                                             |
| -------- | ------------------------ | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Flow 1   | Raw Summarization        | `source_note -> summarizer -> metrics`                                                  | Baseline ban đầu để đánh giá khả năng tóm tắt trực tiếp             |
| Flow 1.5 | Clinical Context Builder | `source_note -> structured clinical context -> summarizer -> metrics`                   | Kiểm tra tác động của structured clinical context                   |
| Flow 2   | RAG Grounded             | `source_note -> chunk -> MiniLM -> retrieve evidence -> summarizer -> citation metrics` | Đánh giá retrieval-grounded summarization                           |
| Flow 2.1 | RAG Best Models          | `retrieved evidence -> strict prompt -> provider comparison`                            | So sánh BART/Pegasus với Qwen/Llama trong cùng evidence-first setup |

Cách tổ chức này giúp benchmark có tính giải thích tốt hơn. Nếu Flow 1 cho thấy giới hạn của raw summarization, Flow 1.5 cho thấy tác dụng của structured context, thì Flow 2 và Flow 2.1 giúp đánh giá trực tiếp giá trị của retrieval, citation grounding và evidence-first prompt.

---

### 3.2. Provider Layer Đã Được Mở Rộng Có Kiểm Soát

Week 3 đã mở rộng provider layer từ nhóm BART/Pegasus sang nhiều loại provider hơn:

| Provider               | Backend/Model                     | Vai trò                                                        |
| ---------------------- | --------------------------------- | -------------------------------------------------------------- |
| Deterministic baseline | `deterministic_sentence_baseline` | Extractive baseline, kiểm tra pipeline                         |
| BART                   | `facebook/bart-large-cnn`         | Local Hugging Face summarization baseline                      |
| Pegasus CNN/DailyMail  | `google/pegasus-cnn_dailymail`    | General summarization baseline                                 |
| Pegasus XSum           | `google/pegasus-xsum`             | Single-summary baseline                                        |
| Pegasus PubMed         | `google/pegasus-pubmed`           | Medical/scientific Pegasus checkpoint                          |
| Qwen2.5                | `ollama/qwen2.5:3b`               | Local LLM testing provider                                     |
| Llama3.2               | `ollama/llama3.2:3b`              | Local LLM testing provider                                     |
| Gemini 2.5 Flash Lite  | `gemini/gemini-2.5-flash-lite`    | Optional cloud provider, phụ thuộc API availability/governance |

Việc bổ sung Qwen2.5 và Llama3.2 có ý nghĩa quan trọng vì hai provider này là decoder-only instruction-following models, phù hợp hơn với prompt dạng evidence-grounded so với BART/Pegasus. Tuy nhiên, các provider này vẫn được xem là **testing providers**, không được trình bày như clinical-ready models.

---

### 3.3. LLM Gateway Đã Được Tập Trung Hóa

Thay vì gọi từng provider rời rạc trong nhiều script, hệ thống đã tập trung hóa model routing qua LLM Gateway. Gateway giúp chuẩn hóa:

* model alias nội bộ;
* timeout;
* max tokens;
* local context window;
* routing giữa Ollama và Gemini;
* output cleaning;
* error handling;
* khả năng thay đổi provider trong tương lai.

Đây là cải tiến đúng hướng vì provider orchestration là một phần quan trọng nếu hệ thống cần mở rộng sang nhiều model, nhiều môi trường hoặc enterprise gateway.

---

## 4. RAG/Evidence-first Là Hướng Phù Hợp Hơn Cho Bài Toán

### 4.1. Vì Sao Raw Summarization Chưa Đủ

Raw summarization có giá trị làm baseline, nhưng chưa đủ cho Medical Record Summarization vì bản chất dữ liệu bệnh án khác với văn bản thông thường. Clinical notes thường dài, rời rạc, có nhiều diagnosis, medication, timeline event, lab result và plan. Nếu chỉ đưa toàn bộ note vào model để tóm tắt, hệ thống dễ gặp các vấn đề:

* bỏ sót diagnosis hoặc medication quan trọng;
* lẫn giữa timeline, assessment và plan;
* sinh câu nghe hợp lý nhưng không có source evidence;
* không chỉ ra được claim nào lấy từ đâu;
* ROUGE có thể tốt nhưng summary vẫn không an toàn hoặc không đủ clinical usefulness.

Vì vậy, bài toán này không nên được xem đơn thuần là abstractive summarization, mà nên được xem là **retrieval-grounded clinical summarization**.

---

### 4.2. Clinical Context Builder Là Bước Trung Gian Có Giá Trị

Flow 1.5 sử dụng Clinical Context Builder để tổ chức lại input thành các section như:

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

Kết quả cho thấy structured context giúp BART/Pegasus hoạt động tốt hơn so với raw summarization trong một số metric, đặc biệt là ROUGE-L và citation-related proxy. Điều này cho thấy việc tổ chức lại input theo clinical section có tác dụng tích cực.

Tuy nhiên, Clinical Context Builder vẫn chưa giải quyết hoàn toàn bài toán traceability. Nó giúp model đọc input rõ hơn, nhưng chưa đủ để bảo đảm rằng từng claim trong summary đều có evidence rõ ràng. Do đó, Flow 1.5 là bước cải thiện cần thiết, nhưng chưa phải kiến trúc cuối cùng.

---

### 4.3. RAG Là Hướng Chính Của Hệ Thống

Flow 2 và Flow 2.1 đưa retrieval vào trước generation:

```text
source note
  -> chunking
  -> MiniLM embedding
  -> vector retrieval
  -> evidence pack
  -> structured clinical context
  -> provider generation
  -> citation/failure metrics
```

Cách tiếp cận này phù hợp hơn với bài toán clinical summary vì nó buộc model làm việc trên evidence cụ thể thay vì đọc lan man toàn bộ note. RAG cũng tạo nền tảng cho citation coverage, unsupported claim detection và doctor review workflow.

Kết luận kỹ thuật của Week 3 là: **RAG/evidence-first nên là hướng kiến trúc chính của MVP**, trong khi BART/Pegasus nên được giữ lại như baseline để so sánh.

---

## 5. Kết Quả Định Lượng Chính

### 5.1. Flow 2 - Retrieval-Grounded Benchmark Optimized

Run Flow 2 được thực hiện trên 50 records, sử dụng MiniLM embedding và Qdrant memory vector store.

**Retrieval metrics:**

| Metric                    | Result |
| ------------------------- | -----: |
| Average chunks per record |   4.12 |
| Average retrieved chunks  |   4.96 |
| Average context tokens    | 753.70 |
| Recall@5 proxy            | 0.9512 |
| MRR proxy                 | 0.9600 |
| nDCG@5 proxy              | 0.8919 |

Các kết quả này cho thấy retrieval pipeline đã đạt mức đủ tốt trong proxy setup. Recall@5 và MRR cao cho thấy hệ thống thường retrieve được các chunks liên quan ở vị trí tốt, tạo điều kiện để model sinh summary có grounding tốt hơn.

**Model comparison snapshot:**

| Model                 | Records | ROUGE-L | BERTScore F1 | Citation coverage | Unsupported claim rate | Faithfulness proxy | Latency p95 ms |
| --------------------- | ------: | ------: | -----------: | ----------------: | ---------------------: | -----------------: | -------------: |
| deterministic         |      50 |  0.1625 |       0.7858 |            0.9237 |                 0.0000 |             0.9018 |            0.0 |
| BART                  |      50 |  0.1388 |       0.8229 |            0.3047 |                 0.0000 |             0.7592 |      33,423.85 |
| Pegasus XSum          |      50 |  0.0973 |       0.8276 |            0.5200 |                 0.0600 |             0.7266 |      19,533.30 |
| Pegasus PubMed        |      50 |  0.1733 |       0.8236 |            0.6429 |                 0.4573 |             0.6067 |      94,318.55 |
| Pegasus CNN/DailyMail |      50 |  0.1490 |       0.8271 |            0.4083 |                 0.0000 |             0.7922 |      69,205.05 |

Điểm đáng chú ý là deterministic baseline có citation coverage và faithfulness proxy cao vì nó thiên về extractive/evidence-bound output. Trong khi đó, BART/Pegasus vẫn có giá trị baseline nhưng chưa đủ mạnh nếu thiếu instruction-following và citation-grounded synthesis.

---

### 5.2. Flow 2.1 - RAG Best Models Benchmark

Flow 2.1 là kết quả nổi bật nhất trong Week 3 vì nó so sánh BART/Pegasus với Qwen2.5 và Llama3.2 trong cùng điều kiện RAG/evidence-first.

**Run setup:**

```text
Records: 20
Embedding: sentence-transformers/all-MiniLM-L6-v2
Vector store: Qdrant memory
Providers: BART, Pegasus CNN/DailyMail, Qwen2.5, Llama3.2
Gemini: optional, excluded from official no-Gemini snapshot due to API availability
```

**Retrieval metrics:**

| Metric                    | Result |
| ------------------------- | -----: |
| Average chunks per record |   3.55 |
| Average retrieved chunks  |   3.15 |
| Average context tokens    | 733.15 |
| Recall@5 proxy            | 0.9275 |
| MRR proxy                 | 0.9750 |
| nDCG@5 proxy              | 0.8533 |

**Model comparison:**

| Model                 | Records | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore F1 | Citation coverage | Faithfulness proxy | Hallucinated entity avg | Critical omission |
| --------------------- | ------: | ------: | ------: | ------: | -----------: | ----------------: | -----------------: | ----------------------: | ----------------: |
| BART                  |      20 |  0.1138 |  0.0140 |  0.0793 |       0.8074 |            0.1483 |             0.7873 |                    1.75 |            0.9722 |
| Pegasus CNN/DailyMail |      20 |  0.1663 |  0.0716 |  0.1380 |       0.8174 |            0.3167 |             0.8142 |                    0.95 |            0.8542 |
| Qwen2.5               |      20 |  0.3758 |  0.1810 |  0.2607 |       0.8583 |            0.8747 |             0.8715 |                    0.10 |            0.5486 |
| Llama3.2              |      20 |  0.3735 |  0.1826 |  0.2603 |       0.8559 |            0.8576 |             0.8817 |                    0.35 |            0.4375 |

**Failure pattern comparison:**

| Model                 | No major proxy failure | Hallucinated content | Missing diagnosis | Missing medication | Missing timeline | Retrieval-related failure |
| --------------------- | ---------------------: | -------------------: | ----------------: | -----------------: | ---------------: | ------------------------: |
| BART                  |                      0 |                   19 |                 5 |                  1 |               12 |                        11 |
| Pegasus CNN/DailyMail |                      3 |                   11 |                 5 |                  2 |               10 |                         9 |
| Qwen2.5               |                     11 |                    2 |                 3 |                  2 |                5 |                         5 |
| Llama3.2              |                      9 |                    6 |                 4 |                  2 |                3 |                         3 |

Kết quả này cho thấy Qwen2.5 và Llama3.2 vượt BART/Pegasus rõ ràng trong RAG/evidence-first setting. Qwen2.5 đạt ROUGE-L và BERTScore F1 cao nhất, đồng thời có citation coverage 0.8747 và hallucinated entity average rất thấp. Llama3.2 đạt faithfulness proxy cao nhất và critical omission thấp nhất, cho thấy khả năng giữ lại thông tin quan trọng tốt hơn.

Điều này củng cố nhận định rằng BART/Pegasus phù hợp hơn với document compression, trong khi RAG clinical summarization cần instruction-following, evidence selection và citation-aware generation.

---

### 5.3. Flow 1.5 - Clinical Context Benchmark

Flow 1.5 kiểm tra tác động của structured clinical context trước khi generation.

| Model                 | Records | ROUGE-L | BERTScore F1 | Citation coverage | Faithfulness proxy | Timeline completeness | Latency p95 ms |
| --------------------- | ------: | ------: | -----------: | ----------------: | -----------------: | --------------------: | -------------: |
| deterministic         |      50 |  0.1008 |       0.7877 |            0.5515 |             0.7839 |                0.1237 |            0.0 |
| BART                  |      50 |  0.2077 |       0.8453 |            0.8500 |             0.7938 |                0.2742 |      41,181.75 |
| Pegasus XSum          |      50 |  0.1448 |       0.8471 |            1.0000 |             0.7539 |                0.1720 |      16,060.55 |
| Pegasus PubMed        |      50 |  0.1732 |       0.8240 |            0.8126 |             0.6080 |                0.1720 |      93,506.60 |
| Pegasus CNN/DailyMail |      50 |  0.1766 |       0.8328 |            0.9633 |             0.7827 |                0.1452 |      66,673.00 |

Flow 1.5 cho thấy BART hoạt động tốt hơn khi input được tổ chức thành clinical context có cấu trúc. Điều này giải thích vì sao BART có thể perform tốt ở Clinical Context Benchmark nhưng lại giảm mạnh ở Flow 2.1 RAG: BART xử lý tốt bài toán nén một context tương đối sạch, nhưng không mạnh ở việc hiểu prompt dài gồm instruction, retrieved chunks, citation rule và evidence selection.

---

## 6. Ý Nghĩa Của Kết Quả

Week 3 giúp hệ thống trả lời được ba câu hỏi kỹ thuật quan trọng.

Thứ nhất, retrieval có đủ tốt để tiếp tục hướng RAG không? Câu trả lời là có. Các run RAG đạt Recall@5 proxy khoảng 0.9275-0.9512 và MRR khoảng 0.9600-0.9750, cho thấy retrieved evidence đủ ổn định để làm nền cho generation.

Thứ hai, RAG/evidence-first có giúp provider sinh summary tốt hơn không? Kết quả Flow 2.1 cho tín hiệu rõ ràng. Qwen2.5 và Llama3.2 vượt BART/Pegasus ở ROUGE-L, BERTScore F1, citation coverage, hallucination reduction và critical omission. Điều này cho thấy bài toán không nên được đóng khung như summarization thuần túy, mà nên được xem là evidence-grounded clinical synthesis.

Thứ ba, có nên bỏ BART/Pegasus không? Không. BART/Pegasus vẫn cần được giữ làm baseline vì chúng giúp chứng minh sự khác biệt giữa conventional summarization và RAG/evidence-first generation. Tuy nhiên, chúng không nên là provider trung tâm cho doctor-facing workflow nếu thiếu retrieval, context builder và citation validation.

---

## 7. Cải Thiện Frontend Và Doctor Workflow

### 7.1. Admin Evaluation Dashboard

Admin dashboard đã được cải thiện để phục vụ benchmark review và technical demo. Dashboard hiện có thể hiển thị model comparison, benchmark stages, BERTScore status, clinical proxy metrics, prediction file availability và failure analysis theo model. Điều này giúp mentor hoặc reviewer không chỉ nhìn thấy một bảng điểm trung bình, mà còn hiểu được provider nào chạy, dataset nào được dùng, artifact nào được tạo ra và metric nào đã được tính.

### 7.2. Failure Analysis Dashboard

Failure analysis đã chuyển từ mức tổng hợp sang hướng per-record review. Hệ thống có thể hỗ trợ xem input note, reference summary, generated summary, retrieved evidence, citation information và failure labels. Đây là cải tiến quan trọng vì trong Clinical NLP, các case lỗi cụ thể thường quan trọng hơn điểm trung bình. Việc biết model sai ở đâu giúp phân biệt lỗi do retrieval, prompt, provider hay source data limitation.

### 7.3. Doctor-facing Workflow

Doctor UI đã được chuyển dần sang hướng evidence-first. Các phần Generate Summary, Review & Evidence, Patient History và Audit History đã có cấu trúc rõ hơn. Đặc biệt, Review & Evidence đã bắt đầu thể hiện đúng workflow bác sĩ cần: xem generated draft, kiểm tra source evidence, quan sát citation/claim status, phát hiện unsupported claims và đưa ra quyết định approve/reject/request revision.

Tuy nhiên, phần này vẫn cần tiếp tục cải thiện. Hiện tại doctor UI đã đúng hướng về mặt product logic, nhưng chưa nên được mô tả là hoàn thiện. Các điểm cần tiếp tục tối ưu gồm: giảm scrolling, làm citation hover/click rõ hơn, cải thiện information hierarchy, làm provider selection gọn hơn và giúp bác sĩ truy vết evidence nhanh hơn.

---

## 8. Human-in-the-Loop Và Clinical Review

Week 3 đã củng cố hướng Human-in-the-Loop. Doctor workflow đã có các thao tác start review, edit, approve, reject và reject reason. Review history và audit trail cũng được dùng để ghi lại các hành động quan trọng.

Human evaluation rubric đã được định hướng theo các tiêu chí phù hợp hơn với clinical summarization:

| Tiêu chí                   | Câu hỏi đánh giá                                                |
| -------------------------- | --------------------------------------------------------------- |
| Clinical correctness       | Summary có đúng với source không?                               |
| Completeness               | Có bỏ sót diagnosis, medication hoặc timeline quan trọng không? |
| Evidence grounding         | Claim quan trọng có citation không?                             |
| Unsupported claim handling | Claim thiếu evidence có được flag rõ không?                     |
| Readability                | Bác sĩ có đọc và kiểm tra nhanh không?                          |
| Safety                     | Output có tránh recommendation không được phép không?           |
| Usefulness                 | Summary có giúp giảm thời gian review không?                    |

Điểm quan trọng là human review không chỉ là thao tác UI, mà có thể trở thành training signal cho Week 4. Các edit, reject reason và unsupported claim pattern có thể được dùng để cải thiện prompt, retrieval strategy và evidence packing.

---

## 9. Backend Và Artifact Improvements

Backend đã có nhiều cải thiện đáng kể trong Week 3:

* provider catalog rõ hơn;
* model routing qua LLM Gateway;
* Ollama local providers hoạt động với Qwen2.5 và Llama3.2;
* Gemini được giữ ở trạng thái optional do phụ thuộc API availability;
* Hugging Face loading chuyển sang AutoTokenizer/AutoModelForSeq2SeqLM thay vì high-level pipeline;
* cache model được chuẩn hóa về D drive;
* benchmark artifacts được tổ chức theo output folder;
* model comparison, per-record metrics, predictions và run summary được xuất ra để phục vụ dashboard;
* artifact writer đã được cải thiện để tránh mất kết quả khi benchmark hoàn tất.

Việc tổ chức artifact có ý nghĩa lớn đối với reproducibility. Các benchmark run cần lưu rõ dataset version, model checkpoint, provider name, prompt version, retrieval config, embedding model, generation params, environment và output folder. Đây là nền tảng để so sánh các lần chạy sau một cách có kiểm soát.

---

## 10. So Sánh Week 2 Và Week 3

| Hạng mục             | Week 2                                        | Week 3                                                              | Mức cải thiện |
| -------------------- | --------------------------------------------- | ------------------------------------------------------------------- | ------------- |
| Benchmark            | Chủ yếu BART/Pegasus medium benchmark         | Có Flow 1, Flow 1.5, Flow 2, Flow 2.1                               | Rất lớn       |
| Provider             | Deterministic, BART, Pegasus, Gemini optional | Thêm Qwen2.5, Llama3.2, Gemini Flash Lite optional                  | Rất lớn       |
| Retrieval            | Đã chọn MiniLM, bắt đầu readiness             | MiniLM + Qdrant memory, có Recall@5/MRR/nDCG                        | Rất lớn       |
| Metrics              | ROUGE là chính                                | ROUGE, BERTScore, citation, factuality proxy, failure metrics       | Rất lớn       |
| Failure analysis     | Tổng quát                                     | Theo model, theo record, có hallucination/missing/retrieval failure | Lớn           |
| Doctor workflow      | Chạy được nhưng còn thô                       | Evidence-first review workspace, có citation/claim review           | Lớn           |
| Admin dashboard      | Đọc artifacts cơ bản                          | Hiển thị nhiều flow/provider/metrics hơn                            | Lớn           |
| Provider design      | Tương đối phân tán                            | Có LLM Gateway và model alias                                       | Rất lớn       |
| Production readiness | MVP chạy được                                 | PoC có evaluation discipline và artifact tracking                   | Rất lớn       |

Tổng thể, Week 3 là bước chuyển từ “MVP chạy được” sang “PoC có thể đo lường và giải thích kết quả”. Đây là khác biệt quan trọng vì trong Clinical NLP, mô hình không thể chỉ được đánh giá bằng cảm nhận output, mà cần được đặt trong một hệ thống có evidence tracing, benchmark, failure analysis, human review và governance.

---

## 11. Hạn Chế Hiện Tại

Các hạn chế cần được ghi rõ để tránh overclaim:

1. **Chưa chứng minh clinical performance.** Toàn bộ kết quả hiện tại là proxy evaluation, chưa chứng minh clinical safety, clinical effectiveness hoặc real-world healthcare performance.

2. **Chưa chạy real EHR benchmark.** MIMIC-IV-Note hoặc MIMIC-IV-BHC vẫn cần credentialed access và governance approval.

3. **Doctor workflow chưa hoàn toàn dùng full production RAG path.** Doctor generation hiện đi theo hướng evidence-first/structured clinical context, nhưng full MiniLM + Qdrant retrieval vẫn cần được wire chặt hơn vào doctor endpoint.

4. **Gemini chưa ổn định để đưa vào official snapshot.** Gemini là optional provider và có thể bị ảnh hưởng bởi API availability, ví dụ lỗi high demand/503.

5. **Human evaluation chưa đủ lớn.** Rubric và workflow đã có, nhưng vẫn cần nhiều reviewer có chuyên môn để kết quả có ý nghĩa hơn.

6. **Qwen/Llama vẫn là testing providers.** Dù kết quả proxy tốt hơn BART/Pegasus trong Flow 2.1, hai model này chưa được xem là clinical-ready.

7. **Metric vẫn là proxy.** Citation coverage, faithfulness proxy và BERTScore giúp đánh giá tốt hơn ROUGE, nhưng không thay thế được clinical review.

---

## 12. Kế Hoạch Week 4

### Priority 1 - Wire Full RAG Into Doctor Workflow

Mục tiêu quan trọng nhất là đồng nhất benchmark RAG và doctor-facing generation workflow:

```text
Doctor generation
  -> patient/encounter scoped notes
  -> chunking
  -> MiniLM embedding
  -> Qdrant retrieval
  -> clinical context builder
  -> provider generation
  -> citation validation
  -> doctor review
```

### Priority 2 - Improve Retrieval Quality

Các cải tiến cần triển khai:

* section-aware retrieval;
* query riêng cho diagnosis, medication, timeline, plan;
* reranking;
* patient/encounter scope validation;
* wrong-patient citation prevention;
* conflict evidence visibility;
* retrieval quality gate trước generation.

### Priority 3 - Improve Doctor UI/UX

Doctor UI cần tiếp tục được tối ưu để phục vụ review thật:

* giảm scrolling ở Generate Summary;
* làm provider selection gọn hơn;
* cải thiện 3-panel Review & Evidence;
* citation hover/click phải hiển thị evidence excerpt rõ ràng;
* unsupported claims phải nổi bật hơn;
* action bar không được che nội dung;
* review workflow phải phù hợp với bác sĩ, không chỉ phù hợp với demo kỹ thuật.

### Priority 4 - Dataset Diversity

Cần mở rộng benchmark sang nhiều loại dữ liệu hơn:

* MTS-Dialog;
* MEDIQA-Sum;
* synthetic structured EHR cases;
* messy formatting cases;
* subsets theo note length, diagnosis density, medication density và timeline complexity.

### Priority 5 - Human Evaluation At Scale

Cần chuẩn hóa human evaluation:

* rubric form;
* doctor edit diff;
* approve/reject reason analytics;
* reviewer signature;
* final approved summary lock;
* export human evaluation dataset.

### Priority 6 - Background Jobs

Các tác vụ nặng nên chuyển khỏi synchronous API:

* enqueue job;
* progress status;
* cancel job;
* timeout;
* model warmup;
* model readiness screen;
* cached model status.

---

## 13. Kết Luận Week 3

Week 3 là một bước tiến quan trọng của Medical Record Summarization MVP. Nếu Week 2 chứng minh hệ thống đã chạy được, thì Week 3 chứng minh hệ thống bắt đầu có khả năng đo lường, so sánh và giải thích chất lượng output. Đây là nền tảng cần thiết để một dự án Clinical NLP vượt khỏi mức demo đơn giản.

Kết quả nổi bật nhất là RAG/evidence-first pipeline cho thấy tín hiệu tốt hơn raw summarization trong setup hiện tại. Flow 2.1 cho thấy Qwen2.5 và Llama3.2 vượt BART/Pegasus ở nhiều metric quan trọng như citation coverage, BERTScore, faithfulness proxy, hallucination reduction và critical omission. Điều này ủng hộ định hướng rằng bài toán không nên được xem là summarization thuần túy, mà là retrieval-grounded clinical summarization với citation validation và human review.

Tuy nhiên, kết quả hiện tại vẫn phải được hiểu đúng phạm vi. Đây là proxy evaluation trên benchmark/de-identified data, chưa phải clinical validation. Hệ thống chưa được dùng để đưa ra chẩn đoán, điều trị, kê đơn hoặc quyết định lâm sàng. Mọi summary vẫn phải là draft và cần được bác sĩ kiểm tra.

Tóm lại, Week 3 đã đưa dự án từ một MVP generate summary sang một PoC evidence-grounded có khả năng đánh giá, giải thích và cải thiện liên tục. Hướng phát triển hợp lý nhất cho Week 4 là tích hợp full RAG vào doctor workflow, mở rộng dataset, tăng human evaluation và tiếp tục cải thiện UI evidence review để bác sĩ có thể kiểm tra citation và unsupported claims một cách nhanh, rõ và đáng tin cậy.
