# Proposal triển khai nghiên cứu Medical Record Summarization tại Vinmec

> **Bản đề xuất nộp kèm Week 5 Delivery.**
>
> Tài liệu này là proposal nghiên cứu/pilot cho bài toán hiện tại:
> **citation-grounded medical record summarization**. Đây không phải xác nhận
> Vinmec đã phê duyệt, cung cấp dữ liệu, tích hợp HIS/EMR hoặc sử dụng hệ thống.
>
> **Ranh giới lâm sàng:** hệ thống chỉ tạo **AI-generated draft** để bác sĩ
> kiểm tra. Không chẩn đoán, không khuyến nghị điều trị, không tự ký hồ sơ,
> không tự ghi vào HIS/EMR và không thay thế quyết định của bác sĩ.
>
> **Ghi chú:** bản proposal chính theo style enterprise/slide-ready hiện nằm tại
> [`docs/proposal/MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md`](../proposal/MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md).
> File này được giữ như bản research detail/reference.

## 1. Executive summary

Dự án hiện tại không nên được trình bày như một chatbot tóm tắt bệnh án tổng
quát. Cách trình bày đúng và mạnh hơn là:

> Một PoC clinical NLP theo hướng evidence-first: hệ thống tạo bản nháp tóm tắt
> hồ sơ bệnh án có citation, giới hạn retrieval theo đúng patient/encounter, có
> gate khi thiếu bằng chứng bắt buộc, và luôn giữ bác sĩ là người review cuối.

Nếu đưa bài toán này vào Vinmec, bước tiếp theo hợp lý không phải là triển khai
rộng ngay, mà là một **research-first pilot** có governance:

```text
PoC local staging
→ governance/workflow discovery
→ retrospective de-identified study
→ controlled Raw vs Structured vs RAG vs Adaptive comparison
→ clinician human evaluation
→ silent/shadow mode
→ clinician-visible usability pilot
→ external validation
```

Khuyến nghị pilot đầu tiên là **clinician-facing discharge handoff draft** cho
**một khoa nội trú người lớn tại một site**. Đây là phạm vi đủ hẹp để kiểm soát
rủi ro nhưng đủ giàu dữ liệu để kiểm tra giá trị của RAG/evidence-first so với
raw summarization trên một note ngắn.

Thành công của pilot không nên đo bằng ROUGE cao nhất. Thành công nên được định
nghĩa bằng các câu hỏi thực tế hơn:

- bác sĩ có giảm thời gian tổng hợp/kiểm tra hồ sơ không;
- critical omission/commission có tăng không;
- citation có thật sự hỗ trợ claim không;
- hệ thống có phát hiện hoặc dừng khi thiếu evidence bắt buộc không;
- draft có làm bác sĩ hiểu nhầm là kết luận đã ký không;
- toàn bộ output có audit và tái tạo được không.

## 2. Vì sao Vinmec là bối cảnh đáng nghiên cứu?

Từ thông tin công khai, Vinmec là bối cảnh có tính thuyết phục để đề xuất
nghiên cứu, nhưng chưa thể suy luận rằng hệ thống đã sẵn sàng áp dụng thật.
Cần phân biệt ba lớp:

1. **Tín hiệu công khai:** Vinmec là hệ thống bệnh viện/phòng khám nhiều cơ sở,
   định vị theo academic healthcare, research, innovation và có chính sách bảo
   vệ dữ liệu cá nhân.
2. **Nhu cầu có thể suy luận:** hệ thống nhiều cơ sở, nhiều chuyên khoa và
   nhiều lần thăm khám thường tạo ra gánh nặng tổng hợp hồ sơ, chuyển khoa,
   chuyển viện, tái khám và discharge handoff.
3. **Điểm chưa được xác nhận:** không tìm thấy công bố công khai về một hệ
   thống LLM/RAG medical record summarization đang nằm trong workflow HIS/EMR
   Vinmec.

Vì vậy, proposal này không nói “Vinmec đã sẵn sàng dùng hệ thống”. Proposal này
nói:

> Vinmec là một bối cảnh hợp lý để thiết kế research pilot cho evidence-first
> summarization, miễn là mọi giả định về dữ liệu, HIS/EMR, workflow, quyền truy
> cập và đánh giá lâm sàng đều được xác minh qua discovery và governance.

