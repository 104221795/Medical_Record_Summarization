# Báo Cáo Bàn Giao Week 4

## 1. Tóm Tắt Điều Hành

Week 4 đã đưa MVP Tóm tắt Hồ sơ Y tế từ PoC nghiên cứu có grounding bằng bằng chứng ở Week 3 thành một PoC end-to-end hoàn chỉnh, sẵn sàng trình diễn trên môi trường staging cục bộ, chỉ sử dụng dữ liệu đã khử định danh và bắt buộc bác sĩ duyệt. Thay đổi chính không phải là bổ sung một năng lực lâm sàng mới hoặc đưa ra tuyên bố về hiệu quả lâm sàng, mà là hoàn thiện và ổn định toàn bộ quy trình:

```text
Dữ liệu lâm sàng đã khử định danh
  -> giới hạn theo bệnh nhân và lượt khám
  -> retrieval nhận biết từng nhóm thông tin
  -> cổng kiểm tra chất lượng retrieval
  -> tạo bản nháp có grounding bằng bằng chứng
  -> kiểm tra citation và claim thiếu bằng chứng
  -> background job được lưu bền vững
  -> không gian Review & Evidence
  -> bác sĩ chỉnh sửa/phê duyệt/từ chối
  -> khóa bản cuối và ghi nhận chữ ký reviewer
  -> audit an toàn với PHI và phân tích đánh giá
```

Quy trình này hiện được hỗ trợ bởi web service, worker, PostgreSQL và hàng đợi Redis có thể triển khai độc lập. Hệ thống chứng minh được toàn bộ vòng lặp kỹ thuật và sản phẩm, từ dữ liệu nguồn đến bước bác sĩ review có kiểm soát, đồng thời duy trì ranh giới rằng mọi output do AI tạo ra chỉ là bản nháp cho đến khi được người có thẩm quyền phê duyệt.

Khối lượng bàn giao kể từ báo cáo Week 3 ban đầu là đáng kể: phần chênh lệch repository từ commit `32fa429` đến commit hiện tại `75c89fd` gồm 103 file thay đổi, 11.380 dòng thêm và 2.241 dòng xóa. Nhánh `main` hiện khớp với `origin/main`.

Quá trình xác minh kết thúc với 165 backend test pass và không có test fail, bộ test tập trung vào deployment có 19 test pass, Docker build thành công và môi trường Docker Compose staging cục bộ chạy thành công. Topology đã xác minh gồm FastAPI web, RQ worker, PostgreSQL và Redis. PostgreSQL ở trạng thái healthy, Redis đang chạy, web service healthy, worker đã đăng ký, `/health` trả HTTP 200 và `/ready` trả HTTP 200 cùng thông tin readiness có cấu trúc cho database, queue, worker và provider.

Ranh giới dependency của runtime cũng đã được sửa. Deployment image chỉ cài `requirements-runtime.txt`; các package ML và benchmark nặng dành cho local nằm trong `requirements-ml.txt`. Image cuối có kích thước xấp xỉ 122 MB. Quá trình xác minh xác nhận Torch, Transformers, sentence-transformers, BERTScore, datasets, evaluate, MLflow, sentencepiece, CUDA và các package NVIDIA không có trong image.

Việc triển khai Railway công khai chưa được thực hiện vì không có hosting credit. Đây là giới hạn vận hành về tài nguyên hosting, không phải blocker về kiến trúc hệ thống. Topology Railway-ready dự kiến đã được xác minh cục bộ thông qua Docker Compose staging. Báo cáo không đưa ra tuyên bố về mức độ sẵn sàng vận hành thực tế trong bệnh viện, độ an toàn lâm sàng hoặc hiệu quả lâm sàng.

## 1.1 Tóm Tắt Dành Cho Reviewer

| Hạng mục | Trạng thái |
| --- | --- |
| Trạng thái tổng thể | PoC staging cục bộ sẵn sàng trình diễn |
| Xác minh | 165 backend test pass; bộ test tập trung vào deployment pass; Docker build pass; Docker Compose pass; `/health` và `/ready` trả HTTP 200 |
| Triển khai | Kiến trúc Railway-ready đã được chuẩn bị; triển khai Railway công khai được hoãn do giới hạn hosting credit |
| Ranh giới runtime | Staging image gọn nhẹ không chứa Torch, Transformers, sentence-transformers, BERTScore, datasets, evaluate, MLflow, CUDA và các package NVIDIA |
| Ranh giới an toàn | Summary do AI tạo ra vẫn là bản nháp chỉ dành cho bác sĩ review; không có tuyên bố về độ an toàn hoặc hiệu quả lâm sàng |
| Hành động tiếp theo | Ghi hình demo cục bộ, đóng gói bằng chứng và tùy chọn triển khai public cloud khi có đủ tài nguyên hosting |

## 2. Baseline Week 3

Week 3 thiết lập định hướng nghiên cứu và sản phẩm, chưa phải một hệ thống hoàn chỉnh về deployment. Baseline gồm:

- định hướng tóm tắt RAG/evidence-first dành cho bác sĩ;
- retrieval và xây dựng clinical context;
- truy vết citation và review claim thiếu bằng chứng;
- phiên bản ban đầu của không gian Review & Evidence;
- thử nghiệm provider deterministic, BART, Pegasus, Qwen, Llama và Gemini tùy chọn;
- benchmark artifact và so sánh provider;
- kế hoạch đa dạng dataset và human evaluation;
- kế hoạch background job dùng Redis/RQ;
- mục tiêu về deployment readiness.

### 2.1 Baseline Benchmark Week 3

Week 3 thiết lập hai mốc benchmark quan trọng để diễn giải kết quả Week 4.

