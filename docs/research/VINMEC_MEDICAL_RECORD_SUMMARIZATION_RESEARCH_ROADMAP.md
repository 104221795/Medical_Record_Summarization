# Đề cương nghiên cứu Medical Record Summarization tại Vinmec

> **Trạng thái tài liệu:** đề xuất nghiên cứu và triển khai theo giai đoạn, không
> phải xác nhận Vinmec đã phê duyệt, cung cấp dữ liệu hoặc sử dụng hệ thống.
>
> **Ranh giới lâm sàng:** AI chỉ tạo bản nháp để bác sĩ kiểm tra. Không chẩn
> đoán, không khuyến nghị điều trị, không tự ký/xác nhận hồ sơ, không ghi ngược
> vào HIS/EMR trước khi hoàn tất phê duyệt đạo đức, pháp lý, an ninh, đánh giá
> con người và validation tại chỗ.

**Tài liệu companion:**

- [Vinmec Pilot Proposal](VINMEC_PILOT_PROPOSAL.md) — bản pitch/pilot plan
  theo P0/P1/P2, risk register, human evaluation và go/no-go.
- [Final Research Conclusion](FINAL_RESEARCH_CONCLUSION.md) — kết luận nghiên
  cứu ngắn gọn để dùng trong final report hoặc presentation.

## 1. Tóm tắt đề xuất

Nếu đưa dự án này vào Vinmec, hướng đúng không phải là “cài một chatbot tóm tắt
bệnh án”. Hướng đúng là xây một **nghiên cứu evidence-first clinical
summarization** với câu hỏi:

> Một hệ thống tạo bản nháp có citation, giới hạn theo đúng
> patient/encounter và biết từ chối khi thiếu bằng chứng có giúp bác sĩ giảm
> thời gian tổng hợp hồ sơ mà không làm tăng lỗi quan trọng hay không?

Nghiên cứu nên bắt đầu tại **một bệnh viện, một khoa, một loại summary và một
workflow**. Khuyến nghị ban đầu là chọn một đơn vị nội trú người lớn có nhiều
nguồn tài liệu nhưng quy trình tương đối ổn định, sau đó mới mở rộng sang khoa
khác hoặc bệnh viện khác.

Vinmec Times City là một ứng viên hợp lý để thảo luận pilot vì đây là một cơ sở
trong mạng lưới Vinmec và Vinmec công bố định hướng academic healthcare,
research và innovation. Đây là đề xuất suy luận từ thông tin công khai, không
phải xác nhận cơ sở này đã đồng ý tham gia. Nếu pilot diễn ra tại miền Bắc,
external validation nên thực hiện tại một cơ sở khác, ví dụ Central Park, để
đo site shift thay vì chỉ kiểm tra lại cùng một bệnh viện.

### 1.1 Hiện trạng công khai của Vinmec và ý nghĩa đối với bài toán

Từ thông tin công khai, có thể nhìn Vinmec như một môi trường **có tiềm năng
phù hợp cho nghiên cứu medical record summarization**, nhưng chưa thể kết luận
đã sẵn sàng triển khai. Điểm quan trọng là phải phân biệt ba lớp:

1. **Có tín hiệu công khai**: Vinmec là hệ thống bệnh viện nhiều cơ sở, có định
   hướng academic healthcare, innovation, nghiên cứu và có chính sách bảo vệ dữ
   liệu cá nhân.
2. **Có khả năng là nhu cầu thật**: hệ thống nhiều cơ sở, nhiều chuyên khoa và
   nhiều lần thăm khám thường tạo ra gánh nặng tổng hợp hồ sơ, chuyển tuyến,
   tái khám và discharge handoff.
3. **Chưa được xác nhận công khai**: không tìm thấy công bố công khai về một
   hệ thống LLM/RAG medical record summarization trong workflow HIS/EMR Vinmec.

Vì vậy, cách viết an toàn và mạnh nhất cho report là:

> Vinmec là bối cảnh có tính thuyết phục để đề xuất nghiên cứu ứng dụng
> evidence-first summarization, nhưng mọi giả định về HIS/EMR, dữ liệu thật,
> workflow bác sĩ, quyền truy cập và hiệu quả lâm sàng đều phải được xác minh
> qua discovery, governance và pilot có kiểm soát.