| Tín hiệu công khai | Ý nghĩa với bài toán | Việc phải xác minh |
| --- | --- | --- |
| Mạng lưới nhiều cơ sở | Có thể có nhu cầu longitudinal summary, referral, follow-up và discharge handoff | Patient ID, encounter ID, episode-of-care và cross-site record linking |
| Định hướng academic healthcare/research/innovation | Phù hợp với research protocol, reviewer và safety gate | Clinical PI, ethics/IRB, data access, publication policy |
| Chính sách bảo vệ dữ liệu cá nhân | Bắt buộc private-by-default, audit-first, de-identified-first | Legal basis, DPO/legal review, retention, cloud/vendor/data-transfer controls |
| Hệ sinh thái AI y tế Việt Nam có tiền lệ ở imaging | Có bài học về dataset, annotation, validation | Không suy luận từ imaging sang text; text summarization cần validation riêng |
| Chưa có công bố công khai về RAG summarization trong HIS/EMR Vinmec | Khoảng trống nghiên cứu rõ ràng | Stakeholder interview, workflow observation, technical integration assessment |

## 3. Bài toán cụ thể nên đưa vào Vinmec

Không nên bắt đầu bằng mục tiêu “AI tóm tắt mọi hồ sơ bệnh án”. Mục tiêu đó quá
rộng, khó đánh giá và dễ vượt ranh giới an toàn. Nên bắt đầu bằng một workflow
hẹp:

> **AI-generated discharge handoff draft có citation cho một khoa nội trú người
> lớn tại một site.**

### 3.1 Lý do chọn discharge handoff draft

Workflow này phù hợp cho pilot vì:

- có nhu cầu thật: bác sĩ phải tổng hợp diễn biến, chẩn đoán, thủ thuật, thuốc,
  xét nghiệm, follow-up và cảnh báo;
- có ranh giới output rõ hơn patient-facing summary;
- có thể so sánh với discharge summary hiện hữu như weak reference;
- có thể review bởi bác sĩ nội trú/chuyên khoa;
- có thể đo accept/edit/reject, edit time và critical error;
- phù hợp với evidence-first vì mỗi claim quan trọng cần nguồn.

### 3.2 Các workflow khác nên để sau

| Workflow | Giá trị | Vì sao chưa nên là pilot đầu tiên |
| --- | --- | --- |
| Pre-rounding / daily summary | Giúp bác sĩ nắm diễn biến 24–72 giờ | Đòi hỏi dữ liệu gần thời gian thực và timeline rất chặt |
| Longitudinal outpatient summary | Hữu ích cho tái khám nhiều lần | Dữ liệu trải nhiều encounter, template và site |
| Referral/transfer summary | Quan trọng cho chuyển khoa/chuyển viện | Cần master patient identity và cross-site semantics tốt |
| Insurance/admin summary | Tiết kiệm thời gian hành chính | Ít phù hợp nếu mục tiêu là clinical evidence-first |
| Patient-facing summary | Tăng khả năng hiểu hồ sơ cho người bệnh | Rủi ro diễn giải và trách nhiệm pháp lý cao hơn |

## 4. Bài học từ PoC hiện tại

PoC hiện tại đã chứng minh được một lõi kỹ thuật đủ tốt để làm nền nghiên cứu:

- end-to-end flow từ retrieval, generation, citation validation, doctor review
  boundary đến admin evaluation;
- benchmark nhiều provider trên 50 records, gồm no-gate run và gated run tách
  biệt;
- đánh giá không chỉ ROUGE/BERTScore mà còn citation coverage, factuality proxy,
  timeline proxy, hallucinated entities và critical omission proxy;
- retrieval gate minh họa khả năng dừng khi thiếu evidence bắt buộc;
- human-review package có blinding và blank score sheet, không giả lập điểm con
  người;
- local Docker Compose staging và evidence package đã được chuẩn hóa.

Những điểm này giúp PoC đủ mạnh cho final demo và đủ nghiêm túc để đề xuất
pilot. Tuy nhiên, PoC chưa phải bằng chứng cho dữ liệu thật tại bệnh viện. Nó
chưa chứng minh giảm thời gian bác sĩ trong workflow thật, chưa chứng minh trên
dữ liệu Vinmec, chưa chứng minh phù hợp mọi khoa và chưa cho phép writeback vào
HIS/EMR.

