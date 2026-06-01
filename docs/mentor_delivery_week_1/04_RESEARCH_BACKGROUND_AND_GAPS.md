# 04 — Research Background and Research Gaps

**Loại tài liệu:** Phụ lục nghiên cứu
**Mục đích:** Cung cấp nền tảng học thuật và lập luận nghiên cứu cho PRD, User Flow và Evaluation Plan
**Phiên bản:** v1.1

---

## 1. Động lực nghiên cứu

Hồ sơ bệnh án thường bao gồm cả dữ liệu có cấu trúc và dữ liệu phi cấu trúc. Dữ liệu có cấu trúc có thể bao gồm chẩn đoán, đơn thuốc, kết quả xét nghiệm, thông tin lượt khám/nhập viện và các mã hóa lâm sàng. Trong khi đó, dữ liệu phi cấu trúc thường nằm trong discharge notes, progress notes, radiology reports, consultation notes hoặc các narrative notes khác.

Trong thực tế lâm sàng, bác sĩ và nhân sự y tế thường phải tái dựng bối cảnh bệnh nhân từ nhiều nguồn thông tin khác nhau trong điều kiện thời gian hạn chế. Điều này tạo ra nhu cầu rõ ràng đối với các công cụ có khả năng tóm tắt và tổ chức lại thông tin để giảm cognitive load trong quá trình review hồ sơ.

Tuy nhiên, **medical summarization không phải là một bài toán text summarization thông thường**. Trong bối cảnh y tế, một bản tóm tắt sai, thiếu bằng chứng, diễn giải quá mức hoặc trình bày thông tin không chắc chắn như sự thật có thể ảnh hưởng đến quá trình suy luận lâm sàng. Vì vậy, một hệ thống tóm tắt bệnh án có giá trị không chỉ cần tạo ra summary dễ đọc, mà còn phải hỗ trợ:

```text
evidence traceability
missing-information visibility
hallucination risk control
human review
auditability
role-based accountability
evaluation boundary
```

Dự án này được xây dựng trên quan điểm rằng một hệ thống tóm tắt bệnh án đáng tin cậy cần kết hợp giữa năng lực sinh summary của mô hình AI và workflow kiểm soát an toàn trong môi trường lâm sàng. Nói cách khác, giá trị của hệ thống không chỉ nằm ở model output, mà còn nằm ở khả năng giúp người dùng kiểm chứng, chỉnh sửa, phê duyệt và truy vết quá trình sử dụng summary.

Luận điểm nghiên cứu trung tâm của dự án là:

> Medical summarization is not only a generation problem. In clinical settings, it is a trust, grounding, workflow, and evaluation problem.

---

## 2. Vì sao medical summarization khó hơn general summarization?

Trong general summarization, một summary tốt thường được đánh giá theo độ ngắn gọn, mạch lạc và mức độ bao phủ ý chính. Trong medical summarization, các tiêu chí đó vẫn cần thiết nhưng chưa đủ. Một summary bệnh án cần xử lý thêm các yêu cầu sau:

| Yêu cầu                         | Vì sao quan trọng                                                             |
| ------------------------------- | ----------------------------------------------------------------------------- |
| Factual correctness             | Một claim sai có thể làm người dùng hiểu nhầm bối cảnh bệnh nhân              |
| Source grounding                | Bác sĩ cần biết claim đến từ nguồn nào trước khi tin hoặc dùng                |
| Missing-information awareness   | Không có dữ liệu không đồng nghĩa với “không có bệnh/tình trạng”              |
| Clinical uncertainty visibility | Hệ thống không nên che giấu sự không chắc chắn bằng văn phong tự tin          |
| Human review                    | AI output cần được bác sĩ kiểm tra trước khi trở thành approved documentation |
| Auditability                    | Clinical workflow cần truy vết ai tạo, sửa, xem citation, approve hoặc reject |
| Data governance                 | Dữ liệu y tế có yêu cầu privacy và governance nghiêm ngặt                     |

Vì vậy, một hệ thống chỉ có flow:

```text
clinical note → model summary → automatic metric
```

là chưa đủ để mô tả một sản phẩm clinical AI đáng tin cậy. Dự án này mở rộng bài toán thành:

```text
clinical source data
→ source-aware ingestion
→ section/chunk representation
→ draft summary generation
→ claim-level citation
→ unsupported claim flag
→ doctor review
→ audit log
→ multi-layer evaluation
```

---

## 3. Các chủ đề chính trong literature review

### 3.1 Nhu cầu tóm tắt clinical text