| Tín hiệu công khai | Ý nghĩa với bài toán summarization | Việc phải xác minh trước pilot |
| --- | --- | --- |
| Vinmec công bố là hệ thống bệnh viện/phòng khám nhiều cơ sở | Có khả năng tồn tại nhu cầu tóm tắt longitudinal record, referral, follow-up và discharge handoff giữa nhiều nơi chăm sóc | Kiến trúc patient ID, encounter ID, episode-of-care và khả năng liên kết hồ sơ giữa cơ sở |
| Vinmec định vị theo academic healthcare, research, innovation và tiêu chuẩn quốc tế | Phù hợp để bắt đầu bằng nghiên cứu có protocol, reviewer, safety gate và publication-quality evidence | Cơ chế phê duyệt nghiên cứu, clinical PI, ethics/IRB, data access và publication policy |
| Vinmec công bố chính sách bảo vệ dữ liệu cá nhân, trong đó hồ sơ sức khỏe là dữ liệu nhạy cảm | Bài toán bắt buộc phải thiết kế theo private-by-default, audit-first, de-identified-retrospective-first | Legal basis, consent/waiver, DPO/legal review, data retention, cross-border/cloud processing và vendor controls |
| Hệ sinh thái y tế/AI Việt Nam đã có kinh nghiệm đánh giá AI lâm sàng trong các bài toán khác, đặc biệt imaging | Đây là tín hiệu tích cực về năng lực nghiên cứu, nhưng không thay thế validation cho clinical text summarization | Không được suy luận từ imaging sang text; phải có đánh giá riêng cho Vietnamese/mixed clinical notes, citations và workflow bác sĩ |
| Không có bằng chứng công khai về triển khai RAG summarization tại Vinmec | Khoảng trống này chính là lý do đề xuất nên là research pilot, không phải deployment claim | Cần stakeholder interview, workflow observation và technical integration assessment |

Ví dụ, VinDr-CXR là một tín hiệu tốt rằng bối cảnh Việt Nam đã có tiền lệ xây
dữ liệu hồi cứu, gán nhãn bởi bác sĩ và đánh giá AI cho bài toán hình ảnh y tế.
Nhưng đây là bài toán chest X-ray, không phải free-text clinical summarization;
vì vậy chỉ nên dùng như bài học về cách làm validation, không dùng làm bằng
chứng cho hiệu quả của RAG/text summarization tại Vinmec.

Nói ngắn gọn: Vinmec có nhiều điều kiện nền để **đáng nghiên cứu**, nhưng chưa
có đủ bằng chứng công khai để bước qua governance gate. Đây không
phải điểm yếu của đề xuất; ngược lại, nó giúp định vị dự án đúng chuẩn nghiên
cứu ứng dụng: bắt đầu bằng câu hỏi kiểm chứng, không bắt đầu bằng tuyên bố sản
phẩm.

### 1.2 Hiện trạng ứng dụng có thể suy luận: bài toán chưa nên là “AI tóm tắt mọi hồ sơ”

Nếu áp dụng tại Vinmec, không nên định nghĩa bài toán là một công cụ tổng quát
“đưa mọi bệnh án vào rồi sinh tóm tắt”. Cách đó rủi ro vì mỗi khoa có cấu trúc
hồ sơ, ngôn ngữ, mức độ timeline, rủi ro thuốc và yêu cầu pháp lý khác nhau.
Nên chia bài toán thành các workflow nhỏ, có thể kiểm thử được:

| Workflow ứng viên | Giá trị kỳ vọng | Vì sao phù hợp/không phù hợp giai đoạn đầu |
| --- | --- | --- |
| Discharge handoff draft cho nội trú người lớn | Giúp bác sĩ tổng hợp diễn biến, chẩn đoán, thủ thuật, thuốc và follow-up | Phù hợp nhất để pilot vì có output rõ, có reference discharge summary và có reviewer chuyên môn |
| Pre-rounding / daily progress summary | Giúp bác sĩ nắm diễn biến 24–72 giờ gần nhất | Hữu ích nhưng đòi hỏi timeline và dữ liệu mới cập nhật liên tục; nên để sau khi retrieval/audit ổn |
| Longitudinal outpatient summary cho tái khám | Giúp bác sĩ xem nhanh lịch sử bệnh, thuốc, xét nghiệm và lần khám trước | Có giá trị cao nhưng khó vì dữ liệu trải qua nhiều encounter, nhiều template và có nguy cơ thiếu ngữ cảnh |
| Referral / transfer summary giữa cơ sở hoặc chuyên khoa | Giảm mất thông tin khi chuyển tuyến/chuyển khoa | Có giá trị chiến lược cho hệ thống nhiều cơ sở, nhưng cần chuẩn hóa patient identity và encounter semantics |
| Insurance/admin summary | Có thể tiết kiệm thời gian hành chính | Không nên là ưu tiên nghiên cứu lâm sàng đầu tiên nếu mục tiêu là evidence-first clinical quality |
| Patient-facing summary | Giúp người bệnh hiểu hồ sơ | Rủi ro diễn giải, health literacy và trách nhiệm pháp lý cao hơn; nên làm sau clinician-facing draft |