Thứ nhất, baseline retrieval-grounded tối ưu trên 50 record đánh giá deterministic và các summarizer encoder-decoder. Mọi provider đều hoàn thành 50/50 record. Retrieval đạt Recall@5 `0.9512`, MRR `0.9600` và nDCG@5 `0.8919`. Baseline deterministic bị ràng buộc theo bằng chứng đạt citation coverage cao nhất (`0.9237`) và faithfulness proxy cao nhất (`0.9018`). Các biến thể BART và Pegasus có BERTScore cao hơn nhưng yếu hơn về citation grounding và có nhiều tín hiệu bỏ sót thông tin hơn.

Thứ hai, Flow 2.1 của Week 3 so sánh BART, Pegasus CNN/DailyMail, Qwen2.5 và Llama3.2 trên 20 record trong cùng thiết lập evidence-first. Đây là thí nghiệm chính để lựa chọn model:

| Provider trong Flow 2.1 Week 3 | Hoàn thành | ROUGE-L | BERTScore F1 | Citation coverage | Faithfulness proxy | Timeline completeness | Trung bình entity hallucination | Critical omission rate | Latency p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BART | 20/20 | `0.0793` | `0.8074` | `0.1483` | `0.7873` | `0.0000` | `1.75` | `0.9722` | `25,714.50 ms` |
| Pegasus CNN/DailyMail | 20/20 | `0.1380` | `0.8174` | `0.3167` | `0.8142` | `0.1667` | `0.95` | `0.8542` | `36,024.15 ms` |
| Qwen2.5 | 20/20 | `0.2607` | `0.8583` | `0.8747` | `0.8715` | `0.4722` | `0.10` | `0.5486` | `15,504.75 ms` |
| Llama3.2 | 20/20 | `0.2603` | `0.8559` | `0.8576` | `0.8817` | `0.6250` | `0.35` | `0.4375` | `16,051.20 ms` |

Kết luận của Week 3 có phạm vi cụ thể: trong thiết lập 20 record này, Qwen2.5 và Llama3.2 là các ứng viên mạnh hơn BART/Pegasus cho tác vụ tổng hợp evidence-first. Qwen2.5 dẫn đầu về ROUGE-L, BERTScore F1 và citation coverage; Llama3.2 dẫn đầu về faithfulness proxy, timeline completeness và critical omission thấp nhất. Đây là tín hiệu lựa chọn provider từ benchmark proxy, không phải kết quả thẩm định lâm sàng.

Báo cáo Week 3 đã xác định rõ các ưu tiên cho Week 4: kết nối đầy đủ RAG vào doctor workflow, bổ sung bảo vệ theo patient/encounter, đưa vào retrieval quality gate, cải thiện Review & Evidence UI, mở rộng tài sản dataset governance, chuẩn hóa human evaluation và chuyển tác vụ nặng sang background job.

Week 4 đã chuyển các ưu tiên này thành hành vi hệ thống được triển khai và kiểm thử. Kết quả không chứng minh hiệu năng trên EHR thực, mức độ sẵn sàng sử dụng trong bệnh viện hoặc độ an toàn/hiệu quả lâm sàng.

## 3. Phạm Vi Bàn Giao Week 4

Week 4 tập trung vào tích hợp, kiểm soát an toàn, độ tin cậy vận hành và hardening cho deployment:

1. Kết nối doctor workflow với quá trình tạo RAG giới hạn theo patient và encounter.
2. Chặn generation hoặc approval khi bằng chứng hay phạm vi citation không đạt yêu cầu.
3. Giữ citation, unsupported claim, conflict và missing evidence để bác sĩ review.
4. Lưu bền vững background generation job và hiển thị trạng thái queue, worker, timeout, cancellation và progress.
5. Tách dependency staging gọn nhẹ khỏi dependency ML và benchmark cục bộ.
6. Xác minh cục bộ topology Railway-ready gồm web, worker, PostgreSQL và Redis.
7. Hardening authentication, readiness, CI, migration và audit.
8. Duy trì khả năng tái lập benchmark và tách biệt rõ kết quả lịch sử với kết quả hiện tại có gate nghiêm ngặt hơn.

Không có chức năng khuyến nghị chẩn đoán, khuyến nghị điều trị, kê đơn, tự động phê duyệt xuất viện, chẩn đoán hình ảnh y tế hoặc writeback vào EMR thực.

### 3.1 Ranh Giới Chấp Nhận PoC End-to-End

Trong Week 4, “PoC end-to-end” nghĩa là toàn bộ luồng trình diễn dự kiến đã được triển khai và có thể thực thi bằng dữ liệu mock hoặc dữ liệu đã khử định danh:

| Giai đoạn PoC | Hành vi đã bàn giao | Bằng chứng hoàn thành |
| --- | --- | --- |
| Input và scope | Chọn patient và encounter; giữ phạm vi source document | Doctor generation workflow và test theo encounter scope |
| Retrieval | Xây dựng bằng chứng theo diagnosis, medication, timeline, assessment, plan và diagnostics | RAG workflow, benchmark manifest và retrieval metric |
| Evidence gate | Chặn generation khi thiếu bằng chứng diagnosis/timeline bắt buộc | Hai record bị chặn trong run 50 record nghiêm ngặt |
| Generation | Route đến provider khả dụng được chọn; deterministic làm fallback cho staging smoke | Provider catalog/readiness và benchmark artifact |
| Background execution | Persist, enqueue, process, cancel, timeout và báo progress | `model_jobs`, Redis/RQ worker, job test và admin UI |
| An toàn bản nháp | Kiểm tra citation, scope, conflict và unsupported claim | Safety test và không gian Review & Evidence |
| Human review | Chỉnh sửa, approve, reject hoặc yêu cầu revision kèm lý do | Review API, UI action, rubric và analytics |
| Hoàn tất | Khóa summary đã approve và gắn reviewer signature | Review workflow và evaluation test |
| Audit | Export metadata đã làm sạch, không làm lộ raw note | Test PHI-safe audit export |
| Vận hành | Chạy web, worker, PostgreSQL và Redis cùng health/readiness check | Xác minh Docker Compose staging |