## 5. Vì sao không chỉ dùng Raw summarization?

Benchmark hiện tại có source trung bình khoảng 500–600 tokens, thường chỉ tương
đương khoảng 2.000–2.500 ký tự tiếng Anh. Với một note ngắn như vậy, Raw có thể
đưa gần như toàn bộ thông tin vào model và đạt ROUGE tốt.

Nhưng một encounter bệnh viện thực tế có thể có:

- admission note;
- progress notes nhiều ngày;
- consultation notes nhiều chuyên khoa;
- medication list và thay đổi thuốc;
- allergies;
- lab trend;
- radiology reports;
- procedure/surgery notes;
- nursing notes;
- discharge planning.

Vì vậy, câu hỏi nghiên cứu không nên là “Raw hay RAG thắng tuyệt đối?”. Câu hỏi
tốt hơn là:

> Với từng loại hồ sơ, context strategy nào giúp bác sĩ kiểm tra evidence nhanh
> hơn và giảm rủi ro bỏ sót/sai claim?

| Tình huống | Strategy đề xuất | Lý do |
| --- | --- | --- |
| Một note ngắn, nằm trọn context window | Raw/full-note + citation extraction | Ít mất mát qua retrieval |
| Vài note có cấu trúc rõ | Structured Context | Giữ logic section, giảm overhead vector search |
| Nhiều ngày, nhiều tài liệu, vượt context window | Section-aware RAG | Chọn evidence, có citation, có patient/encounter filter |
| Thiếu diagnosis/medication/allergy evidence bắt buộc | Block hoặc review retrieval trước | Không ép model sinh khi thiếu nền bằng chứng |
| Evidence mâu thuẫn | Hiển thị conflict cho bác sĩ | Không để model tự giải quyết mâu thuẫn lâm sàng |

Kết luận đúng: **Raw phù hợp note ngắn; RAG phù hợp evidence traceability trên
hồ sơ dài/đa tài liệu; hướng tốt nhất cho bệnh viện là adaptive evidence-first
routing.**

## 6. Vai trò của chunking, embedding và Qdrant

Pipeline nghiên cứu đề xuất:

```text
HIS/EMR read-only extract
  → de-identification / pseudonymization
  → normalization
  → section-aware chunking
  → embedding từng chunk
  → private vector index
  → patient/encounter/site-filtered retrieval
  → adaptive context builder
  → draft generation
  → claim/citation/gate validation
  → clinician review
  → research metrics and audit
```

Chunking không phải việc của Qdrant. Chunking xảy ra trước để tạo đơn vị bằng
chứng có section, source span và metadata. Embedding biểu diễn ý nghĩa từng
chunk. Qdrant lưu vector và payload cần thiết để tìm lại top-k chunk phù hợp,
đồng thời lọc theo patient/encounter/site.

Điểm an toàn quan trọng: embedding không nên được mặc định là dữ liệu ẩn danh.
Vector, metadata và raw chunk payload vẫn có thể chứa hoặc suy ra thông tin
lâm sàng nhạy cảm. Vì vậy, trong bối cảnh Vinmec:

- Qdrant nên nằm trong private research/security boundary;
- payload nên được tối thiểu hóa;
- raw chunk text nên được bảo vệ như clinical data;
- không đưa raw notes, chunks, embeddings hoặc snapshots lên public cloud khi
  chưa có phê duyệt pháp lý, bảo mật và data-processing phù hợp;
- logs không được chứa raw clinical text.

## 7. Câu hỏi nghiên cứu

### RQ1 — Chất lượng summary

Raw, Structured Context, Section-aware RAG và Adaptive routing khác nhau thế nào
về factual correctness, clinical completeness, critical omission và critical
commission?

### RQ2 — Chất lượng evidence

Citation có thật sự hỗ trợ claim hay chỉ trỏ tới đoạn có từ khóa tương tự?

### RQ3 — Hiệu quả workflow

Draft có giúp bác sĩ giảm thời gian đọc/tổng hợp/chỉnh sửa so với tạo summary
từ đầu không?

### RQ4 — Điều kiện RAG có lợi

RAG có lợi hơn Raw ở ngưỡng nào về số note, số ngày điều trị, số chuyên khoa,
timeline complexity và medication density?