Khuyến nghị: **workflow đầu tiên nên là clinician-facing discharge handoff draft
cho một khoa nội trú người lớn**, vì nó cân bằng tốt giữa giá trị, khả năng đo
lường và rủi ro. Output phải luôn là **AI-generated draft**, có citation, có
unsupported-claim warning, có reviewer signature và không tự ghi vào hồ sơ chính
thức.

### 1.3 Bản đồ mở rộng từ PoC hiện tại sang Vinmec

PoC hiện tại chứng minh được một lõi kỹ thuật: retrieval theo patient/encounter,
citation-first summary, gate khi thiếu evidence, benchmark theo provider và
proxy metrics. Để mở rộng sang Vinmec, cần chuyển từ “model benchmark” sang
“clinical workflow evidence”.

| Lớp | PoC hiện tại đã có | Cần thêm để phù hợp Vinmec |
| --- | --- | --- |
| Data | Mock/de-identified benchmark records | Retrospective de-identified Vinmec dataset, data dictionary, section mapping, Vietnamese/mixed-language normalization |
| Retrieval | Patient/encounter-filtered RAG và Qdrant | Site/department/encounter boundary, terminology mapping, wrong-patient prevention tests, private deployment boundary |
| Generation | Multi-provider comparison, deterministic control | One frozen model/prompt/schema per study arm; no silent model drift; Vietnamese clinical style constraints |
| Safety | Unsupported-claim validation và retrieval gate | Clinical risk taxonomy, reviewer adjudication, critical-error stopping rules, incident workflow |
| Evaluation | ROUGE/BERTScore/citation/factuality/timeline proxy | Clinician review, edit distance/time, accept/edit/reject, citation usefulness, critical omission/commission |
| Deployment | Local staging PoC, Docker Compose | Research-only environment, read-only HIS/EMR extract, no writeback, RBAC, audit, retention, security review |
| Governance | Disclaimers and safety boundaries | Ethics/IRB, DPO/legal approval, DPIA/risk assessment, data processing agreement, publication rules |

Điểm chuyển hóa quan trọng là: tại Vinmec, metric chính không nên là “model nào
có ROUGE cao nhất”, mà là:

- bác sĩ có tiết kiệm thời gian review/tổng hợp không;
- critical omission/commission có tăng không;
- citation có thật sự giúp kiểm chứng claim không;
- hệ thống có biết dừng khi thiếu evidence không;
- draft có làm bác sĩ hiểu nhầm là kết luận đã xác nhận không;
- workflow có tái tạo và audit được không.

### 1.4 Khả năng mở rộng trong Vinmec: nên mở rộng theo vòng tròn đồng tâm

Nếu pilot đầu tiên đạt tiêu chí go/no-go, mở rộng nên đi theo vòng tròn đồng
tâm, không nhảy ngay sang toàn viện:

```text
Một khoa / một summary type
→ thêm một khoa cùng site
→ thêm một summary type cùng site
→ thêm một site thứ hai để đo site shift
→ chuẩn hóa cross-site governance và evaluation
→ chỉ sau đó mới cân nhắc platform hóa
```

Mỗi vòng mở rộng phải đóng băng lại evaluation plan, vì khi đổi khoa hoặc đổi
site thì bài toán có thể thay đổi mạnh:

- template ghi chép khác;
- cách dùng viết tắt khác;
- tỷ lệ tiếng Việt/Anh khác;
- độ dài encounter khác;
- mật độ thuốc, xét nghiệm, thủ thuật khác;
- chuẩn coding và problem list khác;
- mức độ trùng lặp hoặc thiếu dữ liệu khác;
- kỳ vọng bác sĩ với summary khác.

Do đó, “mở rộng được” không có nghĩa là chỉ scale hạ tầng. Mở rộng trong bệnh
viện là **scale bằng chứng**: mỗi domain mới phải chứng minh lại chất lượng,
safety, workflow fit và governance.

### 1.5 Các câu hỏi discovery cần hỏi Vinmec trước khi xin dữ liệu

Trước khi chạm vào dữ liệu thật, nhóm nghiên cứu cần một vòng discovery có cấu
trúc. Các câu hỏi này giúp biến đề xuất từ “ý tưởng AI” thành “protocol có thể
được hội đồng và IT xem xét”:

| Nhóm câu hỏi | Câu hỏi cần trả lời |
| --- | --- |
| Workflow | Bác sĩ đang mất thời gian nhất ở loại summary nào? Ai tạo, ai duyệt, ai dùng lại summary? |
| Data source | Note nằm ở HIS/EMR nào? Có RIS/PACS/LIS/pharmacy feed không? Dữ liệu structured và free-text tách nhau thế nào? |
| Identity boundary | Patient ID, encounter ID, visit ID, department ID và site ID được quản lý ra sao? Có master patient index không? |
| Vietnamese NLP | Tỷ lệ tiếng Việt, tiếng Anh, viết tắt, copy-forward, template, typo và mixed-language là bao nhiêu? |
| Safety | Lỗi nào là critical: sai thuốc, sai dị ứng, sai diagnosis, sai procedure, sai timeline, nhầm người bệnh? |
| Human review | Ai review draft? Review trong bao lâu? Có adjudication khi hai bác sĩ bất đồng không? |
| Integration | Giai đoạn nghiên cứu lấy dữ liệu bằng export/batch hay read-only API? Có tuyệt đối cấm writeback không? |
| Security | Môi trường chạy ở đâu? Ai có quyền truy cập? Log có chứa PHI không? Backup và retention thế nào? |
| Evaluation | Thành công được định nghĩa bằng thời gian, chất lượng, safety, satisfaction hay tất cả? |
| Governance | Cần ethics/IRB, legal/DPO, cybersecurity, medical records và patient safety phê duyệt theo thứ tự nào? |

Nếu chưa trả lời được các câu hỏi này, chưa nên demo với dữ liệu thật. Demo nên
tiếp tục dùng mock/de-identified data.

### 1.6 Kết luận nghiên cứu hiện trạng

Hiện trạng hợp lý nhất để trình bày với mentor là:

1. **Không tìm thấy công bố công khai về một hệ thống medical record
   summarization bằng LLM/RAG trong workflow HIS/EMR Vinmec.**
2. **Có cơ sở để đề xuất nghiên cứu tại Vinmec** vì hệ thống nhiều cơ sở, định
   hướng nghiên cứu/innovation và yêu cầu bảo vệ dữ liệu sức khỏe tạo ra cả nhu
   cầu lẫn điều kiện governance cho một pilot nghiêm túc.
3. **PoC hiện tại chưa phải sản phẩm triển khai**, nhưng là nền tốt cho research
   pilot vì đã có citation-first design, retrieval gate, benchmark theo provider,
   Docker/local staging và audit-oriented workflow.
4. **Mở rộng được**, nhưng nên mở rộng theo bằng chứng: retrospective
   de-identified study → controlled comparison → silent mode → clinician-visible
   pilot → external validation.
5. **Điểm khác biệt của đề xuất không phải “LLM tóm tắt hay hơn”**, mà là
   evidence-first summarization: draft có nguồn, có gate, có cảnh báo, có bác sĩ
   duyệt và có audit.

## 2. Vì sao bài toán tại bệnh viện khác benchmark hiện tại?

Benchmark hiện tại có source trung bình khoảng 500–600 tokens, thường chỉ tương
đương khoảng 2.000–2.500 ký tự tiếng Anh. Với một note ngắn như vậy, Raw có thể
đưa gần như toàn bộ thông tin vào model và đạt ROUGE tốt.

Một encounter thực tế có thể bao gồm:

- admission note;
- progress notes của nhiều ngày và nhiều chuyên khoa;
- chẩn đoán và problem list;
- thuốc đang dùng, thay đổi liều, thuốc dừng;
- dị ứng;
- xét nghiệm lặp theo thời gian;
- chẩn đoán hình ảnh;
- thủ thuật/phẫu thuật;
- consultation notes;
- nursing notes;
- discharge planning.

Giá trị của RAG chỉ xuất hiện rõ khi bài toán chuyển từ “tóm tắt một đoạn ngắn”
thành “tìm đúng evidence trong nhiều tài liệu, nhiều thời điểm và nhiều loại dữ
liệu”. Vì thế không được suy rộng trực tiếp kết quả 50 records hiện tại thành
hiệu quả tại Vinmec.

## 3. RAG trong nghiên cứu này là evidence-first

RAG không được chọn với giả định rằng nó luôn làm ROUGE cao hơn Raw. RAG được
chọn để tạo các thuộc tính mà workflow bác sĩ cần:

- mỗi claim quan trọng có thể truy ngược về source;
- retrieval bị giới hạn đúng patient, encounter và tenant;
- bác sĩ có thể mở đoạn bằng chứng thay vì đọc lại toàn bộ hồ sơ;
- missing evidence được biểu diễn là unknown, không bị diễn giải thành absent;
- unsupported hoặc conflicting claims luôn hiện để review;
- hệ thống có thể dừng thay vì ép model tạo nội dung khi thiếu evidence bắt buộc;
- mọi lần generate, edit, approve hoặc reject có thể audit.