Các nghiên cứu gần đây nhấn mạnh tình trạng quá tải thông tin trong hệ thống hồ sơ sức khỏe điện tử. Bác sĩ có thể phải đọc nhiều loại tài liệu khác nhau để nắm được bối cảnh bệnh nhân, từ chẩn đoán, kết quả xét nghiệm, thuốc đang sử dụng đến các ghi chú tiến triển và discharge summaries.

Automatic clinical text summarization trở thành một hướng nghiên cứu quan trọng vì nó có thể giúp giảm thời gian đọc, hỗ trợ review nhanh và cải thiện khả năng định hướng thông tin. Tuy nhiên, clinical summarization chỉ có ý nghĩa thực tế nếu output có thể được kiểm chứng và được đặt trong workflow review phù hợp.

Các dataset như MIMIC-IV-Note và MIMIC-IV-Ext-BHC cho thấy bài toán note-level summarization có giá trị nghiên cứu rõ ràng, đặc biệt trong discharge summaries và Brief Hospital Course summarization. Tuy nhiên, các dataset này thường yêu cầu credentialed access, khiến một MVP cần tách rõ giữa functional validation, open benchmark evaluation và future real EHR benchmark.

---

### 3.2 Tiềm năng và giới hạn của LLMs / summarization models

Large Language Models và các encoder-decoder models như BART/Pegasus có khả năng tạo summary mạch lạc, ngắn gọn và dễ đọc. Chúng hữu ích cho việc xây dựng baseline trong các task summarization có reference summary.

Tuy nhiên, trong y tế, tiêu chí “đọc hay” là chưa đủ. Một summary có thể rất mượt nhưng vẫn sai, thiếu nguồn, bỏ sót thông tin quan trọng hoặc thêm claim không có trong record. Đây là lý do hệ thống không thể chỉ dựa vào generation model. Cần có thêm:

```text
citation grounding
claim verification
safety panel
human-in-the-loop review
audit log
evaluation boundary
```

Trong dự án này:

| Model / tool             | Vai trò                                                                     |
| ------------------------ | --------------------------------------------------------------------------- |
| BART/Pegasus             | Summarization generation baselines cho Layer C benchmark                    |
| BERT/BERTScore           | Semantic evaluation hoặc claim-source similarity support                    |
| Gemini                   | Product LLM provider hoặc controlled difficult-case normalization assistant |
| Deterministic summarizer | Stable baseline để test workflow                                            |
| Human reviewer           | Review usefulness, factuality, citation usefulness và safety perception     |

BERT không được định vị là model chính để sinh summary. Vai trò hợp lý của BERT/BioBERT/BERTScore là semantic evaluation, similarity scoring hoặc evidence matching support.

---

### 3.3 Thách thức trong đánh giá

Automatic metrics như ROUGE và BERTScore có giá trị trong việc so sánh generated summary với reference summary. Tuy nhiên, chúng không đo đầy đủ factual correctness, missing information, hallucination risk hoặc usefulness trong clinical workflow.

Một summary có thể đạt ROUGE tốt nhưng vẫn bỏ sót thông tin quan trọng. Ngược lại, một summary có thể dùng phrasing khác reference nhưng vẫn đúng về mặt ngữ nghĩa. BERTScore giúp cải thiện đánh giá semantic similarity, nhưng cũng không phải bằng chứng đầy đủ về clinical correctness.

Do đó, đánh giá medical summarization cần nhiều lớp:

```text
functional validation
structured EHR validation
open clinical summarization benchmark
normalization stress test
future real EHR note-level benchmark
human evaluation
```

Mỗi lớp trả lời một câu hỏi khác nhau. Mock data chứng minh workflow chạy được, nhưng không chứng minh model tốt. MultiClinSum hỗ trợ open benchmark evaluation, nhưng không phải real EHR benchmark. Human evaluation giúp đánh giá usefulness và reviewability, nhưng không thay thế clinical validation quy mô lớn.

---

### 3.4 Hallucination và unsupported claims

Một rủi ro chính của LLM-generated medical summaries là hallucination. Trong bối cảnh này, hallucination không chỉ là việc bịa ra thông tin sai. Nó còn bao gồm:

```text
fabricated fact
unsupported claim
false negative
over-interpretation
wrong timeline
wrong-patient evidence
unsupported causal inference
missing uncertainty
```

Ví dụ:

* Nếu hồ sơ không có thông tin dị ứng, hệ thống không được tự viết “bệnh nhân không có dị ứng”.
* Nếu chỉ có một giá trị xét nghiệm, hệ thống không được kết luận xu hướng tăng/giảm.
* Nếu diagnosis không xuất hiện trong nguồn dữ liệu, hệ thống không được tự thêm diagnosis.
* Nếu source evidence thuộc bệnh nhân khác, citation phải bị chặn.

