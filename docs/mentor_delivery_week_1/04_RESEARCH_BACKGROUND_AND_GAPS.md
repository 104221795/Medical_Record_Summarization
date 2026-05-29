# 04 — Research Background and Research Gaps

**Loại tài liệu:** Phụ lục nghiên cứu
**Mục đích:** Cung cấp nền tảng học thuật cho PRD và User Flow

---

## 1. Động lực nghiên cứu

Hồ sơ bệnh án thường bao gồm cả dữ liệu có cấu trúc và dữ liệu phi cấu trúc. Dữ liệu có cấu trúc có thể bao gồm chẩn đoán, đơn thuốc, kết quả xét nghiệm và thông tin lượt khám/nhập viện. Trong khi đó, dữ liệu phi cấu trúc thường nằm trong các ghi chú lâm sàng như discharge notes, progress notes, radiology reports hoặc các narrative notes khác.

Trong thực tế lâm sàng, bác sĩ và nhân sự y tế thường phải tái dựng bối cảnh bệnh nhân từ nhiều nguồn thông tin khác nhau trong điều kiện thời gian hạn chế. Điều này tạo ra nhu cầu rõ ràng đối với các công cụ tóm tắt có khả năng giảm tải thông tin và hỗ trợ quá trình review hồ sơ bệnh án.

Tuy nhiên, medical summarization không phải là một bài toán text summarization thông thường. Trong bối cảnh y tế, một bản tóm tắt sai, thiếu bằng chứng hoặc gây hiểu nhầm có thể ảnh hưởng đến quá trình suy luận lâm sàng. Vì vậy, một hệ thống có giá trị không chỉ cần tạo ra summary dễ đọc, mà còn phải xử lý các vấn đề như evidence traceability, missing information, hallucination risk, human review và auditability.

Dự án này được xây dựng trên quan điểm rằng một hệ thống tóm tắt bệnh án đáng tin cậy cần kết hợp giữa năng lực sinh summary của mô hình AI và workflow kiểm soát an toàn trong môi trường lâm sàng. Nói cách khác, giá trị của hệ thống không chỉ nằm ở model output, mà còn nằm ở khả năng giúp người dùng kiểm chứng, chỉnh sửa, phê duyệt và truy vết quá trình sử dụng summary.

---

## 2. Các chủ đề chính trong literature review

### 2.1 Nhu cầu tóm tắt clinical text

Các nghiên cứu gần đây nhấn mạnh tình trạng quá tải thông tin trong hệ thống hồ sơ sức khỏe điện tử. Bác sĩ có thể phải đọc nhiều loại tài liệu khác nhau để nắm được bối cảnh bệnh nhân, từ chẩn đoán, kết quả xét nghiệm, thuốc đang sử dụng đến các ghi chú tiến triển và discharge summaries.

Trong bối cảnh đó, automatic clinical text summarization trở thành một hướng nghiên cứu quan trọng. Các dataset như MIMIC-IV-Note cung cấp discharge summaries và radiology reports đã được de-identified, trong khi MIMIC-IV-Ext-BHC được xây dựng riêng cho bài toán Brief Hospital Course summarization từ clinical notes.

Điều này cho thấy clinical summarization có giá trị thực tế rõ ràng, nhưng cũng đặt ra yêu cầu cao về chất lượng, tính chính xác và khả năng kiểm chứng của đầu ra.

### 2.2 Tiềm năng của LLMs và mô hình summarization

Large Language Models và các encoder-decoder models như BART/Pegasus đã cho thấy khả năng mạnh trong các tác vụ summarization. Các mô hình này có thể sinh ra văn bản mạch lạc, ngắn gọn và dễ đọc hơn so với phương pháp rule-based hoặc extractive summarization truyền thống.

Tuy nhiên, trong y tế, tiêu chí “summary đọc hay” là chưa đủ. Medical summarization yêu cầu mức độ factual reliability cao hơn general summarization, vì người dùng có thể là bác sĩ hoặc nhân sự y tế đang review thông tin bệnh nhân. Một summary sai, suy luận quá mức hoặc thiếu nguồn kiểm chứng có thể làm giảm niềm tin và tạo rủi ro trong workflow.

Vì vậy, việc sử dụng LLM trong medical record summarization cần đi kèm các cơ chế kiểm soát như citation, human review, audit log và safety evaluation.

### 2.3 Thách thức trong đánh giá

Automatic metrics như ROUGE và BERTScore có giá trị trong việc so sánh generated summary với reference summary. Tuy nhiên, các chỉ số này không đo đầy đủ factual correctness, missing information, hallucination risk hoặc usefulness trong clinical workflow.