### RQ5 — Retrieval gate

Gate chặn được case thiếu evidence quan trọng tới đâu và tạo bao nhiêu false
block?

### RQ6 — Generalization

Kết quả có giữ được khi đổi khoa, đổi site, đổi template, đổi ngôn ngữ và đổi
phong cách ghi chép không?

## 8. Thiết kế pilot theo P0, P1, P2

### P0 — Governance, workflow và research readiness

**Mục tiêu:** biến PoC thành proposal đủ điều kiện để clinical, IT, security,
legal/DPO và ethics reviewer xem xét.

| Hạng mục | Deliverable | Exit gate |
| --- | --- | --- |
| Clinical scope | Một site, một khoa, một summary type, một workflow | Có clinical PI và workflow owner |
| Governance | Research protocol, ethics/IRB hoặc waiver rationale, privacy/risk assessment | Không xin dữ liệu thật trước governance gate |
| Data map | HIS/EMR notes, LIS, RIS/PACS reports, medication, allergy, procedure, discharge summary | Biết nguồn nào structured/free-text và ai là custodian |
| Safety taxonomy | Critical omission/commission, wrong-patient evidence, unsupported diagnosis, medication/allergy error | Có severity scale và stopping rules |
| Technical boundary | Research-only environment, read-only extract, no writeback, no public PHI | Security lead phê duyệt boundary |
| Evaluation design | Reviewer rubric, blinded sample, adjudication, metric hierarchy | Human scoring sheet sẵn sàng trước khi chạy pilot |
| Reproducibility | Frozen model/prompt/schema/index versioning | Có audit trail cho từng output |

P0 kết thúc khi dự án đủ điều kiện đạo đức, pháp lý và kỹ thuật để dùng dữ liệu
hồi cứu đã giảm định danh. Nếu P0 chưa xong, mọi demo tiếp tục dùng mock hoặc
de-identified synthetic data.

### P1 — Retrospective offline pilot

**Mục tiêu:** kiểm tra chất lượng trên dữ liệu hồi cứu đã giảm định danh, chưa
đưa output vào workflow điều trị thật.

| Thành phần | Thiết kế |
| --- | --- |
| Dataset | Retrospective de-identified encounters, stratified theo độ dài, số note, số ngày, khoa, ngôn ngữ, medication density và timeline complexity |
| Split | Development, validation, locked test |
| Arms | Raw/full-context, Structured Context, Section-aware RAG, Adaptive routing |
| Frozen variables | Cùng generator, prompt task, decoding, output schema và test set |
| Primary review | Bác sĩ chấm factual correctness, clinical completeness, critical omission, critical commission và citation usefulness |
| Proxy metrics | ROUGE/BERTScore/citation/factuality/timeline chỉ hỗ trợ phân tích, không thay human validation |
| Output | Offline report, failure taxonomy, safety case, recommendation có/không chuyển sang shadow mode |

P1 trả lời:

1. summary có đủ đáng tin để đưa vào shadow mode không;
2. citation có giúp bác sĩ kiểm chứng claim không;
3. retrieval gate block đúng hay tạo quá nhiều false block;
4. adaptive routing có tốt hơn ép mọi case dùng cùng một flow không;
5. lỗi nào xuất hiện nhiều nhất và mitigation nào cần làm trước P2.

### P2 — Silent/shadow mode và clinician-visible usability pilot

**Mục tiêu:** kiểm tra workflow fit trong môi trường gần thực tế nhưng vẫn không
tác động quyết định chăm sóc.

P2 nên tách hai bước:

1. **Silent/shadow mode:** hệ thống chạy song song; output không tác động chăm
   sóc, không ghi vào HIS/EMR và không dùng để đánh giá hiệu suất cá nhân.
2. **Clinician-visible usability pilot:** chỉ sau khi shadow mode đạt exit gate,
   bác sĩ được xem draft trong giao diện nghiên cứu, có quyền reject/fallback
   và phải review citation trước khi sử dụng.

