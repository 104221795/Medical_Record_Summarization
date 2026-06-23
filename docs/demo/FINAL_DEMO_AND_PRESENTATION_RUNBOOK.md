# Runbook demo và thuyết trình cuối kỳ

> Thông điệp mở đầu: đây là demo-ready local staging PoC trên dữ liệu
> mock/đã khử định danh. AI tạo bản nháp để bác sĩ review; benchmark là proxy
> evaluation, không phải clinical validation.

## 1. Mục tiêu buổi demo

Trong 12–15 phút, reviewer cần nhìn thấy bốn điều:

1. hệ thống chạy lặp lại được bằng Docker Compose;
2. doctor workflow giữ citation, review và audit boundary;
3. Admin Flow 2.1 so sánh đủ 50 records x 5 providers, có BERTScore;
4. retrieval gate biết từ chối khi thiếu loại evidence bắt buộc.

Không dành thời gian demo public cloud, thêm model mới hoặc tính năng lớn.

## 2. Kịch bản demo 12–15 phút

| Thời lượng | Màn hình | Nội dung nói |
| --- | --- | --- |
| 0:00–0:45 | Slide phạm vi | PoC, dữ liệu de-identified, draft-only, clinician-review-only |
| 0:45–1:30 | `/health`, `/ready` | HTTP 200; giải thích vector-store warning là cấu hình local dự kiến |
| 1:30–2:30 | Kiến trúc | Doctor/Admin → FastAPI → RAG/evidence → provider → citation/review/audit |
| 2:30–6:00 | Doctor flow | Chọn patient/encounter, tạo draft, mở evidence, kiểm tra unsupported/conflict, edit và review |
| 6:00–7:00 | Audit | Chỉ ra action, reviewer/signature boundary và dữ liệu audit không chứa secret |
| 7:00–9:30 | Admin Flow 2.1 | Năm provider, 50/50 no-gate, 250/250 outputs, BERTScore, Qwen2.5 vs deterministic |
| 9:30–11:00 | Gate case | Hai record bị block vì thiếu diagnosis evidence dù Recall@5 cao |
| 11:00–12:30 | P1/P2 | Diversity strata, failure taxonomy, metric disagreement, threshold sensitivity |
| 12:30–13:30 | Human evaluation | Gói 12 case đã blind; điểm thật chưa được giả lập |
| 13:30–15:00 | Kết luận | Local Compose là staging path đã validate; cloud là optional; nêu giới hạn |

Nếu thời gian chỉ có 10 phút, bỏ chi tiết correlation table và chỉ giữ ba câu
chuyện: doctor workflow, provider comparison, retrieval refusal.

## 3. Storyboard slide

1. **Problem & safety boundary** — giảm tải đọc hồ sơ, không thay quyết định bác sĩ.
2. **End-to-end architecture** — patient scope, retrieval, generation, citations,
   review, audit.
3. **Validated local staging** — 172 full-suite tests và 37 lightweight tests,
   frontend build, Docker build, Compose topology, health/ready đều pass ngày
   2026-06-22.
4. **Doctor workflow** — draft → evidence → edit → approve/reject.
5. **Evaluation discipline** — tách Flow 1, 1.5, 2, 2.1 và tách gated/no-gate.
6. **Flow 2.1 provider results** — Qwen2.5 mạnh nhất trong nhóm generative;
   deterministic là smoke/control ổn định.
7. **Why BERTScore is not enough** — semantic similarity không thay citation,
   omission và hallucination proxies.
8. **Retrieval gate case** — 2/50 block có chủ đích, section-aware.
9. **Data diversity & failure modes** — easy/medium/hard gần cân bằng và lỗi theo provider.
10. **Human review package** — blind, rubric, reviewer roles, không giả điểm.
11. **What is complete / what remains** — automated evidence hoàn tất; screenshot,
    video, SharePoint và reviewer thật là thao tác con người.
12. **Decision** — freeze feature, record demo, package evidence, chỉ deploy cloud
    nếu tài nguyên xuất hiện.

## 4. Evidence phải mở sẵn

```text
artifacts/demo_evidence/2026-06-22/EVIDENCE_SUMMARY.md
artifacts/evaluation/week5_analysis/WEEK5_P1_P2_ANALYSIS.md
docs/evaluation/RETRIEVAL_GATE_CASE_STUDY.md
docs/evaluation/HUMAN_EVALUATION_PROTOCOL.md
docs/demo/LOCAL_DOCKER_COMPOSE_DEMO_CHECKLIST.md
```

Mở trước browser tabs cho frontend, `/health`, `/ready`, API docs và Admin
Evaluation. Không mở `.env`, access token, password hoặc raw credentialed data.

## 5. Câu trả lời ngắn cho mentor

**Tại sao 48/50 ở gated run nhưng 50/50 ở report khác?**  
Gated run đánh giá đủ 50 record nhưng chỉ generate 48 vì 2 record bị policy
gate chặn. No-gate run generate đủ 50 record cho mỗi provider để so sánh model.

**Tại sao cần BERTScore nếu đã có ROUGE?**  
BERTScore đo gần nghĩa hơn lexical overlap, nhưng vẫn không đo citation
grounding hoặc clinical correctness. Vì vậy report giữ cả BERTScore và các
grounding/risk proxies.

**Provider nào tốt nhất?**  
Qwen2.5 là generative provider mạnh nhất trong proxy run hiện tại.
Deterministic phù hợp nhất cho smoke/control. Chưa có cơ sở để gọi provider nào
là clinically best.

**Tại sao không deploy Render/Railway?**  
Local Docker Compose đã là staging path được kiểm chứng và đủ cho final demo.
Public cloud là optional khi có credit/tài nguyên; deployment không làm tăng
giá trị clinical evidence.

**P1/P2 đã hoàn tất chưa?**  
Automated post-hoc analysis, gate study, threshold sensitivity và blinded human
review package đã hoàn tất. Điểm human/clinician thật vẫn phải do reviewer thật
thực hiện.

## 6. Checklist ghi hình

- [ ] Dùng dữ liệu mock/đã khử định danh.
- [ ] Ẩn desktop notification và secrets.
- [ ] Nói disclaimer trong 30 giây đầu.
- [ ] Hiển thị `/health` và `/ready`.
- [ ] Hoàn thành doctor review flow, không dừng ở generation.
- [ ] Hiển thị citation và audit trail.
- [ ] Hiển thị đủ năm provider và BERTScore.
- [ ] Giải thích rõ gated và no-gate là hai run riêng.
- [ ] Kết thúc bằng limitations và next action.
- [ ] Kiểm tra lại video không chứa PHI/password trước khi chia sẻ.

## 7. Tiêu chí buổi demo đạt

Demo đạt khi một reviewer mới có thể trả lời đúng: hệ thống giải quyết vấn đề
gì, evidence được gắn ở đâu, bác sĩ kiểm soát ở đâu, vì sao có 48/50 và 50/50,
provider trade-off là gì, và điều gì chưa được chứng minh.