Điều này cho thấy nhu cầu về claim-level verification, citation-based summary và safety panel. Hệ thống cần làm rõ claim nào được hỗ trợ, claim nào thiếu bằng chứng và claim nào cần bác sĩ kiểm tra thêm.

---

### 3.5 Workflow integration và governance

Healthcare AI tools không thể chỉ dừng ở model output. Để tiến gần hơn tới sản phẩm thực tế, hệ thống cần quan tâm đến workflow integration, role-based access, auditability, privacy control và governance.

Các chuẩn như FHIR và SMART on FHIR có ý nghĩa quan trọng đối với hướng tích hợp trong tương lai, vì chúng hỗ trợ cách các ứng dụng healthcare truy cập dữ liệu EHR, launch trong bối cảnh bệnh nhân cụ thể và tương tác với hệ thống lâm sàng một cách có kiểm soát.

Đối với MVP hiện tại, dự án chưa hướng tới full production HIS/EMR integration, nhưng đã thiết kế theo hướng FHIR-compatible, có ingestion layer, role-based UI, audit logs và monitoring dashboard để phản ánh tư duy product hóa trong môi trường y tế.

---

## 4. Research Gap Framework

Medical summarization trong dự án này được phân tích qua bốn nhóm gap chính.

### Gap 1 — Generation Gap

Câu hỏi: Hệ thống có thể tạo summary ngắn gọn, dễ đọc và đúng trọng tâm không?

Các mô hình như BART/Pegasus/Gemini có thể hỗ trợ generation, nhưng generation quality không thể được hiểu tách rời khỏi factuality và source grounding.

### Gap 2 — Grounding Gap

Câu hỏi: Các claim quan trọng trong summary có thể truy ngược về nguồn bằng chứng không?

Đây là gap quan trọng trong clinical AI. Nếu bác sĩ không biết một claim đến từ đâu, summary có thể làm tăng cognitive risk. Citation grounding biến summary từ “model output” thành “reviewable draft”.

### Gap 3 — Workflow Gap

Câu hỏi: AI output có được đưa vào workflow review, edit, approve/reject và audit không?

Nhiều prototype chỉ dừng ở notebook hoặc model output. MVP này đặt summary vào Doctor Workspace, Safety Panel, HITL Review và Audit Log để phản ánh cách một sản phẩm clinical documentation thực tế cần vận hành.

### Gap 4 — Evaluation Gap

Câu hỏi: Dự án có phân biệt được các loại bằng chứng đánh giá khác nhau không?

Một lỗi phổ biến trong medical AI prototype là dùng mock data hoặc open dataset để overclaim clinical performance. Dự án này tách rõ:

```text
mock data = workflow validation
MIMIC-III demo = structured EHR mapping
MultiClinSum = open clinical summarization benchmark
MTS-Dialog = auxiliary dialogue-to-note evaluation
mtsamples_clean = normalization stress test
MIMIC-IV-Ext-BHC / MIMIC-IV-Note = future real EHR note-level benchmark
human evaluation = review usefulness and safety perception
```

---

## 5. Research Gaps Addressed

| Gap ID | Research Gap                              | Vì sao quan trọng                                               | Cách MVP xử lý                                                  |
| ------ | ----------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- |
| RG-01  | Generation without verification           | Summary đọc mượt vẫn có thể thiếu bằng chứng hoặc gây hiểu nhầm | Citation-grounded claim workflow                                |
| RG-02  | Metrics without clinical grounding        | ROUGE/BERTScore không đảm bảo factual safety                    | Kết hợp human evaluation, safety metrics và citation metrics    |
| RG-03  | Hallucination without visible uncertainty | Unsupported claims có thể bị người dùng tin nhầm                | Unsupported claim detection và Safety Panel                     |
| RG-04  | Weak workflow integration                 | Model-only demos không thể hiện cách bác sĩ review output       | Doctor UI và HITL review workflow                               |
| RG-05  | Weak auditability                         | Clinical systems cần truy vết hành động và quyết định           | Audit logs cho generation, citation view, edit, approve, reject |
| RG-06  | Unclear role boundaries                   | Người dùng khác nhau có trách nhiệm khác nhau                   | Role-based UI và backend permission checks                      |
| RG-07  | Restricted real EHR data access           | Real benchmark thường yêu cầu credentialed access               | Multi-layer evaluation và future benchmark status               |
| RG-08  | External LLM privacy risk                 | Clinical data không thể gửi ra ngoài nếu thiếu governance       | Gemini disabled by default và de-identified/demo data policy    |
| RG-09  | Benchmark overclaim risk                  | Open benchmark không chứng minh real EHR performance            | Evidence ladder và allowed-claim boundaries                     |
| RG-10  | Messy input normalization                 | Clinical files có thể không chuẩn format/heading                | Rule-based chunking + planned difficult-case LLM normalization  |