Hai record bị retrieval gate chặn trong PoC minh họa đúng triết lý này: generic
Recall@5 vẫn cao nhưng không có evidence được phân loại vào `DIAGNOSIS`. Gate
chặn theo loại bằng chứng bắt buộc, không chỉ theo một similarity score tổng.

## 4. Không nên chọn Raw hoặc RAG theo kiểu nhị phân

Nghiên cứu tại Vinmec nên kiểm tra một **adaptive context strategy**:

| Tình huống | Context strategy đề xuất |
| --- | --- |
| Một note ngắn, nằm trọn context window | Full-note/Raw với citation extraction |
| Một encounter có vài note, cấu trúc rõ | Structured clinical context |
| Nhiều ngày, nhiều tài liệu hoặc vượt context window | Section-aware RAG |
| Thiếu diagnosis/medication/allergy evidence bắt buộc | Block hoặc review retrieval trước |
| Retrieval có xung đột | Hiển thị cả hai evidence, không tự giải quyết |
| Case có nguy cơ cao | Draft + enhanced clinician review |

Giả thuyết nghiên cứu phù hợp không phải “RAG thắng Raw”, mà là:

1. Raw có thể tốt hơn về lexical similarity trên note ngắn.
2. RAG có thể tốt hơn về citation, traceability và review efficiency trên hồ sơ
   dài, đa tài liệu.
3. Adaptive routing có thể giữ lợi thế của cả hai.

## 5. Vai trò của chunking, embedding và Qdrant

### 5.1 Pipeline

```text
HIS/EMR read-only extract
  → normalization
  → section-aware chunking
  → embedding từng chunk
  → private vector index
  → patient/encounter-filtered retrieval
  → evidence context
  → draft summary
  → claim/citation validation
  → clinician review
  → research metrics
```

Chunking tạo đơn vị bằng chứng và giữ source span. Embedding biểu diễn ý nghĩa
của từng chunk. Qdrant lưu vector và hỗ trợ tìm top-k chunk gần nghĩa với câu
hỏi, đồng thời lọc theo patient/encounter.

### 5.2 Ranh giới dữ liệu quan trọng

Embedding **không được mặc định là dữ liệu ẩn danh**. Vector có thể tiết lộ
thông tin qua membership/inversion attacks hoặc bị liên kết lại bằng metadata.
Trong implementation PoC hiện tại, Qdrant payload còn lưu cả:

- patient ID;
- encounter ID;
- document ID;
- section;
- raw chunk text;
- source offsets.

Do đó Qdrant hiện chứa dữ liệu lâm sàng nhạy cảm gần như một clinical data
store. Khi nghiên cứu tại Vinmec, cần một trong hai thiết kế:

1. Qdrant private/on-prem lưu vector và payload đã tối thiểu hóa; raw chunk nằm
   trong clinical data store được kiểm soát riêng; hoặc
2. Qdrant private lưu encrypted clinical payload trong cùng security boundary,
   với RBAC, TLS, encryption at rest, audit và retention policy.

Không đưa raw notes, chunks, embeddings hoặc Qdrant snapshots lên public cloud
hay dịch vụ LLM bên ngoài nếu chưa có phê duyệt pháp lý, bảo mật, hợp đồng xử lý
dữ liệu và đánh giá chuyển dữ liệu phù hợp.

## 6. Câu hỏi nghiên cứu

### RQ1 — Chất lượng summary

Evidence-first RAG, Raw và Structured Context khác nhau thế nào về factual
correctness, clinical completeness, critical errors và hallucination?

### RQ2 — Chất lượng evidence

Citation có thật sự hỗ trợ claim không, hay chỉ trỏ tới một đoạn có từ khóa gần
giống?

### RQ3 — Hiệu quả workflow

Draft có giảm thời gian đọc và chỉnh sửa của bác sĩ so với tạo summary từ đầu
không?

### RQ4 — Điều kiện RAG có lợi

Lợi ích thay đổi thế nào theo số tài liệu, độ dài encounter, số ngày điều trị,
số chuyên khoa, medication density và timeline complexity?

### RQ5 — Safety gate

Gate chặn được case thiếu evidence quan trọng tới đâu và tạo bao nhiêu false
blocks?

### RQ6 — Generalization

Kết quả có giữ được khi chuyển khoa, bệnh viện, template, ngôn ngữ và phong cách
ghi chép hay không?

## 7. Thiết kế nghiên cứu theo giai đoạn

### Phase 0 — Governance và workflow discovery

**Thời gian đề xuất:** 4–6 tuần.

Hoạt động:

- chỉ định clinical PI và technical PI;
- xác định data controller, processor, custodian và người chịu trách nhiệm an ninh;
- phỏng vấn bác sĩ, điều dưỡng, medical records, IT/HIS, pháp chế và an toàn người bệnh;
- chọn đúng một summary type;
- lập data-flow diagram và threat model;
- xác định legal basis/consent hoặc waiver phù hợp;
- nộp hội đồng đạo đức/nghiên cứu có thẩm quyền;
- thực hiện data protection impact/risk assessment theo yêu cầu hiện hành;
- định nghĩa incident response, access revocation, retention và deletion.

**Exit gate:** chưa cấp dữ liệu thật cho hệ thống nếu governance, protocol,
security boundary và trách nhiệm phê duyệt chưa được ký.

### Phase 1 — Retrospective de-identified feasibility

**Thời gian đề xuất:** 8–12 tuần.

Sử dụng dữ liệu hồi cứu đã giảm định danh trong môi trường nghiên cứu tách biệt.
Không kết nối writeback với HIS/EMR.

Ba tầng dữ liệu:

1. development set để sửa normalization, chunking và retrieval;
2. validation set để chọn policy/threshold;
3. locked test set chỉ mở khi thiết kế đã đóng băng.

Mẫu phải được stratify theo:

- short vs longitudinal encounter;
- số document;
- độ dài và số ngày điều trị;
- diagnosis/medication/timeline density;
- template và khoa;
- Vietnamese, English và mixed-language;
- missing, conflicting hoặc duplicated information.

**Không dùng discharge summary reference như gold tuyệt đối.** Summary hiện hữu
có thể thiếu hoặc lỗi. Nên dùng:

- clinician-authored discharge summary như weak reference;
- một tập nhỏ được hai bác sĩ review độc lập và adjudicate làm gold set.

### Phase 2 — Controlled offline comparison

**Thời gian đề xuất:** 6–8 tuần.

So sánh tối thiểu:

| Arm | Context |
| --- | --- |
| A | Raw/full encounter context khi vừa context window |
| B | Structured Context, không vector retrieval |
| C | Section-aware RAG |
| D | Adaptive Raw/Structured/RAG routing |

Để kết luận có ý nghĩa, cùng một generator phải dùng:

- cùng model version;
- cùng prompt nhiệm vụ;
- cùng decoding;
- cùng output schema;
- cùng test records.

Chỉ thay context-construction strategy. Đây là điểm mà benchmark lịch sử hiện
tại chưa kiểm soát hoàn toàn, nên không được gọi nó là causal ablation.

### Phase 3 — Prospective silent/shadow mode

**Thời gian đề xuất:** 8–12 tuần.

Hệ thống chạy song song với workflow thật nhưng:

- output không hiển thị cho nhóm điều trị trước khi documentation hoàn tất;
- không tác động quyết định chăm sóc;
- không ghi vào EMR;
- không dùng để đánh giá hiệu suất cá nhân;
- chỉ đối chiếu sau sự kiện bởi reviewer được phân quyền.

Mục tiêu là phát hiện:

- template drift;
- latency thực;
- lỗi mapping encounter;
- wrong-patient retrieval;
- missing data source;
- khác biệt theo ca trực/khoa;
- failure chưa xuất hiện trong dữ liệu hồi cứu.

**Stopping rule:** bất kỳ wrong-patient retrieval hoặc critical medication,
allergy, diagnosis hay procedure error nào cũng phải kích hoạt incident review
và tạm dừng arm liên quan cho đến khi có quyết định của safety owner.

### Phase 4 — Clinician-in-the-loop usability pilot

Chỉ bắt đầu sau khi Phase 3 đạt safety gate.

Output được hiển thị là:

```text
AI-generated draft — clinician review required
```

Bác sĩ phải có khả năng:

- mở citation tại source span;
- thấy unsupported/conflicting evidence;
- edit;
- approve, reject hoặc request regeneration;
- ghi lý do reject;
- ký/xác nhận theo cơ chế hiện hữu của Vinmec.

Trong giai đoạn đầu, không cho autonomous writeback. Nếu cần đưa nội dung vào
EMR, chỉ thực hiện qua thao tác chủ động của bác sĩ và audit đầy đủ sau khi được
phê duyệt.

### Phase 5 — Multi-site external validation

Không mở rộng toàn hệ thống ngay sau pilot. Chuyển model/policy đã khóa sang một
cơ sở khác và đo lại:

- retrieval;
- citation support;
- critical error;
- edit time;
- reject rate;
- latency;
- workflow fit.

Không fine-tune trên site thứ hai trước lần external validation đầu tiên, nếu
mục tiêu là đo khả năng generalize.

## 8. Outcome measures

### 8.1 Primary outcomes

- critical clinical error rate do reviewer thật xác định;
- factual correctness;
- clinical completeness;
- clinician edit time;
- approve/edit/reject rate.

### 8.2 Evidence outcomes