Một summary có thể đạt điểm ROUGE tốt nhưng vẫn bỏ sót thông tin quan trọng hoặc đưa ra claim không được hỗ trợ bởi nguồn dữ liệu. Ngược lại, một summary có thể có phrasing khác reference nhưng vẫn đúng về mặt lâm sàng.

Do đó, đánh giá medical summarization cần kết hợp nhiều lớp:

* automatic metrics để so sánh mô hình;
* citation metrics để đánh giá khả năng truy xuất nguồn;
* safety metrics để phát hiện unsupported claims;
* human evaluation để đánh giá factual correctness, completeness, readability và citation usefulness.

### 2.4 Hallucination và unsupported claims

Một trong những rủi ro chính của LLM-generated medical summaries là hallucination. Trong bối cảnh này, hallucination không chỉ là việc sinh ra thông tin sai, mà còn bao gồm việc thêm thông tin không có nguồn, diễn giải quá mức, bỏ sót thông tin quan trọng hoặc tạo cảm giác chắc chắn khi dữ liệu không đủ.

Ví dụ, nếu hồ sơ không có thông tin dị ứng, hệ thống không được tự viết rằng bệnh nhân “không có dị ứng”. Nếu chỉ có một giá trị xét nghiệm, hệ thống không nên kết luận xu hướng tăng/giảm. Nếu diagnosis không xuất hiện trong nguồn dữ liệu, hệ thống không được tự thêm diagnosis vào summary.

Điều này cho thấy nhu cầu về claim-level verification, citation-based summary và safety panel. Hệ thống cần làm rõ claim nào được hỗ trợ, claim nào thiếu bằng chứng và claim nào cần bác sĩ kiểm tra thêm.

### 2.5 Integration và governance

Healthcare AI tools không thể chỉ dừng ở model output. Để có thể tiến gần hơn tới sản phẩm thực tế, hệ thống cần quan tâm đến workflow integration, role-based access, auditability, privacy control và governance.

Các chuẩn như FHIR và SMART on FHIR có ý nghĩa quan trọng đối với định hướng tích hợp trong tương lai, vì chúng hỗ trợ cách các ứng dụng healthcare truy cập dữ liệu EHR, launch trong bối cảnh bệnh nhân cụ thể và tương tác với hệ thống lâm sàng một cách có kiểm soát.

Đối với MVP hiện tại, dự án chưa hướng tới full production HIS/EMR integration, nhưng đã thiết kế theo hướng FHIR-compatible, có ingestion layer, role-based UI, audit logs và monitoring dashboard để phản ánh tư duy product hóa trong môi trường y tế.

---

## 3. Research Gaps

| Gap ID | Research Gap                              | Vì sao quan trọng                                         | Cách MVP xử lý                                               |
| ------ | ----------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------ |
| RG-01  | Thiếu claim-level evidence traceability   | Bác sĩ cần biết mỗi claim trong summary đến từ nguồn nào  | Citation-based summary với evidence panel                    |
| RG-02  | Phụ thuộc quá nhiều vào automatic metrics | ROUGE/BERTScore không đảm bảo factual safety              | Kết hợp human evaluation, safety metrics và citation metrics |
| RG-03  | Hallucination trong bối cảnh high-stakes  | Unsupported claims có thể làm người dùng hiểu sai         | Unsupported claim detection và safety panel                  |
| RG-04  | Thiếu workflow integration                | Model-only demos không thể hiện cách bác sĩ review output | Doctor UI và HITL review workflow                            |
| RG-05  | Auditability yếu                          | Clinical systems cần truy vết hành động và quyết định     | Audit logs cho generation, citation và review                |
| RG-06  | Role boundaries chưa rõ                   | Người dùng khác nhau cần quyền và workflow khác nhau      | Role-based UI và backend permission checks                   |
| RG-07  | Hạn chế truy cập real EHR notes           | Benchmark thật thường yêu cầu credentialed access         | Multi-layer evaluation và pending benchmark status           |
| RG-08  | Rủi ro privacy khi dùng external LLM      | Clinical data có thể không an toàn khi gửi ra bên ngoài   | Gemini disabled by default và de-identified/demo data policy |

---

## 4. Câu hỏi nghiên cứu

### RQ1 — Workflow usefulness

Làm thế nào một citation-grounded summary workflow có thể giảm effort khi review bối cảnh bệnh nhân nhưng vẫn duy trì clinician control?

### RQ2 — Evidence traceability

Claim-level citation có thể cải thiện niềm tin của người dùng và hỗ trợ review an toàn hơn đối với AI-generated medical summaries hay không?

### RQ3 — Safety và hallucination mitigation

Unsupported claim detection và safety panel có thể làm cho hallucination risk trở nên visible trước khi clinician approval diễn ra hay không?

### RQ4 — Model comparison

