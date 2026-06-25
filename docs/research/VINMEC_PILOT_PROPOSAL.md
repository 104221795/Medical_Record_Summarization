# Vinmec Pilot Proposal — Citation-grounded Medical Record Summarization

> **Trạng thái tài liệu:** đề xuất nghiên cứu/pilot, không phải xác nhận Vinmec
> đã phê duyệt, cung cấp dữ liệu, tích hợp HIS/EMR hoặc sử dụng hệ thống.
>
> **Ranh giới lâm sàng:** hệ thống chỉ tạo **AI-generated draft** để bác sĩ
> kiểm tra. Không chẩn đoán, không khuyến nghị điều trị, không tự ký hồ sơ,
> không ghi ngược vào HIS/EMR và không thay thế quyết định lâm sàng.

> **Ghi chú nộp bài:** bản proposal tổng hợp nên nộp là
> [VINMEC_MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md](VINMEC_MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md).
> File này được giữ như tài liệu tham chiếu chi tiết về pilot.

## 1. One-page proposal

### Vấn đề

Bác sĩ thường phải tổng hợp thông tin từ nhiều nguồn: admission note, progress
notes, xét nghiệm, chẩn đoán hình ảnh, thuốc, dị ứng, thủ thuật, consultation
notes và discharge planning. Với bệnh viện nhiều cơ sở và nhiều chuyên khoa,
gánh nặng không chỉ là “viết summary”, mà là **tìm đúng bằng chứng, không bỏ sót
điểm quan trọng và bàn giao thông tin an toàn**.

### Đề xuất

Thực hiện một pilot nghiên cứu có kiểm soát tại Vinmec cho bài toán
**citation-grounded medical record summarization**:

- đầu vào là dữ liệu hồi cứu đã giảm định danh trong môi trường nghiên cứu riêng;
- hệ thống tạo draft summary có citation theo từng claim quan trọng;
- retrieval bị giới hạn theo patient/encounter/site boundary;
- hệ thống có gate để dừng hoặc cảnh báo khi thiếu bằng chứng bắt buộc;
- bác sĩ review, chỉnh sửa, reject hoặc approve theo workflow nghiên cứu;
- không có HIS/EMR writeback trong giai đoạn pilot.

### Pilot đầu tiên nên chọn gì?

Khuyến nghị chọn **clinician-facing discharge handoff draft** cho **một khoa nội
trú người lớn tại một site**. Đây là phạm vi đủ hẹp để kiểm soát rủi ro nhưng đủ
giàu dữ liệu để RAG/evidence-first có ý nghĩa hơn benchmark một-note ngắn.

### Câu hỏi nghiên cứu chính

> Trên dữ liệu và workflow Vinmec được quản trị đúng, một hệ thống tạo draft
> summary có citation và retrieval gate có giúp bác sĩ tổng hợp/kiểm tra hồ sơ
> nhanh hơn mà không làm tăng critical omission, critical commission hoặc
> unsupported clinical claims hay không?

### Kết luận định hướng

Pilot không nên chứng minh “AI thay bác sĩ”. Pilot nên chứng minh một câu hẹp
hơn nhưng có giá trị hơn:

> AI có thể hỗ trợ bác sĩ bằng cách tạo bản nháp có nguồn, biết chỉ ra phần thiếu
> bằng chứng, và để bác sĩ giữ toàn quyền duyệt cuối cùng.

## 2. Vì sao không chỉ dùng Raw summarization?

Raw summarization có thể tốt trên một note ngắn vì model nhìn được gần như toàn
bộ input. Nhưng bối cảnh bệnh viện thực tế thường khác: một encounter có nhiều
ngày điều trị, nhiều chuyên khoa, nhiều loại tài liệu và nhiều thông tin thay
đổi theo thời gian.

Vì vậy, pilot không nên đặt câu hỏi “Raw hay RAG thắng tuyệt đối?”. Câu hỏi tốt
hơn là **case nào dùng context strategy nào**:

