# Final Research Conclusion — Citation-grounded Medical Record Summarization

> **Scope:** kết luận nghiên cứu cho PoC hiện tại và hướng mở rộng pilot. Đây
> không phải bằng chứng an toàn/hiệu quả lâm sàng, không phải xác nhận triển
> khai tại bệnh viện thật và không phải tài liệu phê duyệt HIS/EMR integration.

> **Ghi chú nộp bài:** kết luận này đã được tích hợp vào
> [VINMEC_MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md](VINMEC_MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md).
> Nếu chỉ nộp một proposal Vinmec, hãy nộp file proposal tổng hợp đó.

## 1. Luận điểm cuối cùng

Dự án này nên được định vị là một **evidence-first clinical summarization PoC**,
không phải một chatbot tóm tắt bệnh án tổng quát.

Điểm mạnh nhất của hệ thống không nằm ở việc sinh văn bản “nghe hay”, mà ở việc
đưa clinical summarization vào một workflow có kiểm soát:

- summary là AI-generated draft;
- claim quan trọng có citation;
- retrieval bị giới hạn theo patient/encounter;
- thiếu bằng chứng thì gate có thể block hoặc cảnh báo;
- bác sĩ là người review và quyết định cuối cùng;
- output, evidence, reviewer action và phiên bản hệ thống có thể audit.

Đây là framing đúng cho một bài toán y tế: không tối đa hóa impression, mà tối
đa hóa khả năng kiểm tra, truy vết và giảm rủi ro hiểu nhầm.

## 2. PoC hiện tại đã chứng minh gì?

PoC đã chứng minh ở mức local staging/research prototype rằng:

1. Có thể chạy end-to-end flow từ retrieval, generation, citation validation,
   doctor review boundary đến admin evaluation.
2. Có thể benchmark nhiều provider trên cùng một bộ records và tách rõ no-gate
   run với gated run.
3. Có thể đo không chỉ ROUGE/BERTScore mà còn citation coverage, factuality
   proxy, timeline proxy, hallucinated entities và critical omission proxy.
4. Có thể tạo human-review package có blinding và blank score sheet mà không
   giả lập điểm đánh giá con người.
5. Có thể dùng retrieval gate để dừng generation khi thiếu evidence bắt buộc,
   thay vì ép model tạo nội dung không được hỗ trợ.
6. Có thể đóng gói demo evidence, Docker/local staging và report theo hướng có
   reproducibility.

Điều này đủ mạnh cho final PoC/demo và đủ nghiêm túc để đề xuất research pilot.

## 3. PoC chưa chứng minh gì?

Các ranh giới này phải được giữ rõ:

- chưa chứng minh an toàn lâm sàng;
- chưa chứng minh hiệu quả lâm sàng;
- chưa chứng minh giảm thời gian bác sĩ trong workflow thật;
- chưa chứng minh trên real EHR/Vinmec data;
- chưa chứng minh hệ thống phù hợp mọi khoa hoặc mọi site;
- chưa cho phép autonomous clinical decision;
- chưa cho phép HIS/EMR writeback.

Đây không phải điểm yếu nếu được trình bày đúng. Nó cho thấy nhóm biết phân biệt
giữa **proxy evaluation**, **human validation**, **silent mode** và **clinical
deployment**.

## 4. Ý nghĩa của benchmark

Benchmark hiện tại nên được đọc như một nghiên cứu PoC có discipline:

- Deterministic là smoke/control provider đáng tin cậy.
- Qwen2.5 và Llama3.2 mạnh hơn BART/Pegasus trong hướng citation-first doctor
  workflow.
- BART/Pegasus vẫn hữu ích làm baseline, nhưng yếu hơn khi cần citation và giảm
  omission.
- Raw có thể có ROUGE cao hơn trên note ngắn vì input chỉ khoảng 500–600 tokens.
- RAG không được chọn để luôn tăng ROUGE; RAG được chọn để hỗ trợ evidence
  traceability, patient isolation, citation review và safe refusal.