Các baseline models như BART/Pegasus so sánh như thế nào với một real LLM provider như Gemini trên các proxy medical summarization datasets hiện có?

### RQ5 — Evaluation design under data constraints

Một MVP medical summarization nên được đánh giá trung thực như thế nào khi real EHR note-level datasets yêu cầu credentialed access?

---

## 5. Đóng góp nghiên cứu đề xuất

Dự án này không chỉ đóng góp một model benchmark, mà đề xuất một **production-style MVP design** cho bài toán Medical Record Summarization.

Đóng góp chính của dự án nằm ở việc tích hợp các thành phần sau vào một workflow thống nhất:

```text id="uxooxs"
summarization model providers
+ citation grounding
+ hallucination mitigation
+ doctor-in-the-loop review
+ auditability
+ role-based UI
+ multi-layer evaluation
```

Thiết kế này giúp thu hẹp khoảng cách giữa clinical summarization research và practical clinical workflow prototyping. Thay vì chỉ đánh giá một mô hình tóm tắt văn bản, dự án đặt model output vào một môi trường sản phẩm có kiểm soát, nơi người dùng có thể kiểm tra nguồn, phát hiện rủi ro, chỉnh sửa, phê duyệt và truy vết lại hành động.

---

## 6. Chiến lược dataset

| Dataset                      | Vai trò                                     | Giới hạn                                           |
| ---------------------------- | ------------------------------------------- | -------------------------------------------------- |
| Mock/de-identified demo data | Functional validation                       | Không thể dùng để claim model quality              |
| MIMIC-III demo DB            | Structured EHR validation                   | Không có clinical note rows cho note summarization |
| OPI/D2N/CHQ                  | Proxy medical text summarization evaluation | Không phải full real EHR discharge-note benchmark  |
| MIMIC-IV-Ext-BHC             | Preferred real benchmark                    | Pending credentialed access                        |
| MIMIC-IV-Note                | Fallback real benchmark                     | Cần section extraction và quyền truy cập           |

Chiến lược này giúp dự án tránh đánh đồng các loại dữ liệu khác nhau. Mock data chỉ dùng để kiểm thử chức năng, MIMIC-III demo DB dùng để validate structured EHR workflow, các dataset OPI/D2N/CHQ dùng cho proxy evaluation, còn real EHR note-level benchmark sẽ được thực hiện khi có quyền truy cập MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.

---

## 7. Liên kết với survey research plan

Survey được thiết kế để kiểm chứng ba giả định chính:

1. Hồ sơ dài và phân tán tạo gánh nặng khi review.
2. Người dùng cần citation để tin tưởng AI-generated summaries.
3. Người dùng muốn có doctor approval trước khi generated summaries trở thành official hoặc được sử dụng trong workflow.

Kết quả survey sẽ hỗ trợ:

* tinh chỉnh personas;
* ưu tiên tính năng;
* xác định trust requirements trong UI;
* kiểm tra mức độ phù hợp của citation-first và doctor-in-the-loop workflow.

Survey không được xem là clinical validation, mà là bước problem validation và workflow validation ở giai đoạn đầu của MVP.

---

## 8. Giới hạn nghiên cứu

Dự án hiện có một số giới hạn quan trọng:

* MVP không thực hiện clinical diagnosis hoặc treatment recommendation.
* Functional validation bằng mock data không thể chứng minh clinical model performance.
* BART/Pegasus proxy evaluation không thể thay thế real EHR note-level benchmark.
* Human evaluation có thể bị giới hạn bởi chuyên môn của evaluator và kích thước mẫu.
* Gemini evaluation trên restricted clinical data cần data governance cẩn trọng.
* MIMIC-III demo DB hữu ích cho structured EHR workflow nhưng không đủ cho note-level summarization benchmark.
* Real EHR benchmark vẫn phụ thuộc vào credentialed access đối với MIMIC-IV-Ext-BHC hoặc MIMIC-IV-Note.

---

## 9. Hướng nghiên cứu tương lai

Các hướng nghiên cứu và phát triển tiếp theo bao gồm:

1. Chạy real EHR note-level benchmark bằng MIMIC-IV-Ext-BHC.
2. Thực hiện clinician-led human evaluation.
3. Cải thiện factuality và citation verification methods.
4. So sánh local LLMs và external LLM APIs trong điều kiện privacy constraints.
5. Nghiên cứu ảnh hưởng của citation UI tới trust và review efficiency.
6. Đánh giá doctor edit distance như một product quality signal.
7. Mở rộng conflict detection cho medication, allergy, lab trend và diagnosis.
8. Tích hợp FHIR/SMART on FHIR trong sandbox hoặc hospital pilot environment.
9. Xây dựng regression test suite cho prompt/model updates.

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