- claim-level citation precision;
- claim-level citation recall;
- unsupported claim rate;
- contradiction rate;
- wrong-patient retrieval count;
- section-specific retrieval recall;
- retrieval gate false-block và missed-block rate.

### 8.3 Workflow outcomes

- thời gian từ mở encounter đến draft được xác nhận;
- số lần mở source evidence;
- số thao tác edit;
- user trust/calibration;
- lý do reject;
- tỷ lệ fallback sang manual workflow.

### 8.4 Operational outcomes

- latency p50/p95;
- index freshness;
- missing-document rate;
- queue failure;
- resource usage;
- audit completeness;
- access-control violations.

ROUGE và BERTScore chỉ là secondary technical metrics. Chúng không được dùng
thay cho critical errors, citation support hoặc clinician effort.

## 9. Annotation và reviewer design

Mỗi case trong locked evaluation set nên có:

- ít nhất hai reviewer độc lập;
- reviewer role và specialty;
- blinded context arm;
- adjudication cho disagreement;
- critical-error taxonomy;
- edit diff và actual edit time;
- citation-by-citation support decision.

Phân tích:

- paired comparison trên cùng encounter;
- confidence intervals bằng bootstrap;
- mixed-effects model nếu có đủ dữ liệu, với reviewer/site/specialty là random
  hoặc fixed effects phù hợp;
- weighted kappa hoặc agreement rate;
- subgroup analysis được định nghĩa trước, không chọn sau khi nhìn kết quả.

Sample size cuối cùng phải do statistician tính từ primary endpoint và effect
size tối thiểu có ý nghĩa, không lấy một con số tiện lợi từ benchmark PoC.

## 10. Kiến trúc nghiên cứu đề xuất

```text
Vinmec HIS/EMR
  │ read-only, allow-listed
  ▼
Research data gateway
  ├── pseudonymization/tokenization
  ├── field allow-list
  ├── encounter scope
  └── immutable access audit
  ▼
Private research environment
  ├── normalization/chunking
  ├── protected clinical text store
  ├── private Qdrant/vector index
  ├── local/approved embedding model
  ├── local/approved generation model
  ├── citation/guardrail service
  └── encrypted metrics store
  ▼
Research reviewer UI
  ├── draft label
  ├── source evidence
  ├── unsupported/conflict warning
  └── approve/edit/reject
```

Nguyên tắc:

- read-only integration trước;
- network segmentation;
- least privilege;
- service identity, không dùng shared admin account;
- encryption in transit/at rest;
- secret management;
- immutable audit;
- no raw-note application logging;
- backup/restore test;
- environment separation;
- model/artifact version pinning;
- no internet egress từ clinical processing zone trừ allow-list được phê duyệt.

## 11. Những thay đổi kỹ thuật cần làm trước Vinmec

### P0 — Bắt buộc

- hỗ trợ tiếng Việt và mixed-language trong normalization, section detection,
  abbreviation và embedding evaluation;
- patient/encounter scoping được test bằng negative tests;
- tách raw clinical text khỏi vector payload hoặc bảo vệ Qdrant như PHI store;
- read-only connector contract;
- immutable audit và role mapping với identity provider;
- data retention/deletion jobs;
- reproducible model/prompt/index manifests;
- disaster recovery và incident response;
- security review, penetration test và dependency scanning.

### P1 — Giá trị nghiên cứu

- hybrid retrieval: vector + lexical;
- section-specific queries và top-k;
- reranker;
- adaptive full-context/RAG routing;
- citation entailment/contradiction;
- temporal normalization;
- structured medication, allergy, lab và procedure evidence;
- uncertainty và refusal reason rõ cho bác sĩ.

### P2 — Chỉ sau khi có human evidence

- prompt/model tuning từ reviewer feedback;
- specialty adaptation;
- multi-site calibration;
- prospective workflow optimization;
- controlled EMR integration.

## 12. Governance tại Vinmec

Vinmec công bố hồ sơ sức khỏe và đời tư trong medical records là sensitive
personal data. Chính sách của Vinmec cũng mô tả yêu cầu mục đích xử lý cụ thể,
biện pháp bảo mật, lưu trữ phù hợp, quyền của chủ thể dữ liệu và kiểm soát chia
sẻ/chuyển dữ liệu. Nghị định 13/2023/NĐ-CP có hiệu lực từ ngày 1/7/2023 là một
mốc pháp lý nền tảng về bảo vệ dữ liệu cá nhân.

Tuy nhiên, đây không phải ý kiến pháp lý. Trước khi bắt đầu nghiên cứu vào năm
2026 hoặc sau đó, pháp chế/DPO của Vinmec phải xác nhận toàn bộ luật, nghị định,
thông tư, hướng dẫn Bộ Y tế, quy định nghiên cứu và yêu cầu chuyển dữ liệu đang
có hiệu lực tại thời điểm triển khai.