| Điều kiện vào P2 | Lý do |
| --- | --- |
| Không có wrong-patient retrieval trong locked test | Đây là lỗi dừng pilot |
| Critical errors có root-cause và mitigation | Không đưa lỗi không hiểu được vào workflow |
| UI hiển thị draft/citation/warning rõ | Giảm nguy cơ bác sĩ over-trust |
| Latency phù hợp workflow | Không làm chậm chăm sóc |
| Audit đầy đủ | Tái tạo được output khi có incident |
| Incident response đã diễn tập | Biết pause/revoke/escalate khi có lỗi |

## 9. Vinmec Applicability Matrix

| Khía cạnh | PoC hiện tại | Cần kiểm chứng tại Vinmec | Rủi ro |
| --- | --- | --- | --- |
| Data | Mock/de-identified benchmark records | HIS/EMR structure, Vietnamese/mixed notes, templates, duplicate/copy-forward | High |
| Patient boundary | Patient/encounter filter trong RAG | Master patient identity, encounter/site boundary, cross-site linking | High |
| Retrieval | Qdrant retrieval + gate | Wrong-patient prevention, section-aware chunking, Vietnamese terminology | High |
| Generation | Multi-provider benchmark, deterministic control | Frozen model/prompt/schema, no silent drift, clinical style constraints | Medium |
| Evidence | Citation coverage and unsupported-claim proxy | Citation truly supports claim, not just lexical match | High |
| Evaluation | Proxy metrics and human-review package | Real clinician review, adjudication, edit time, accept/edit/reject | High |
| Deployment | Local Docker Compose staging | Private research environment, RBAC, audit, retention, no public PHI | Medium |
| Governance | Safety disclaimers and no-writeback boundary | Ethics/IRB, legal/DPO, cybersecurity, data processing agreement | High |
| Workflow | Doctor review UI concept | Actual handoff/discharge workflow, role ownership, escalation path | High |
| Scale | Single-repo PoC | Site-to-site generalization, specialty shift, monitoring, versioning | Medium |

## 10. Human evaluation design

### 10.1 Reviewer setup

- Tối thiểu hai reviewer lâm sàng độc lập cho locked sample.
- Reviewer không biết arm nào tạo output nếu có thể blind.
- Bất đồng quan trọng được adjudicate bởi reviewer thứ ba hoặc clinical PI.
- Không dùng AI-generated score thay cho human score.

### 10.2 Rubric

| Dimension | Câu hỏi chấm |
| --- | --- |
| Factual correctness | Claim có đúng theo source không? |
| Clinical completeness | Có bỏ sót thông tin quan trọng không? |
| Critical omission | Có thiếu diagnosis/medication/allergy/procedure/timeline quan trọng không? |
| Critical commission | Có thêm thông tin nguy hiểm không có trong source không? |
| Citation support | Citation có thật sự chứng minh claim không? |
| Timeline correctness | Thứ tự diễn biến có hợp lý không? |
| Clinical usefulness | Draft có giúp bác sĩ làm việc nhanh/rõ hơn không? |
| Action | Accept, minor edit, major edit, reject |
| Effort | Thời gian review/edit và loại chỉnh sửa |

### 10.3 Metric hierarchy

Human review phải đứng trên proxy metrics:

```text
Critical safety review
→ clinician factual/completeness review
→ citation support review
→ workflow/edit-time review
→ proxy metrics such as ROUGE/BERTScore
```

ROUGE và BERTScore có ích để phân tích mô hình, nhưng không đủ để kết luận cho
workflow bệnh viện. Một output có ROUGE cao vẫn có thể nguy hiểm nếu sai thuốc,
sai dị ứng, sai timeline hoặc citation không hỗ trợ claim.

## 11. Risk register