| Tình huống | Strategy đề xuất | Lý do |
| --- | --- | --- |
| Một note ngắn, dưới context window | Raw/full-note + citation extraction | Giữ toàn bộ thông tin, ít mất mát qua retrieval |
| Vài note có cấu trúc rõ | Structured context | Giữ section logic, giảm overhead vector search |
| Hồ sơ dài, nhiều tài liệu, nhiều ngày | Section-aware RAG | Chọn đúng evidence, có citation và patient/encounter filter |
| Thiếu diagnosis/medication/allergy evidence bắt buộc | Retrieval review hoặc block | Không ép model sinh nội dung khi thiếu nền bằng chứng |
| Evidence mâu thuẫn | Hiển thị conflict cho bác sĩ | Không để model tự “hòa giải” thông tin lâm sàng nhạy cảm |

Do đó hướng 10/10 không phải “RAG thay Raw”, mà là **adaptive evidence-first
summarization**.

## 3. P0, P1, P2 pilot plan

### P0 — Governance, workflow và research readiness

**Mục tiêu:** biến PoC thành một đề cương pilot có thể được clinical, IT,
security, legal/DPO và ethics reviewer xem xét.

| Hạng mục P0 | Deliverable | Exit gate |
| --- | --- | --- |
| Clinical scope | Chọn một site, một khoa, một summary type, một workflow | Có clinical PI và workflow owner |
| Governance | Research protocol, ethics/IRB hoặc waiver rationale, data protection/risk assessment | Không xin dữ liệu thật trước khi ký governance gate |
| Data map | Danh sách nguồn: HIS/EMR notes, LIS, RIS/PACS report, medication, allergy, procedure, discharge summary | Biết dữ liệu nào là structured/free-text và ai là custodian |
| Safety taxonomy | Critical omission/commission, wrong-patient evidence, unsupported diagnosis, medication/allergy error | Có severity scale và stopping rules |
| Technical boundary | Research-only environment, read-only extract, no writeback, no public cloud PHI | Security lead phê duyệt boundary |
| Evaluation design | Reviewer rubric, blinded sample, adjudication, metric hierarchy | Human scoring sheet sẵn sàng trước khi chạy pilot |
| Reproducibility | Frozen model/prompt/schema/index versioning | Có audit trail cho từng output |

P0 kết thúc khi dự án đủ điều kiện đạo đức, pháp lý và kỹ thuật để dùng dữ liệu
hồi cứu đã giảm định danh. Nếu P0 chưa xong, mọi demo vẫn phải dùng mock hoặc
de-identified synthetic data.

### P1 — Retrospective offline pilot

**Mục tiêu:** kiểm tra chất lượng trên dữ liệu hồi cứu đã giảm định danh, chưa
đưa output vào workflow điều trị thật.

Thiết kế đề xuất:

| Thành phần | Thiết kế |
| --- | --- |
| Dataset | Retrospective de-identified encounters, stratified theo độ dài, số ngày, số note, khoa, ngôn ngữ, medication density và timeline complexity |
| Split | Development, validation, locked test |
| Arms | Raw/full-context, Structured Context, Section-aware RAG, Adaptive routing |
| Frozen variables | Cùng generator, prompt task, decoding, output schema và test set |
| Primary review | Bác sĩ chấm factual correctness, clinical completeness, critical omission, critical commission, citation usefulness |
| Proxy metrics | ROUGE/BERTScore/citation/factuality/timeline chỉ dùng hỗ trợ phân tích, không thay human validation |
| Output | Research report + safety case + recommendation có/không chuyển sang shadow mode |

P1 không nhằm tối ưu model bằng mọi giá. P1 nhằm trả lời:

1. summary có đủ đúng để đáng đưa vào shadow mode không;
2. citation có thật sự giúp bác sĩ kiểm chứng claim không;
3. retrieval gate block đúng case thiếu evidence hay tạo quá nhiều false block;
4. adaptive routing có tốt hơn ép mọi case dùng cùng một flow không;
5. lỗi nào xuất hiện nhiều nhất và có mitigation rõ không.

### P2 — Prospective silent mode và clinician-visible usability pilot

**Mục tiêu:** kiểm tra workflow fit trong môi trường gần thực tế nhưng vẫn giữ
ranh giới an toàn.

P2 nên tách hai bước:

1. **Silent/shadow mode**: hệ thống chạy song song, output không tác động chăm
   sóc, không hiển thị cho bác sĩ điều trị trước khi documentation hoàn tất.