---

## 6. Câu hỏi nghiên cứu

### RQ1 — Workflow usefulness

Làm thế nào một citation-grounded summary workflow có thể giảm effort khi review bối cảnh bệnh nhân nhưng vẫn duy trì clinician control?

### RQ2 — Evidence traceability

Claim-level citation có thể cải thiện niềm tin của người dùng và hỗ trợ review an toàn hơn đối với AI-generated medical summaries hay không?

### RQ3 — Safety và hallucination mitigation

Unsupported claim detection và safety panel có thể làm cho hallucination risk trở nên visible trước khi clinician approval diễn ra hay không?

### RQ4 — Model comparison

Các baseline models như BART/Pegasus so sánh như thế nào trên open clinical summarization benchmark như MultiClinSum?

### RQ5 — Evaluation design under data constraints

Một MVP medical summarization nên được đánh giá trung thực như thế nào khi real EHR note-level datasets yêu cầu credentialed access?

### RQ6 — Input normalization

LLM-assisted input normalization có thể cải thiện section detection và chunking trong các clinical documents messy mà không làm mất raw source traceability hay không?

---

## 7. Đóng góp nghiên cứu đề xuất

Dự án này không chỉ đóng góp một model benchmark, mà đề xuất một **production-style MVP design** cho bài toán Medical Record Summarization.

Đóng góp chính của dự án nằm ở việc tích hợp các thành phần sau vào một workflow thống nhất:

```text
summarization model providers
+ citation grounding
+ hallucination mitigation
+ doctor-in-the-loop review
+ auditability
+ role-based UI
+ multi-layer evaluation
```

Thiết kế này giúp thu hẹp khoảng cách giữa clinical summarization research và practical clinical workflow prototyping. Thay vì chỉ đánh giá một mô hình tóm tắt văn bản, dự án đặt model output vào một môi trường sản phẩm có kiểm soát, nơi người dùng có thể kiểm tra nguồn, phát hiện rủi ro, chỉnh sửa, phê duyệt và truy vết lại hành động.

Nói cách khác, contribution của dự án là một **trustworthy clinical summarization workflow**, không chỉ là một model pipeline.

---

## 8. Chiến lược dataset

| Dataset                      | Vai trò                                       | Có thể dùng để claim                                          | Không thể dùng để claim                                               |
| ---------------------------- | --------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------- |
| Mock/de-identified demo data | Functional validation                         | Workflow chạy được                                            | Model quality hoặc clinical performance                               |
| MIMIC-III demo DB            | Structured EHR validation                     | Structured patient/admission/lab/diagnosis/medication mapping | Note-level summarization quality                                      |
| MultiClinSum                 | Primary open clinical summarization benchmark | Pegasus/BART benchmark trên source/reference pairs            | Real hospital EHR note performance                                    |
| MTS-Dialog                   | Auxiliary dialogue-to-note proxy              | Dialogue-to-note section behavior                             | Full medical record summarization                                     |
| ACI-BENCH                    | Optional full-visit dialogue-to-note proxy    | Visit dialogue-to-note behavior                               | Real EHR discharge-note benchmark                                     |
| BIOMEDNLP/mtsamples_clean    | Normalization stress test                     | Messy input handling, section detection, chunking robustness  | Main supervised summarization benchmark nếu thiếu reference summaries |
| MIMIC-IV-Ext-BHC             | Future real benchmark                         | Real EHR note-level hospital course summarization             | Current Week 1 performance                                            |
| MIMIC-IV-Note                | Future/fallback real note dataset             | Real clinical note analysis nếu có quyền truy cập             | Current Week 1 performance                                            |

Chiến lược này giúp dự án tránh đánh đồng các loại dữ liệu khác nhau. Mock data chỉ dùng để kiểm thử chức năng. MIMIC-III demo DB dùng để validate structured EHR workflow. MultiClinSum dùng làm open benchmark chính cho Pegasus/BART evaluation. MTS-Dialog là dataset phụ cho dialogue-to-note. mtsamples_clean dùng riêng cho messy input normalization. Real EHR note-level benchmark sẽ được thực hiện khi có quyền truy cập MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.

---