| Risk | Severity | Example | Mitigation | Stop/pause rule |
| --- | --- | --- | --- | --- |
| Wrong-patient evidence | Critical | Citation lấy từ bệnh nhân khác | Hard patient/encounter/site filters, automated tests, audit | Dừng pilot và incident review ngay |
| Unsupported diagnosis | Critical | Draft nêu diagnosis không có evidence | Claim validation, mandatory diagnosis evidence, visible unsupported flag | Dừng arm/model nếu lặp lại sau mitigation |
| Medication/allergy error | Critical | Sai thuốc, liều, dị ứng hoặc bỏ sót dị ứng | Structured medication/allergy extraction, reviewer checklist, high-risk gate | Pause clinician-visible pilot |
| Timeline inversion | High | Sự kiện sau discharge bị đặt trước admission | Timeline extraction, date normalization, temporal consistency checks | Review batch và sửa normalization |
| Over-trust by doctor | High | Bác sĩ đọc draft như kết luận đã xác nhận | Draft-only label, forced citation review, reject/fallback | Pause nếu reviewer hiểu nhầm repeated |
| PHI leakage in logs | Critical | Raw note xuất hiện trong logs/export | Redaction, PHI-safe audit metadata, log scanning, access restriction | Dừng environment và rotate credentials |
| Retrieval false block | Medium | Gate block case có đủ evidence nhưng section sai | Gate case review, section classifier improvement | Không mở rộng nếu false block quá cao |
| Citation not supporting claim | High | Citation cùng keyword nhưng không chứng minh claim | Citation support rubric, reviewer adjudication, claim-level scoring | Không chuyển sang P2 nếu phổ biến |
| Model/version drift | High | Kết quả thay đổi không tái tạo được | Frozen model/prompt/schema/index versions | Không dùng output không tái tạo được |
| Workflow slowdown | Medium | Bác sĩ mất thêm thời gian vì UI khó dùng | Usability testing, edit-time metric, fallback path | Không mở rộng nếu time-to-review tăng rõ |

## 12. Governance và dữ liệu

Vinmec công bố hồ sơ sức khỏe và đời tư trong medical records là sensitive
personal data. Vì vậy proposal phải được thiết kế theo nguyên tắc:

- de-identified-retrospective-first;
- private research environment;
- least privilege access;
- no public PHI;
- no raw clinical text in logs;
- no writeback trong P0/P1;
- audit mọi lần generate/review/export;
- retention/deletion rõ;
- legal/DPO/security review trước khi nhận dữ liệu thật.

Các hồ sơ governance tối thiểu:

- research protocol;
- ethics/IRB approval hoặc waiver rationale phù hợp;
- data protection/risk assessment;
- data management plan;
- data processing/sharing agreement;
- access-control matrix;
- retention/deletion schedule;
- incident and breach response plan;
- publication/model-release policy;
- statement cấm tái định danh.

Tài liệu này không phải ý kiến pháp lý. Trước khi nghiên cứu thật, pháp chế/DPO
của Vinmec phải xác nhận luật, nghị định, thông tư Bộ Y tế, quy định nghiên cứu
và yêu cầu chuyển dữ liệu đang có hiệu lực tại thời điểm triển khai.

## 13. Research architecture

```text
Vinmec HIS/EMR read-only source
  → approved retrospective export
  → de-identification / pseudonymization
  → research data store
  → section-aware normalization and chunking
  → private vector index
  → patient/encounter/site-filtered retrieval
  → adaptive context builder
  → draft generation
  → claim/citation/gate validation
  → clinician review workspace
  → research metrics and audit package
```

Design constraints:

- không public PHI;
- không HIS/EMR writeback trong P0/P1;
- không hành động lâm sàng tự động;
- không chuyển dữ liệu sang vendor/model bên ngoài nếu chưa được phê duyệt;
- không log raw clinical text;
- mỗi output phải gắn với data snapshot, index version, model version, prompt
  version, reviewer action và timestamp.

## 14. Go/no-go criteria

### Go từ P0 sang P1

- Clinical scope và summary type được phê duyệt.
- Data source và custodian được xác định.
- Ethics/legal/security path rõ.
- De-identification và access boundary được chấp nhận.
- Reviewer rubric và evaluation plan đã sẵn sàng.

### Go từ P1 sang P2 shadow mode

- Locked test không có wrong-patient evidence.
- Critical errors dưới ngưỡng protocol định nghĩa.
- Citation support đủ để bác sĩ review.
- Retrieval gate failures được hiểu và có mitigation.
- Output tái tạo được bằng model/prompt/index/data version.

### Go từ shadow mode sang clinician-visible usability pilot

- Shadow-mode review không phát hiện unresolved critical risks.
- UI hiển thị draft-only status, citation và unsupported warning rõ.
- Bác sĩ có quyền reject/fallback.
- Incident response đã diễn tập.
- Latency và availability phù hợp workflow đã chọn.

### No-go / pause