2. **Clinician-visible usability pilot**: chỉ sau khi shadow mode đạt exit gate,
   bác sĩ được xem draft trong giao diện nghiên cứu, có quyền reject/fallback và
   phải ký xác nhận theo workflow hiện hữu.

| Điều kiện vào P2 | Lý do |
| --- | --- |
| Không có wrong-patient retrieval trong locked test | Đây là lỗi dừng pilot |
| Critical errors có root-cause và mitigation | Không đưa lỗi không hiểu được vào workflow |
| UI hiển thị draft/citation/warning rõ | Giảm nguy cơ bác sĩ over-trust |
| Latency phù hợp workflow | Không làm chậm chăm sóc |
| Audit đầy đủ | Tái tạo được output khi có incident |
| Incident response đã diễn tập | Biết pause/revoke/escalate khi có lỗi |

P2 không phải triển khai vận hành chính thức. P2 là nghiên cứu usability và safety under
workflow constraints.

## 4. Vinmec Applicability Matrix

| Khía cạnh | PoC hiện tại | Cần kiểm chứng tại Vinmec | Mức rủi ro |
| --- | --- | --- | --- |
| Data | Mock/de-identified benchmark records | HIS/EMR structure, Vietnamese/mixed notes, section templates, duplicate/copy-forward patterns | High |
| Patient boundary | Patient/encounter filter trong RAG | Master patient identity, encounter/site boundary, cross-site linking | High |
| Retrieval | Qdrant vector retrieval + gate | Wrong-patient prevention, section-aware chunking, Vietnamese terminology | High |
| Generation | Multi-provider benchmark và deterministic control | Frozen clinical style, no silent drift, reviewer-facing output schema | Medium |
| Evidence | Citation coverage và unsupported-claim proxy | Citation truly supports claim, not just lexical match | High |
| Evaluation | Proxy metrics, failure matrix, human-review package | Real clinician review, adjudication, edit time, accept/edit/reject | High |
| Deployment | Local Docker Compose staging | Private research environment, RBAC, audit, retention, no public PHI | Medium |
| Governance | Safety disclaimers and no-writeback boundary | Ethics/IRB, legal/DPO, cybersecurity, data processing agreement | High |
| Workflow | Doctor review UI concept | Actual handoff/discharge workflow, role ownership, escalation path | High |
| Scale | Single-repo PoC | Site-to-site generalization, specialty shift, monitoring and model/index versioning | Medium |

## 5. Risk register

| Risk | Severity | Example | Mitigation | Stop/pause rule |
| --- | --- | --- | --- | --- |
| Wrong-patient evidence | Critical | Citation lấy từ bệnh nhân khác | Hard patient/encounter/site filters, automated tests, audit | Dừng pilot và incident review ngay |
| Unsupported diagnosis | Critical | Draft nêu diagnosis không có evidence | Claim validation, mandatory diagnosis evidence, visible unsupported flag | Dừng arm/model nếu lặp lại sau mitigation |
| Medication/allergy error | Critical | Sai thuốc, liều, dị ứng hoặc bỏ sót dị ứng | Structured medication/allergy extraction, reviewer checklist, high-risk section gate | Pause clinician-visible pilot |
| Timeline inversion | High | Sự kiện sau discharge bị đặt trước admission | Timeline extraction, date normalization, temporal consistency checks | Review batch và sửa normalization |
| Over-trust by doctor | High | Bác sĩ đọc draft như kết luận đã xác nhận | UI watermark, draft-only label, forced citation review, reject/fallback | Pause nếu reviewer hiểu nhầm repeated |
| PHI leakage in logs | Critical | Raw note xuất hiện trong logs/export | Redaction, PHI-safe audit metadata, log scanning, access restriction | Dừng environment và rotate credentials |
| Retrieval false block | Medium | Gate block case có đủ evidence nhưng section sai | Gate case review, section classifier improvement | Không mở rộng nếu false block quá cao |
| Citation not supporting claim | High | Citation cùng keyword nhưng không chứng minh claim | Citation support rubric, reviewer adjudication, claim-level scoring | Không chuyển sang P2 nếu phổ biến |
| Model/version drift | High | Kết quả thay đổi không tái tạo được | Frozen model/prompt/schema/index versions | Không dùng output không tái tạo được |
| Workflow slowdown | Medium | Bác sĩ mất thêm thời gian vì UI khó dùng | Usability testing, edit-time metric, fallback path | Không mở rộng nếu time-to-review tăng rõ |