Đây là ranh giới chấp nhận của một PoC hoàn chỉnh, không phải ranh giới tích hợp bệnh viện thực tế.

## 4. Các Cải Tiến Chính So Với Week 3

### 4.1 Doctor-Facing RAG Workflow

Luồng generation dành cho bác sĩ hiện được giới hạn theo patient và encounter. Workflow chọn patient và encounter, retrieve bằng chứng liên quan, xây dựng clinical context nhận biết từng section, tạo bản nháp bằng provider được chọn, kiểm tra citation và unsupported claim, sau đó chuyển kết quả sang Review & Evidence.

Thay đổi này khép lại khoảng trống chính của Week 3 giữa benchmark research path và product path. Summary được tạo ra vẫn là bản nháp. Nó không được xem là tài liệu đã phê duyệt cho đến khi một bác sĩ có thẩm quyền hoàn thành review.

Không gian Review & Evidence hỗ trợ xem source evidence, chỉnh sửa draft, kiểm tra citation và claim, hiển thị unsupported claim, đồng thời xử lý approve/reject/request revision. Trạng thái readiness của provider được hiển thị cho người dùng; provider không khả dụng bị vô hiệu hóa thay vì được chọn ngầm.

### 4.2 Retrieval Grounding Và Evidence Gate

Retrieval đã được nâng từ định hướng evidence-first chung thành hành vi có gate rõ ràng:

- retrieval được bảo vệ theo patient và encounter scope;
- bằng chứng lâm sàng được tổ chức theo diagnosis, medications, timeline, assessment, plan và diagnostics;
- fact không được mượn giữa các section nếu section tương ứng không có bằng chứng hợp lệ;
- bằng chứng cho plan phải thể hiện ý định tương lai, không phân loại lại chăm sóc đã hoàn tất thành kế hoạch;
- diagnosis và timeline là các section retrieval bắt buộc;
- medication evidence có thể tạo warning;
- generation bị chặn nếu retrieval quality gate không đạt yêu cầu bằng chứng bắt buộc.

Benchmark manifest ngày 17/06 xác nhận stricter gate đã được bật và cấu hình để chặn generation. Cả 50/50 record đều được benchmark xử lý và đánh giá cho từng provider. Trong đó, 48 record có summary được tạo thành công, còn hai record (`multiclinsum_ls_en_10012` và `multiclinsum_ls_en_10018`) bị retrieval gate chặn có chủ đích với lý do `missing_diagnosis_evidence`. Vì vậy, đây là 50/50 record được đánh giá, gồm 48 generation thành công và 2 refusal có kiểm soát; không phải benchmark bỏ sót hai record hoặc provider bị crash.

### 4.3 An Toàn Lâm Sàng Và Guardrail

Week 4 bổ sung hoặc xác minh các kiểm soát an toàn ở cấp hệ thống quanh draft workflow:

- claim không được hỗ trợ hoặc thiếu bằng chứng vẫn hiển thị và có thể chặn approval;
- citation sai patient được phát hiện và chặn trước approval;
- citation không khớp encounter scope được kiểm tra;
- citation và source evidence tiếp tục khả dụng để truy vết;
- audit export loại bỏ free text và raw-note field không an toàn, đồng thời trả `phi_safe: true`;
- audit event nhạy cảm lưu metadata đã làm sạch thay vì nội dung clinical note thô;
- summary đã approve phải qua review của bác sĩ có thẩm quyền;
- summary đã approve được đánh dấu final-locked và có reviewer signature;
- output AI không được trình bày như chẩn đoán, điều trị, kê đơn hoặc quyết định lâm sàng tự động.

Đây là guardrail cho workflow và phần mềm. Chúng không phải bằng chứng xác nhận độ an toàn hoặc hiệu quả lâm sàng của hệ thống.

### 4.4 Benchmark Provider Và Đánh Giá 50 Record

Benchmark nghiêm ngặt hiện tại so sánh năm provider trên cùng tập yêu cầu 50 record:

- deterministic;
- BART;
- Pegasus;
- Qwen2.5;
- Llama3.2.

Cả năm provider đều xử lý đủ 50/50 record. Với mỗi provider, 48 record tạo summary thành công và hai record bị retrieval quality gate chặn khi thiếu bằng chứng diagnosis bắt buộc. BERTScore không được yêu cầu trong run nghiêm ngặt này.

Kết quả chính xác theo provider:

| Provider trong run nghiêm ngặt Week 4 | Trạng thái xử lý | ROUGE-L | Citation coverage | Unsupported claim rate | Faithfulness proxy | Timeline completeness | Trung bình entity hallucination | Critical omission rate | Latency p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Deterministic | 50/50 được đánh giá; 48 generated; 2 blocked | `0.1752` | `0.9135` | `0.0000` | `0.9032` | `0.6556` | `0.0000` | `0.3794` | `0.00 ms` |
| BART | 50/50 được đánh giá; 48 generated; 2 blocked | `0.0760` | `0.1194` | `0.0000` | `0.7557` | `0.0667` | `0.0000` | `0.9571` | `22,177.65 ms` |
| Pegasus CNN/DailyMail | 50/50 được đánh giá; 48 generated; 2 blocked | `0.1493` | `0.3785` | `0.0104` | `0.7600` | `0.1333` | `0.0208` | `0.9214` | `30,963.70 ms` |
| Qwen2.5 | 50/50 được đánh giá; 48 generated; 2 blocked | `0.2105` | `0.8931` | `0.0225` | `0.8609` | `0.5167` | `0.5625` | `0.5024` | `31,282.30 ms` |
| Llama3.2 | 50/50 được đánh giá; 48 generated; 2 blocked | `0.1969` | `0.8501` | `0.0535` | `0.8426` | `0.4500` | `1.3333` | `0.5135` | `56,981.70 ms` |