## 9. Liên kết với Survey Research Plan

Survey được thiết kế để kiểm chứng các giả định product discovery và workflow validation, không phải clinical validation.

Các giả định chính:

1. Hồ sơ dài và phân tán tạo gánh nặng khi review.
2. Người dùng cần citation để tin tưởng AI-generated summaries.
3. Người dùng muốn AI-generated summaries giữ trạng thái draft cho đến khi có doctor approval.
4. Safety warnings như unsupported claim, weak citation hoặc missing information có thể tăng trust.
5. Role-based access là cần thiết trong clinical documentation workflow.

Survey hỗ trợ:

* tinh chỉnh personas;
* ưu tiên tính năng;
* xác định trust requirements trong UI;
* kiểm tra mức độ phù hợp của citation-first và doctor-in-the-loop workflow.

Survey không chứng minh:

* clinical accuracy;
* model performance;
* real EHR benchmark performance;
* medical safety.

---

## 10. Giới hạn nghiên cứu

Dự án hiện có một số giới hạn quan trọng:

* MVP không thực hiện clinical diagnosis hoặc treatment recommendation.
* Functional validation bằng mock data không thể chứng minh clinical model performance.
* MultiClinSum là open clinical summarization benchmark, không phải real EHR benchmark.
* MTS-Dialog là auxiliary proxy dataset, không phải full medical record summarization benchmark.
* mtsamples_clean là normalization stress test, không phải main supervised summarization benchmark nếu thiếu reference summaries.
* BART/Pegasus proxy evaluation không thể thay thế real EHR note-level benchmark.
* Human evaluation có thể bị giới hạn bởi chuyên môn của evaluator và kích thước mẫu.
* Gemini evaluation trên restricted clinical data cần data governance cẩn trọng.
* MIMIC-III demo DB hữu ích cho structured EHR workflow nhưng không đủ cho note-level summarization benchmark.
* Real EHR benchmark vẫn phụ thuộc vào credentialed access đối với MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.

---

## 11. Hướng nghiên cứu tương lai

Các hướng nghiên cứu và phát triển tiếp theo bao gồm:

1. Chạy Layer C.1 benchmark bằng MultiClinSum với Pegasus/BART và ROUGE/BERTScore.
2. Bổ sung MTS-Dialog như auxiliary dialogue-to-note evaluation.
3. Dùng BIOMEDNLP/mtsamples_clean để stress test messy input normalization.
4. Chạy real EHR note-level benchmark bằng MIMIC-IV-Ext-BHC khi có quyền truy cập.
5. Thực hiện clinician-led human evaluation.
6. Cải thiện factuality và citation verification methods.
7. So sánh local LLMs và external LLM APIs trong điều kiện privacy constraints.
8. Nghiên cứu ảnh hưởng của citation UI tới trust và review efficiency.
9. Đánh giá doctor edit distance như một product quality signal.
10. Mở rộng conflict detection cho medication, allergy, lab trend và diagnosis.
11. Tích hợp FHIR/SMART on FHIR trong sandbox hoặc hospital pilot environment.
12. Xây dựng regression test suite cho prompt/model updates.

---

## References

* Aali, A. et al. (2025) *MIMIC-IV-Ext-BHC: Labeled Clinical Notes Dataset for Hospital Course Summarization*. PhysioNet. Available at: https://physionet.org/content/labelled-notes-hospital-course/
* Bednarczyk, L. et al. (2025) *Scientific Evidence for Clinical Text Summarization Using Large Language Models*. Journal of Medical Internet Research. Available at: https://www.jmir.org/2025/1/e68998/
* Croxford, E. et al. (2025) *Evaluating clinical AI summaries with large language models*. npj Digital Medicine. Available at: https://www.nature.com/articles/s41746-025-02005-2
* FDA (2026) *Clinical Decision Support Software: Guidance for Industry and Food and Drug Administration Staff*. Available at: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
* HL7 (2024) *SMART App Launch Implementation Guide*. Available at: https://build.fhir.org/ig/HL7/smart-app-launch/
* Johnson, A. et al. (2024) *MIMIC-IV-Note: Deidentified free-text clinical notes*. PhysioNet. Available at: https://physionet.org/content/mimic-iv-note/
* NIST (2024) *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. Available at: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
* Tang, L. et al. (2023) *Evaluating large language models on medical evidence summarization*. npj Digital Medicine. Available at: https://pmc.ncbi.nlm.nih.gov/articles/PMC10449915/
* WHO (2021) *Ethics and governance of artificial intelligence for health*. Available at: https://www.who.int/publications/i/item/9789240029200