## 6. Human evaluation design

### Reviewer setup

- Tối thiểu hai reviewer lâm sàng độc lập cho locked sample.
- Reviewer không biết arm nào tạo output nếu có thể blind.
- Bất đồng quan trọng được adjudicate bởi reviewer thứ ba hoặc clinical PI.
- Không dùng AI-generated score thay cho human score.

### Rubric

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

### Metric hierarchy

Human review phải đứng trên proxy metrics:

```text
Critical safety review
→ clinician factual/completeness review
→ citation support review
→ workflow/edit-time review
→ proxy metrics such as ROUGE/BERTScore
```

ROUGE và BERTScore có ích để phân tích mô hình, nhưng không đủ để kết luận lâm
sàng. Với medical record summarization, một output có ROUGE cao vẫn có thể nguy
hiểm nếu sai thuốc, sai dị ứng hoặc trích citation không hỗ trợ claim.

## 7. Architecture for research pilot

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

- no public PHI;
- no HIS/EMR writeback in P0/P1;
- no autonomous clinical action;
- no unapproved vendor/model data transfer;
- no raw clinical text in logs;
- every output must be linked to model, prompt, data snapshot, index version and
  reviewer action.

## 8. Go/no-go criteria

### Go from P0 to P1

- Clinical scope and summary type are approved.
- Data source and custodian are identified.
- Ethics/legal/security path is clear.
- De-identification and access boundary are accepted.
- Reviewer rubric and evaluation plan are ready.

### Go from P1 to P2 shadow mode

- Locked test has no wrong-patient evidence.
- Critical errors are below the threshold defined by protocol.
- Citation support is clinically reviewable.
- Retrieval gate failures are understood.
- Outputs are reproducible by model/prompt/index/data version.

### Go from shadow mode to clinician-visible usability pilot

- Shadow-mode review does not reveal unresolved critical risks.
- UI clearly marks draft-only status and unsupported claims.
- Doctors retain reject/fallback control.
- Incident response is rehearsed.
- Latency and availability fit the chosen workflow.

### No-go / pause

- Any wrong-patient evidence.
- PHI leakage outside approved boundary.
- Repeated unsupported medication/allergy/diagnosis claims.
- Reviewer confusion between draft and signed clinical record.
- Inability to reproduce outputs.
- Any pressure to use draft as autonomous clinical decision support.

## 9. P0/P1/P2 deliverables

| Phase | Deliverables |
| --- | --- |
| P0 | Research protocol, workflow map, data-flow diagram, governance checklist, risk register, reviewer rubric, no-writeback technical boundary |
| P1 | Offline comparison report, human evaluation results, failure taxonomy, gate analysis, adaptive routing recommendation, safety case |
| P2 | Shadow-mode report, usability findings, incident log, go/no-go decision, external-validation plan |

## 10. What makes this proposal strong

The strength of this proposal is not that it promises immediate deployment.
The strength is that it is deliberately narrow, measurable and safe:

- starts with one workflow instead of whole-hospital deployment;
- separates proxy benchmark from clinical validation;
- treats RAG as evidence infrastructure, not as a magic ROUGE booster;
- keeps doctors as final reviewers;
- has explicit stop rules;
- respects data governance before touching real records;
- turns the existing PoC into a research instrument.

## 11. Final pilot conclusion

The best next step for Vinmec is a **research-first pilot**, not a public-cloud
deployment and not an official live rollout. The PoC should be positioned as a
locally validated, citation-grounded prototype that is ready to support a
controlled study.

If the pilot succeeds, the project can move from “model benchmark” to “clinical
workflow evidence”: not proving broad clinical performance in general, but
showing under a narrow, governed workflow whether an AI-generated draft with
citation, gate and clinician review can reduce documentation burden without
increasing critical errors.

That is the credible 10/10 framing: ambitious enough for real hospital value,
but disciplined enough for clinical governance.