- Có wrong-patient evidence.
- PHI rời khỏi approved boundary.
- Lặp lại unsupported medication/allergy/diagnosis claims.
- Reviewer hiểu nhầm draft là signed clinical record.
- Không tái tạo được output.
- Có áp lực sử dụng draft như công cụ tự ra quyết định lâm sàng.

## 15. Lộ trình 9–12 tháng đề xuất

| Tháng | Kết quả |
| --- | --- |
| 1–2 | Workflow discovery, governance, ethics/security submissions |
| 2–4 | De-identified dataset, Vietnamese normalization, baseline reproduction |
| 4–6 | Controlled Raw/Structured/RAG/Adaptive study |
| 6–8 | Locked human evaluation và safety case |
| 8–10 | Prospective silent/shadow mode nếu đạt gate |
| 10–12 | Clinician-visible usability pilot nếu shadow-mode review đạt |

Timeline có thể dài hơn nếu data access, ethics, HIS integration hoặc security
review chưa hoàn tất. Không được rút ngắn bằng cách bỏ governance gate.

## 16. Deliverables

| Phase | Deliverables |
| --- | --- |
| P0 | Research protocol, workflow map, data-flow diagram, governance checklist, risk register, reviewer rubric, no-writeback technical boundary |
| P1 | Offline comparison report, human evaluation results, failure taxonomy, gate analysis, adaptive routing recommendation, safety case |
| P2 | Shadow-mode report, usability findings, incident log, go/no-go decision, external-validation plan |

## 17. Vì sao proposal này mạnh

Proposal này mạnh vì không hứa quá mức. Nó biến PoC hiện tại thành một research
instrument có kỷ luật:

- bắt đầu bằng một workflow thay vì toàn viện;
- tách proxy benchmark khỏi human validation;
- xem RAG là evidence infrastructure, không phải công cụ làm ROUGE tăng bằng mọi
  giá;
- giữ bác sĩ là người review cuối;
- có stop/pause rules;
- đặt dữ liệu thật sau governance gate;
- có đường đi từ PoC sang retrospective study, shadow mode và usability pilot.

Nếu mentor hỏi “điểm mới ở đâu?”, câu trả lời nên là:

> Dự án không chỉ benchmark model. Dự án xây một khuôn khổ clinical NLP có kiểm
> soát: đo provider, kiểm tra citation, phân tích failure, tách proxy metric khỏi
> human validation, giữ bác sĩ trong vòng review và thiết kế đường đi thực tế từ
> PoC sang research pilot tại Vinmec.

## 18. Final conclusion

Bước tiếp theo tốt nhất cho bài toán này tại Vinmec là **research-first pilot**,
không phải public cloud deployment và không phải triển khai rộng ngay.

PoC hiện tại nên được trình bày là một prototype local staging đã chứng minh
được workflow evidence-first: AI tạo bản nháp, claim có nguồn, retrieval có
gate, bác sĩ duyệt cuối cùng, quá trình có audit và benchmark có interpretation
boundary.

Nếu pilot thành công, dự án có thể chuyển từ “model benchmark” sang “clinical
workflow evidence”: trong một workflow hẹp và được quản trị đúng, AI-generated
draft có citation/gate/clinician review có thể được kiểm tra xem có giảm gánh
nặng documentation mà không làm tăng lỗi quan trọng hay không.

Đây là framing 10/10: đủ tham vọng để có giá trị bệnh viện thật, nhưng đủ kỷ
luật để phù hợp với governance y tế.

## 19. Nguồn công khai dùng để định hướng

- [Vinmec — Vision and Mission](https://www.vinmec.com/eng/vision-and-mission/)
- [Vinmec — Hospitals and Clinics Directory](https://www.vinmec.com/eng/hospital/)
- [Vinmec — Personal Data Protection Policy](https://www.vinmec.com/eng/blog/personal-data-protection-policy-of-vinmec-international-general-hospital-joint-stock-company)
- [Vinmec — Research Institute of Stem Cell and Gene Technology](https://www.vinmec.com/eng/specialties/vinmec-research-institute-of-stem-cell-and-gene-technology)
- [VinDr-CXR — Open chest X-ray dataset with radiologist annotations](https://arxiv.org/abs/2012.15029)
- [Cổng Thông tin điện tử Chính phủ — Nghị định 13/2023/NĐ-CP](https://vanban.chinhphu.vn/?docid=207759&pageid=27160)