Kết luận đúng không phải “RAG luôn tốt hơn Raw”. Kết luận đúng là:

> Raw phù hợp note ngắn. Structured context phù hợp hồ sơ vừa. Section-aware RAG
> phù hợp hồ sơ dài, nhiều tài liệu và cần evidence review. Hướng tốt nhất cho
> bệnh viện là adaptive evidence-first routing.

## 5. Vì sao hướng Vinmec nên là pilot nghiên cứu?

Vinmec là bối cảnh đáng đề xuất vì thông tin công khai cho thấy đây là hệ thống
bệnh viện nhiều cơ sở, có định hướng academic healthcare/research/innovation và
có chính sách bảo vệ dữ liệu cá nhân trong đó dữ liệu sức khỏe là nhạy cảm.

Nhưng chính vì bối cảnh này nghiêm túc, bước tiếp theo không nên là deploy public
hoặc tuyên bố production. Bước tiếp theo nên là:

```text
governance discovery
→ retrospective de-identified study
→ controlled Raw/Structured/RAG/Adaptive comparison
→ clinician human evaluation
→ silent/shadow mode
→ clinician-visible usability pilot
→ external validation
```

Nếu đi thẳng từ PoC sang triển khai, dự án sẽ yếu về governance. Nếu đi qua
pilot nghiên cứu, dự án có cơ hội trở thành một case study có chiều sâu thật.

## 6. P0/P1/P2 recommendation

### P0 — Freeze and package

- Freeze major features before final demonstration.
- Package demo evidence, benchmark result, gate case study and human-review
  protocol.
- Keep public deployment optional, not required.
- Prepare Vinmec pilot proposal with governance, data-flow and risk register.

### P1 — Human validation and pilot readiness

- Invite qualified reviewers to score blinded outputs.
- Analyze accept/edit/reject, critical omission/commission and citation support.
- Convert reviewer feedback into a safety case.
- Finalize retrospective de-identified pilot protocol.

### P2 — Research expansion, not feature sprawl

- Study adaptive Raw/Structured/RAG routing.
- Improve Vietnamese/mixed-language normalization and section-aware chunking.
- Add stronger claim-citation validation only after human error patterns are
  known.
- Plan silent mode only after P1 human validation and governance gates.

## 7. Final wording for presentation

The cleanest final presentation message is:

> We built a demo-ready local staging PoC for citation-grounded medical record
> summarization. The PoC does not claim hospital-grade validation or live EHR use.
> Its contribution is an evidence-first workflow: AI drafts, citation support,
> retrieval gate, doctor review, auditability and disciplined evaluation. The
> right next step is a governed research pilot, not an official live rollout.

Vietnamese version:

> Dự án đã đạt mức PoC local staging có thể demo end-to-end cho bài toán tóm tắt
> hồ sơ bệnh án có citation. Hệ thống không tuyên bố an toàn/hiệu quả lâm sàng
> và chưa validation trên EHR thật. Giá trị chính là workflow evidence-first:
> AI chỉ tạo bản nháp, claim có nguồn, retrieval có gate, bác sĩ duyệt cuối cùng
> và toàn bộ quá trình có thể audit. Bước tiếp theo đúng là pilot nghiên cứu có
> governance, không phải triển khai production.

## 8. Final conclusion

Nếu mentor hỏi “dự án này tốt ở đâu?”, câu trả lời nên là:

> Dự án không chỉ benchmark model. Dự án xây một khuôn khổ clinical NLP an toàn
> hơn: đo provider, kiểm tra citation, phân tích failure, tách proxy metric khỏi
> human validation, giữ bác sĩ trong vòng kiểm soát và thiết kế đường đi thực tế
> từ PoC sang research pilot.

Đó là điểm làm project trưởng thành: biết mình đã chứng minh gì, biết mình chưa
chứng minh gì, và biết bước tiếp theo phải đi qua bằng chứng nào.