Các hồ sơ governance tối thiểu:

- research protocol;
- ethics/IRB approval hoặc quyết định waiver phù hợp;
- data processing impact/risk assessment;
- data management plan;
- data sharing/processing agreement;
- consent/waiver rationale;
- access-control matrix;
- retention/deletion schedule;
- incident and breach response plan;
- publication and model-release policy;
- statement cấm tái định danh.

## 13. Tổ chức đội dự án

| Vai trò | Trách nhiệm |
| --- | --- |
| Clinical PI | Chịu trách nhiệm clinical question, workflow và safety escalation |
| Technical PI | Thiết kế NLP/RAG, reproducibility và technical risk |
| Clinical informatics lead | Mapping HIS/EMR, terminology, encounter semantics |
| Data custodian | Phê duyệt dataset, access và retention |
| Privacy/legal/DPO | Legal basis, data subject rights, transfer và contracts |
| Cybersecurity | Threat model, segmentation, monitoring, incident response |
| Statistician | Sample size, analysis plan và uncertainty |
| Clinician reviewers | Annotation, adjudication và usability evaluation |
| Patient safety/quality | Critical-error taxonomy và stopping rules |
| MLOps/research engineer | Versioning, monitoring, reproducible artifacts |

## 14. Lộ trình 9–12 tháng đề xuất

| Tháng | Kết quả |
| --- | --- |
| 1–2 | Workflow discovery, governance, ethics/security submissions |
| 2–4 | De-identified dataset, Vietnamese normalization, baseline reproduction |
| 4–6 | Controlled Raw/Context/RAG/Adaptive study |
| 6–8 | Locked human evaluation và safety case |
| 8–10 | Prospective silent mode |
| 10–12 | Clinician-in-loop pilot nếu tất cả exit gates đạt |

Timeline có thể dài hơn nếu data access, ethics, HIS integration hoặc security
review chưa hoàn tất. Không được rút ngắn bằng cách bỏ governance gate.

## 15. Go/no-go criteria

### Go sang shadow mode khi

- không có cross-patient retrieval trong locked test;
- audit và access control đã được kiểm thử;
- critical errors đã được review và có mitigation;
- retrieval/citation failure có thể giải thích;
- protocol và governance được phê duyệt.

### Go sang clinician-visible pilot khi

- shadow-mode safety review đạt;
- UI hiển thị draft/citation/warning rõ ràng;
- bác sĩ có quyền reject/fallback;
- latency và availability phù hợp workflow;
- incident response đã diễn tập.

### No-go hoặc pause khi

- wrong-patient evidence;
- không tái tạo được model/index/prompt version;
- raw PHI xuất hiện trong log hoặc môi trường không được phê duyệt;
- critical error không có root-cause/mitigation;
- người dùng hiểu nhầm draft là kết luận đã xác nhận;
- hệ thống gây trì hoãn hoặc làm mất dữ liệu lâm sàng.

## 16. Kết luận

Đề xuất phù hợp cho Vinmec không phải “triển khai RAG toàn viện”, mà là:

```text
Một site
→ một workflow
→ retrospective de-identified study
→ controlled Raw vs Context vs RAG vs Adaptive comparison
→ human evaluation
→ silent mode
→ clinician-visible pilot
→ external validation
```

Thành công không được định nghĩa bằng ROUGE cao nhất. Thành công là chứng minh,
trên dữ liệu và workflow Vinmec được quản trị đúng, rằng bác sĩ có thể tạo hoặc
kiểm tra summary nhanh hơn trong khi claim vẫn truy vết được, critical errors
không tăng và quyền quyết định cuối cùng luôn thuộc về bác sĩ.

## 17. Nguồn công khai dùng để định hướng

- [Vinmec — Vision and Mission](https://www.vinmec.com/eng/vision-and-mission/)
- [Vinmec — Hospitals and Clinics Directory](https://www.vinmec.com/eng/hospital/)
- [Vinmec — Personal Data Protection Policy](https://www.vinmec.com/eng/blog/personal-data-protection-policy-of-vinmec-international-general-hospital-joint-stock-company)
- [Vinmec — Research Institute of Stem Cell and Gene Technology](https://www.vinmec.com/eng/specialties/vinmec-research-institute-of-stem-cell-and-gene-technology)
- [VinDr-CXR — Open chest X-ray dataset with radiologist annotations](https://arxiv.org/abs/2012.15029)
- [Cổng Thông tin điện tử Chính phủ — Nghị định 13/2023/NĐ-CP](https://vanban.chinhphu.vn/?docid=207759&pageid=27160)