**Ý nghĩa thực tiễn:** Qwen2.5 hiện là generative provider mạnh nhất cho PoC trong run có gate nghiêm ngặt. Deterministic vẫn là provider smoke/control ổn định nhất. BART và Pegasus tiếp tục hữu ích làm baseline nhưng yếu hơn đối với doctor workflow ưu tiên citation. Việc hệ thống đánh giá đủ 50/50 record nhưng chủ động chặn generation ở 2 record thiếu bằng chứng cho thấy retrieval gate đang hoạt động đúng mục tiêu. Tuy nhiên, toàn bộ kết quả vẫn là proxy evaluation, không phải thẩm định lâm sàng.

Run hiện tại củng cố một số kết quả từ Week 3:

- Qwen2.5 tiếp tục là generative provider mạnh nhất trong run hiện tại về ROUGE-L (`0.2105`), citation coverage (`0.8931`), faithfulness proxy (`0.8609`) và timeline completeness (`0.5167`).
- Llama3.2 tiếp tục có grounding tốt hơn đáng kể so với BART/Pegasus xét theo citation coverage. Tuy nhiên, hallucinated-entity proxy (`1.3333`) và p95 latency (`56,981.70 ms`) trong run lớn hơn cho thấy trade-off về độ tin cậy và vận hành rõ hơn so với kết quả 20 record ở Week 3.
- BART và Pegasus vẫn hữu ích làm baseline cho summarization truyền thống, nhưng citation coverage thấp và critical omission rate cao tiếp tục cho thấy chúng kém phù hợp hơn với doctor workflow citation-first.
- Baseline deterministic tiếp tục là control bị ràng buộc theo bằng chứng mạnh nhất. Citation coverage cao, faithfulness cao, timeline completeness tốt, hallucinated-entity proxy bằng không và latency không đáng kể khiến nó phù hợp cho smoke test và xác minh pipeline. Kết quả này không có nghĩa output extractive là summary hữu ích nhất về mặt lâm sàng.

Không được xem giá trị Week 3 và Week 4 như một thí nghiệm before/after có kiểm soát về hiệu năng model. Số lượng record, sample được chọn, context size, strict section isolation, retrieval gate và cấu hình BERTScore có khác biệt. Do đó, so sánh hợp lệ nằm ở cấp kiến trúc và định hướng: Week 3 chọn các provider tiềm năng; Week 4 vận hành các provider đó dưới cơ chế quản trị bằng chứng rộng hơn và nghiêm ngặt hơn.

Ranh giới provider hiện rõ ràng hơn:

- deterministic là fallback nhẹ cho smoke test;
- Gemini 2.5 Flash Lite là provider Railway/API tùy chọn, chỉ khả dụng khi có server-side API key và điều kiện sử dụng dữ liệu bên ngoài đã được phê duyệt;
- Qwen2.5 và Llama3.2 vẫn là local benchmark provider, trừ khi external Ollama service được cấu hình rõ ràng và vượt qua readiness check;
- BART và Pegasus vẫn là local/offline benchmark provider, không bắt buộc cho staging startup.

Sự phân tách này ngăn deployment image kế thừa toàn bộ môi trường nghiên cứu cục bộ.

#### 4.4.1 Run No-Gate Hoàn Tất 50/50 Trước Data Diversity

Sau run gated ngày 17/06, benchmark được chạy lại trên cùng `data/processed/governance/benchmark_set.jsonl`, giới hạn 50 record và trước bước data diversity. Cấu hình retrieval được giữ nguyên với MiniLM, Qdrant memory, `top-k-per-query=5`, tối đa 12 context chunk và strict section-aware context. Khác biệt có chủ đích duy nhất về governance là dùng `--disable-retrieval-gate` ở benchmark để buộc đánh giá generation trên đủ 50 record. Thay đổi này không tắt retrieval gate trong doctor-facing workflow.

Kết quả cuối gồm 250/250 prediction hoàn thành, không có prediction fail. BERTScore được tính bổ sung ngày 19/06/2026 trực tiếp từ các prediction/reference pair đã lưu bằng `roberta-large` trên CPU, batch size 2; không chạy lại generation model:

| Provider trong run no-gate 50 record | Trạng thái | ROUGE-L | BERTScore P | BERTScore R | BERTScore F1 | Citation coverage | Unsupported claim rate | Faithfulness proxy | Timeline completeness | Trung bình entity hallucination | Critical omission rate | Latency p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Deterministic | 50/50 completed | `0.1737` | `0.7440` | `0.8546` | `0.7952` | `0.9147` | `0.0000` | `0.9071` | `0.6667` | `0.0000` | `0.3688` | `0.00 ms` |
| BART | 50/50 completed | `0.0757` | `0.8217` | `0.7815` | `0.8010` | `0.1307` | `0.0000` | `0.7585` | `0.0645` | `0.0000` | `0.9583` | `59,018.25 ms` |
| Pegasus CNN/DailyMail | 50/50 completed | `0.1495` | `0.8381` | `0.8091` | `0.8232` | `0.3800` | `0.0100` | `0.7626` | `0.1290` | `0.0200` | `0.9236` | `50,691.55 ms` |
| Qwen2.5 | 50/50 completed | `0.2122` | `0.8118` | `0.8690` | `0.8391` | `0.8884` | `0.0346` | `0.8713` | `0.4785` | `0.4800` | `0.4460` | `46,864.95 ms` |
| Llama3.2 | 50/50 completed | `0.1863` | `0.7796` | `0.8545` | `0.8149` | `0.8620` | `0.0618` | `0.8413` | `0.4570` | `1.3000` | `0.5108` | `65,747.15 ms` |

Qwen2.5 tiếp tục là generative provider mạnh nhất trong run no-gate theo ROUGE-L (`0.2122`), BERTScore F1 (`0.8391`), citation coverage (`0.8884`), faithfulness proxy (`0.8713`) và critical omission thấp nhất trong nhóm generative (`0.4460`). Deterministic tiếp tục là smoke/control provider ổn định nhất. Pegasus có BERTScore F1 đứng thứ hai (`0.8232`) nhưng citation coverage và omission vẫn yếu hơn đáng kể, cho thấy semantic similarity không đủ để kết luận grounding tốt. Run này chứng minh khả năng generation đủ 50/50 trước data diversity; run gated 48 generated + 2 blocked vẫn được giữ riêng để chứng minh refusal behavior. Cả hai đều là proxy evaluation và không thay thế thẩm định lâm sàng.

Artifact cuối được lưu tại:

```text
D:\clin_summ_outputs\rag_best_models_benchmark_50_no_gate
```

### 4.5 Human Evaluation Và Auditability

Human evaluation đã tiến từ kế hoạch ở Week 3 thành các bề mặt review và analytics được triển khai. Các năng lực đã xác minh gồm:

- human-review rubric có cấu trúc;
- bác sĩ edit, approve, reject và xử lý lý do revision;
- các lựa chọn rejection reason và phân bố lý do;
- reviewer signature;
- final lock cho summary đã approve;
- human-evaluation analytics cho approval, rejection, edit, evaluation và locked summary;
- evaluation record có thể export;
- PHI-safe audit export;
- audit event cho generation, xem citation, edit, approve và reject.

Các năng lực này giúp kết quả review có thể đo lường và audit. Chúng không thay thế một đợt đánh giá có quản trị, quy mô phù hợp bởi reviewer lâm sàng đủ chuyên môn.

Dataset governance cũng được củng cố bằng tài sản để tách record thành benchmark-ready, warning và rejected. Repository hỗ trợ kế hoạch và normalization cho MultiClinSum, MTS-Dialog, MEDIQA-Sum, synthetic structured EHR và trường hợp messy formatting. Đây vẫn là tài nguyên open/proxy, synthetic hoặc đã khử định danh; báo cáo không tuyên bố đã đánh giá trên EHR thực.

### 4.6 Background Job Và Độ Tin Cậy

Tác vụ generation nặng hiện có persisted job model và execution path dùng Redis/RQ:

- bảng `model_jobs` lưu trạng thái và metadata của job;
- job có các trạng thái queued, running, completed, failed, cancelled và timed-out;
- progress và current-step được hiển thị cho UI;
- job có thể bị hủy;
- timeout được biểu diễn và kiểm thử;
- queue depth và active job được đưa vào readiness/admin visibility;
- RQ worker registration được kiểm tra cho staging readiness;
- worker heartbeat được triển khai cho local worker mode được hỗ trợ;
- persisted state vẫn có thể truy vấn sau khi refresh API/UI.

Compose worker hiện vô hiệu hóa HTTP health check kế thừa từ web image. Worker readiness được đánh giá qua queue và worker registration, thay vì yêu cầu sai rằng worker container phải phục vụ HTTP.

### 4.7 Deployment Hardening

Dependency model hiện được tách rõ:

| File | Mục đích |
| --- | --- |
| `requirements-runtime.txt` | FastAPI web/worker gọn nhẹ, database, Redis/RQ, provider API, readiness và dependency retrieval cho deployment |
| `requirements-ml.txt` | Package ML, multimodal và benchmark tùy chọn dành cho local |
| `requirements-test.txt` | Dependency chỉ dùng cho test |
| `requirements.txt` | Môi trường local research/development đầy đủ, kết hợp cả ba nhóm |

Docker runtime chỉ cài `requirements-runtime.txt`. Docker build trước đây tải các cây dependency Torch, CUDA và NVIDIA rất lớn vì dependency deployment bị trộn với dependency nghiên cứu cục bộ. Việc tách dependency đã loại các package này khỏi runtime image và giảm kích thước image cuối xuống khoảng 122 MB.

Topology staging đã xác minh cục bộ gồm:

- web service;
- worker service dùng cùng image nhưng có command riêng;
- PostgreSQL;
- Redis.

Tài liệu Railway hiện mô tả các service bắt buộc, biến môi trường, provider strategy, hành vi health/readiness, post-deploy QA, cân nhắc rollback và clinical disclaimer. Staging runtime chủ động dùng hashing-based retrieval để tránh model download và package ML nặng. Thiết lập này chỉ xác minh tính khả thi của deployment và hành vi workflow, không phải tuyên bố về hiệu năng lâm sàng.

Authentication đã được hardening cho staging:

- protected route dùng bearer-token role-based access control;
- demo role header do client kiểm soát bị vô hiệu hóa;
- staging từ chối demo-header authentication;
- public admin self-registration bị vô hiệu hóa;
- yêu cầu secret không phải giá trị mặc định và CORS được cấu hình rõ ràng.

### 4.8 CI/CD Và Xác Minh

CI hiện xác minh bề mặt deployment gọn nhẹ thông qua:

- backend smoke test và safety test;
- Alembic migration trên SQLite sạch;
- compile deployment entrypoint;
- quét pattern secret phổ biến;
- cài dependency frontend và production build;
- Docker image build.

SQLite migration regression trên database sạch được sửa trong commit cuối `75c89fd`. Trong quá trình stabilization, các full-suite failure được phân loại thay vì gộp thành một vấn đề duy nhất:

| Nhóm failure | Số lượng | Cách xử lý |
| --- | ---: | --- |
| SQLite migration regression | 1 | Sửa hành vi migration trên database sạch |
| Legacy auth/provider contract test | 12 | Đồng bộ với contract staging đã hardening |
| Nhiễm môi trường ML/MLflow cục bộ | 5 | Sửa isolation của môi trường/dependency |

Kết quả backend cuối là 165 test pass và 0 test fail. Bộ test tập trung vào deployment có 19 test pass.

### 4.9 UI Và Mức Độ Sẵn Sàng Sản Phẩm

Phần UI được mô tả chính xác nhất là workflow hardening, không phải một đợt redesign lớn. Các cải tiến đã xác minh gồm:

- lựa chọn patient và encounter rõ ràng hơn cho generation;
- hiển thị generation progress và cancellation;
- provider readiness và selectability;
- lý do provider không khả dụng;
- các panel Review & Evidence cho evidence, editable summary, citation, claim validation và unsupported claim;
- clinician review action kèm reason/comment;
- admin visibility cho Jobs & Readiness;
- human-evaluation analytics;
- audit và patient-history visibility.

Kết quả tạo ra một workflow mạch lạc hơn cho demo dành cho bác sĩ, nhưng đây vẫn là giao diện PoC và chưa được xác thực như một trải nghiệm người dùng lâm sàng trong vận hành thực tế.

### 4.10 Mức Độ Hoàn Thiện PoC End-to-End So Với Week 3

Week 3 chứng minh các thành phần RAG và benchmark cốt lõi có thể hoạt động. Week 4 chứng minh các thành phần này có thể vận hành như một ứng dụng thống nhất có quản trị:

| Năng lực | Trạng thái Week 3 | Trạng thái đã bàn giao Week 4 |
| --- | --- | --- |
| RAG | Research/evaluation pipeline và định hướng sản phẩm | Doctor generation path theo patient/encounter scope |
| Chất lượng retrieval | Retrieval metric và kế hoạch cải thiện chất lượng | Required-section gate có hành vi chặn generation |
| So sánh provider | Tín hiệu lựa chọn Qwen/Llama/BART/Pegasus trên 20 record | Thực thi 50 record có stricter gate và provider catalog nhận biết deployment |
| Citation | Grounding metric và review display ban đầu | Scope validation, unsupported visibility, approval blocking và traceability |
| Human review | Định hướng HITL và action ban đầu | Rubric, reason, analytics, reviewer signature và final lock |
| Background work | Được lên kế hoạch | Persisted Redis/RQ job có progress, cancellation, timeout và worker readiness |
| Audit | Audit trail ban đầu | Export PHI-safe đã làm sạch và bao phủ event review/generation |
| UI | Evidence-first prototype | Generation, job progress, Review & Evidence và admin readiness đã kết nối |
| Deployment | Định hướng và risk | Image gọn nhẹ cùng topology web/worker/PostgreSQL/Redis đã xác minh |
| Verification | Bằng chứng component và benchmark | 165 backend test pass, 19 deployment test pass, Docker và Compose pass |

Đây là thành tựu chính của Week 4: dự án không còn chỉ là tập hợp các thành phần RAG, benchmark, UI và deployment có triển vọng. Nó đã trở thành một PoC end-to-end mạch lạc, trong đó refusal path, review path, audit path và operational path đều có thể quan sát và kiểm thử.

## 5. Cập Nhật Benchmark Và Evaluation

### 5.1 Dòng Thời Gian Benchmark

Bằng chứng benchmark cần được đọc thành ba checkpoint riêng biệt:

| Run | Records | Providers | Trạng thái hoàn thành | Kết quả chính | Diễn giải |
| --- | ---: | --- | --- | --- | --- |
| Historical optimized 50-record baseline | 50 | Deterministic, BART, Pegasus XSum, Pegasus PubMed, Pegasus CNN/DailyMail | Mọi provider hoàn thành 50/50; có tính BERTScore | Retrieval: Recall@5 `0.9512`, MRR `0.9600`, nDCG@5 `0.8919`. Deterministic citation coverage `0.9237`; BERTScore F1 cao nhất `0.8276` thuộc Pegasus XSum. | Xác lập rằng retrieval-grounded pipeline đã tối ưu có thể hoàn thành medium run và tạo metric có thể tái lập. Run này chưa so sánh Qwen/Llama hoặc áp dụng stricter gate cuối. |
| Week 3 Flow 2.1 provider-selection run | 20 | BART, Pegasus CNN/DailyMail, Qwen2.5, Llama3.2 | Mọi provider hoàn thành 20/20; có tính BERTScore | Qwen2.5 dẫn đầu ROUGE-L (`0.2607`), BERTScore F1 (`0.8583`) và citation coverage (`0.8747`). Llama3.2 dẫn đầu faithfulness (`0.8817`) và có critical omission thấp nhất (`0.4375`). | Cung cấp bằng chứng Week 3 rằng instruction-following provider phù hợp hơn BART/Pegasus cho evidence-first synthesis trong thiết lập proxy này. |
| Current stricter 50-record gated run, 17/06/2026 | 50 | Deterministic, BART, Pegasus CNN/DailyMail, Qwen2.5, Llama3.2 | Mỗi provider đánh giá đủ 50/50: 48 generated, 2 blocked bởi retrieval quality gate; không yêu cầu BERTScore | Retrieval: Recall@5 `0.9465`, MRR `0.9900`, nDCG@5 `0.9083`. Citation coverage: Qwen `0.8931`; deterministic `0.9135`; Llama `0.8501`. | Đánh giá execution rộng hơn cùng strict section isolation và refusal behavior nghiêm ngặt hơn. Hệ thống không ép generation cho record thiếu bằng chứng retrieval bắt buộc. |
| Pre-diversity 50-record no-gate run, 18/06/2026; bổ sung BERTScore 19/06/2026 | 50 | Deterministic, BART, Pegasus CNN/DailyMail, Qwen2.5, Llama3.2 | Mỗi provider completed 50/50; tổng cộng 250/250 prediction completed; BERTScore tính từ prediction đã lưu | Qwen2.5: ROUGE-L `0.2122`, BERTScore F1 `0.8391`, citation coverage `0.8884`, faithfulness `0.8713`. Deterministic citation coverage `0.9147`. | Xác minh generation đủ 50 record trước data diversity khi benchmark blocking được tắt. BERTScore dùng `roberta-large`; run này không thay thế run gated và không thay đổi safety gate của doctor workflow. |

Hai run 50 record trả lời các câu hỏi khác nhau và phải được giữ tách biệt. Run 20 record ở Week 3 cũng không được gộp trực tiếp với bất kỳ run 50 record nào.

### 5.2 Kết Quả Retrieval

| Retrieval metric | Historical optimized 50-record baseline | Week 3 Flow 2.1, 20 record | Stricter gated 50-record run | Pre-diversity no-gate 50-record run |
| --- | ---: | ---: | ---: | ---: |
| Trung bình chunk mỗi record | `4.12` | `3.55` | `4.12` | `4.12` |
| Trung bình retrieved chunk | `4.96` | `3.15` | `3.78` | `3.78` |
| Trung bình context token | `753.70` | `733.15` | `1,594.66` | `1,594.66` |
| Recall@5 proxy | `0.9512` | `0.9275` | `0.9465` | `0.9465` |
| MRR proxy | `0.9600` | `0.9750` | `0.9900` | `0.9900` |
| nDCG@5 proxy | `0.8919` | `0.8533` | `0.9083` | `0.9083` |

Run hiện tại retrieve ít chunk hơn historical optimized baseline nhưng đóng gói số context token lớn hơn đáng kể. MRR và nDCG@5 proxy cao hơn, trong khi Recall@5 thấp hơn một chút. Kết quả gợi ý cấu hình retrieval hiện tại xếp hạng bằng chứng liên quan tốt và đóng gói context nhận biết từng section phong phú hơn. Tuy nhiên, các metric sử dụng proxy label suy ra từ độ trùng token với reference summary, nên phù hợp cho regression analysis chứ không phải tuyên bố về độ liên quan lâm sàng.

Run nghiêm ngặt cũng thay đổi ý nghĩa của “thành công”. Một record có thể nằm trong một run có aggregate retrieval metric tốt nhưng vẫn thiếu section diagnosis hoặc timeline bắt buộc. Quality gate vì vậy đánh giá bằng chứng bắt buộc ở cấp record, thay vì chỉ dựa vào aggregate retrieval average thuận lợi.

### 5.3 Diễn Giải Theo Provider

Benchmark hỗ trợ năm kết luận thực tiễn:

1. **Qwen2.5 là ứng viên generative PoC mạnh nhất hiện tại.** Trong run 50/50 mới nhất, Qwen2.5 dẫn đầu về ROUGE-L (`0.2122`), BERTScore F1 (`0.8391`), citation coverage (`0.8884`) và faithfulness proxy (`0.8713`). Unsupported-claim rate vẫn khác không (`0.0346`), vì vậy citation validation và clinician review vẫn bắt buộc.
2. **Llama3.2 vẫn có năng lực nhưng bộc lộ trade-off rõ hơn trong run lớn.** BERTScore F1 đạt `0.8149` và citation coverage đạt `0.8620`, nhưng hallucinated-entity proxy (`1.3000`) và p95 latency (`65,747.15 ms`) cao hơn Qwen.
3. **BART không phù hợp tốt với strict evidence-first prompt.** Dù BERTScore F1 đạt `0.8010`, BART chỉ có citation coverage `0.1307`, timeline completeness `0.0645` và critical omission `0.9583`.
4. **Pegasus có semantic similarity tương đối tốt nhưng grounding vẫn yếu.** BERTScore F1 đạt `0.8232`, trong khi citation coverage chỉ `0.3800` và critical omission là `0.9236`. Điều này minh họa rằng BERTScore không thay thế citation và clinical proxy metrics.
5. **Deterministic là control quan trọng, không phải model chiến thắng.** Provider này xác minh retrieval, evidence packing, citation, latency và deployment behavior với độ biến thiên generation tối thiểu. Grounding proxy cao là kết quả được kỳ vọng từ extractive output bị ràng buộc theo bằng chứng.

### 5.4 Diễn Giải Failure Pattern

Artifact hiện tại hiển thị failure count thay vì che chúng sau các giá trị trung bình:

| Provider | Tín hiệu failure đáng chú ý trong run hiện tại |
| --- | --- |
| Deterministic | 16 retrieval-related failure, 12 missing-diagnosis label, 8 missing-timeline label; 30 record không phát hiện major proxy failure |
| BART | 36 retrieval-related failure, 28 missing-timeline label, 21 missing-diagnosis label, 26 source-data-limitation label |
| Pegasus | 30 retrieval-related failure, 26 missing-timeline label, 21 missing-diagnosis label, 19 incomplete-summary label |
| Qwen2.5 | 22 hallucinated-content label, 14 retrieval-related failure, 12 missing-timeline label, 10 missing-diagnosis label; 13 record không phát hiện major proxy failure |
| Llama3.2 | 41 hallucinated-content label, 15 missing-timeline label, 14 retrieval-related failure, 14 missing-diagnosis label |

Các failure label này là tín hiệu proxy tự động và có thể chồng lấp trong cùng một record. Không được diễn giải chúng như lỗi lâm sàng đã được chuyên gia adjudicate. Giá trị của chúng nằm ở việc cho thấy vì sao một metric trung bình đơn lẻ là chưa đủ:

- retrieval failure có thể giới hạn mọi downstream provider;
- ROUGE hoặc BERTScore cao không bảo đảm citation coverage;
- unsupported-claim rate thấp vẫn có thể đi cùng omission;
- một model có thể giữ timeline tốt nhưng đồng thời tạo tín hiệu entity-level hallucination;
- từ chối ở retrieval gate tốt hơn việc tạo một bản nháp không đủ bằng chứng.

### 5.5 Diễn Giải Từ Week 3 Đến Week 4

So sánh có cơ sở nhất nằm ở cấp kiến trúc:

- Week 3 trả lời: “Provider nào cho thấy tiềm năng evidence-first tốt nhất?”
- Week 4 trả lời: “Kiến trúc đã chọn có thể chạy trên tập yêu cầu rộng hơn, từ chối khi thiếu bằng chứng, hiển thị failure và kết nối kết quả vào một ứng dụng end-to-end có review hay không?”

Câu trả lời cho câu hỏi thứ nhất nghiêng về Qwen2.5 và Llama3.2 so với BART/Pegasus. Câu trả lời cho câu hỏi thứ hai là có ở cấp PoC: run nghiêm ngặt xử lý tập yêu cầu 50 record trên năm provider, chặn nhất quán hai record, giữ đầy đủ artifact chi tiết và đưa cùng các khái niệm quản trị bằng chứng vào doctor-facing workflow.

Mọi metric trong báo cáo được lấy trực tiếp từ artifact report, CSV và manifest tương ứng. Không có metric nào được tự tạo hoặc gộp giữa các run.

## 6. Bằng Chứng Xác Minh

| Hạng mục xác minh | Kết quả |
| --- | --- |
| Đồng bộ repository | `main` và `origin/main` cùng ở `75c89fdc596692b692fdaaf311efe40a06c96b30` |
| Toàn bộ backend suite | 165 pass, 0 fail |
| Bộ test tập trung vào deployment | 19 pass |
| Docker build | Pass |
| Docker Compose staging | Pass sau khi dọn stale Docker network/container state trên host |
| PostgreSQL | Healthy |
| Redis | Đang chạy |
| Web service | Healthy |
| Worker | Đang chạy và có một worker đăng ký |
| `/health` | HTTP 200 |
| `/ready` | HTTP 200 với readiness có cấu trúc |
| Readiness check | Database pass; Redis/RQ pass; deterministic provider có thể chọn; không bắt buộc Ollama/HF provider; chỉ có staging warning dự kiến |
| Runtime image | Xấp xỉ 122 MB |
| Module ML nặng | Không có trong Compose runtime image |
| CI/CD | Backend smoke, migration, secret scan, frontend build và Docker build đã cấu hình và pass |

Lần chạy Compose ban đầu fail do stale Docker network/container state ở phía host. Compose cleanup đã xử lý vấn đề; không cần thay đổi kiến trúc ứng dụng.

## 7. Trạng Thái Deployment

Repository hiện có kiến trúc Railway-ready cho PoC staging chỉ dùng dữ liệu đã khử định danh và bắt buộc clinician review. Topology Railway dự kiến:

```text
Web service
  + Worker service
  + PostgreSQL
  + Redis
```

Việc triển khai Railway công khai được hoãn vì không có hosting credit. Cùng topology và giả định runtime đã được xác minh cục bộ thông qua Docker Compose staging, gồm database migration, web health, kết nối Redis/RQ, worker registration và provider readiness.

Đây là giới hạn vận hành về hosting, không phải blocker kiến trúc. Mô tả chính xác về trạng thái bàn giao là:

> Kiến trúc Railway-ready và đã được xác minh cục bộ thông qua Docker Compose staging.

Hệ thống chưa được đưa lên Railway công khai.

## 8. Ranh Giới Diễn Giải

Benchmark Flow 2.1 đã hoàn tất trên 50/50 record cho cả năm provider, tương ứng 250/250 prediction, đồng thời đã bổ sung BERTScore cho toàn bộ kết quả. Vì vậy, báo cáo không còn xem số lượng record, trạng thái hoàn thành provider hoặc BERTScore là hạn chế còn tồn tại.

Các ranh giới cần giữ để diễn giải kết quả chính xác:

- kết quả là proxy evaluation trên dữ liệu open/de-identified, không phải thẩm định trên EHR bệnh viện;
- summary do AI tạo ra vẫn là bản nháp bắt buộc clinician review;
- public Railway deployment là bước tùy chọn khi có hosting credit, vì Docker Compose staging cục bộ đã được xác minh;
- báo cáo không đưa ra tuyên bố về độ an toàn, hiệu quả lâm sàng, quyết định lâm sàng tự động hoặc writeback vào EMR thực.

## 9. Đề Xuất Bước Tiếp Theo Cho Week 5

Week 5 nên ưu tiên chất lượng trình diễn, đóng gói bằng chứng và khả năng lặp lại thay vì bổ sung feature lớn:

1. Giữ Docker Compose cục bộ làm staging path hiện đã được xác minh cho demo cuối.
2. Hoàn thiện evidence package gồm readiness output, provider status, ví dụ generation bị gate kiểm soát, ảnh Review & Evidence, audit export và bảng benchmark.
3. Ghi hình demo end-to-end trên môi trường Docker Compose staging cục bộ.
4. Chạy lại deterministic smoke theo checklist trước khi ghi hình để xác nhận tính lặp lại của demo.
5. Đóng gói kết quả benchmark đã hoàn tất, giữ tách biệt historical optimized baseline, Week 3 provider-selection run, stricter gated run và run 50/50 có BERTScore.
6. Tùy chọn triển khai Railway hoặc Render công khai khi có hosting credit/tài nguyên; đây không phải điều kiện bắt buộc để hoàn tất demo hiện tại.
7. Nếu có public staging, chạy deterministic smoke trước; chỉ chạy Gemini smoke khi có key, external use đã được phê duyệt và dữ liệu demo đã khử định danh.
8. Không bổ sung feature lớn trước buổi trình diễn cuối; tập trung vào repeatability, trình bày bằng chứng, disclosure rủi ro và operational cleanup.

## 10. Kết Luận

So với Week 3, Week 4 đã chuyển định hướng RAG, evidence gate, human review, background job và deployment readiness thành một bề mặt staging tích hợp và đã được xác minh. Thành quả quan trọng nhất không phải là một metric cao hơn hoặc một model mới, mà là sự kết hợp giữa scoped retrieval, evidence-gated generation, clinician review, hành động có thể audit, persisted job, dependency deployment gọn nhẹ và structured readiness.

Hệ thống hiện là một PoC staging chỉ dùng dữ liệu đã khử định danh, bắt buộc clinician review và sẵn sàng cho demo cục bộ; việc triển khai public cloud được hoãn vì lý do tài nguyên hosting. Kiến trúc đã Railway-ready và được xác minh cục bộ thông qua Docker Compose staging. Báo cáo không đưa ra tuyên bố về độ an toàn hoặc hiệu quả lâm sàng.
