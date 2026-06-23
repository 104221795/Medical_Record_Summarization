# Giao thức đánh giá con người cho Week 5

> Phạm vi: đánh giá PoC trên dữ liệu mô phỏng/đã khử định danh. Kết quả không
> chứng minh an toàn lâm sàng, hiệu quả lâm sàng hoặc hiệu năng trên EHR thực.
> Mọi bản tóm tắt do AI tạo vẫn là bản nháp và phải được bác sĩ có thẩm quyền
> kiểm tra trước khi sử dụng.

## 1. Mục tiêu

Giao thức này bổ sung đánh giá con người cho các chỉ số tự động của Flow 2.1.
Nó tập trung vào câu hỏi thực tế: đầu ra nào đúng, đủ, dễ kiểm tra bằng citation
và cần ít chỉnh sửa hơn trong quy trình bác sĩ?

Gói đánh giá đã được tạo tại:

```text
artifacts/evaluation/week5_analysis/
  human_review_cases.jsonl
  human_review_scores.csv
  human_review_blinding_key.csv
  human_review_sample_manifest.json
```

Mẫu có 12 hồ sơ và bao gồm cả hai trường hợp bị retrieval gate chặn:
`multiclinsum_ls_en_10012` và `multiclinsum_ls_en_10018`.

## 2. Vai trò người đánh giá

| Vai trò | Được đánh giá | Không được suy diễn |
| --- | --- | --- |
| Bác sĩ/nhân sự lâm sàng đủ chuyên môn | Tính đúng sự kiện, thiếu thông tin quan trọng, nguy cơ hallucination, quyết định approve/edit/reject | Không suy rộng 12 hồ sơ thành clinical validation |
| Chuyên gia health IT/clinical informatics | Citation usefulness, khả năng truy vết, workflow fit, readability | Không thay thế đánh giá chuyên môn lâm sàng |
| Người đánh giá phi lâm sàng | Readability, conciseness, lỗi trình bày rõ ràng | Không chấm factual correctness hoặc clinical completeness như kết luận lâm sàng |

Khuyến nghị tối thiểu là hai người đánh giá độc lập cho mỗi case, trong đó có
ít nhất một người có chuyên môn lâm sàng. Nếu nguồn lực chỉ có một người, báo
cáo phải ghi rõ đây là đánh giá đơn reviewer và không báo inter-rater agreement.

## 3. Thiết kế mù

- `human_review_cases.jsonl` chỉ hiển thị `output_id`; không hiển thị provider.
- Không mở `human_review_blinding_key.csv` trước khi khóa điểm.
- Người vận hành giữ blinding key riêng và chỉ giải mù sau khi tất cả score
  sheets đã được nộp.
- Mỗi reviewer dùng một `reviewer_id` giả danh và ghi đúng `reviewer_role`.
- Không thay đổi output, citation hoặc source note trong quá trình đánh giá.

## 4. Quy trình hai lượt

### Lượt A — evidence-first

1. Đọc source note và output có citation.
2. Kiểm tra từng claim quan trọng có evidence phù hợp hay không.
3. Chấm factual correctness, citation usefulness, hallucination risk và
   critical error.
4. Ghi rõ claim thiếu citation, citation sai ngữ cảnh hoặc xung đột bằng chứng.

### Lượt B — workflow-first

1. Đọc reference summary sau khi hoàn tất lượt A.
2. Chấm clinical completeness, readability và conciseness.
3. Chọn `approve`, `edit` hoặc `reject`.
4. Ước lượng số phút chỉnh sửa cần thiết.

Thứ tự này giảm nguy cơ reviewer chỉ đo mức giống reference thay vì kiểm tra
grounding với hồ sơ nguồn.

## 5. Rubric

| Trường | Quy ước |
| --- | --- |
| `factual_correctness_1_to_5` | 1: có sai lệch nghiêm trọng; 3: phần lớn đúng nhưng có lỗi; 5: không phát hiện sai lệch quan trọng |
| `clinical_completeness_1_to_5` | 1: thiếu phần lớn thông tin quan trọng; 3: còn thiếu đáng kể; 5: bao phủ đầy đủ cho mục đích review |
| `citation_usefulness_1_to_5` | 1: citation không dùng được; 3: truy vết được một phần; 5: citation hỗ trợ rõ các claim quan trọng |
| `readability_1_to_5` | 1: khó hiểu; 3: dùng được sau chỉnh sửa; 5: rõ ràng, có cấu trúc |
| `conciseness_1_to_5` | 1: quá dài/lặp hoặc quá ngắn; 3: còn dư/thiếu; 5: cô đọng phù hợp |
| `hallucination_risk_low_medium_high` | Mức rủi ro quan sát được từ claim không có căn cứ hoặc sai nguồn |
| `decision_approve_edit_reject` | Approve: có thể dùng làm draft sau review; Edit: cần sửa; Reject: nên tạo lại/không dùng |
| `estimated_edit_minutes` | Thời gian reviewer ước lượng để đạt draft chấp nhận được |
| `critical_error_present_yes_no` | Yes nếu lỗi có thể làm sai chẩn đoán, thuốc, dị ứng, thủ thuật, thời gian hoặc trạng thái quan trọng |

Điểm 5 không có nghĩa là hệ thống đã an toàn lâm sàng. Nó chỉ có nghĩa reviewer
không phát hiện vấn đề theo rubric trong mẫu PoC đang xem.

## 6. Kiểm soát chất lượng

- Reviewer hoàn thành độc lập trước khi thảo luận bất đồng.
- Trường bắt buộc không được để trống.
- Nếu chọn `critical_error_present=yes`, comments phải mô tả lỗi và evidence.
- Nếu chọn `reject`, comments phải nêu lý do chính.
- Người vận hành kiểm tra duplicate rows, output bị thiếu và giá trị ngoài miền.
- Không dùng AI để tự điền score sheet hoặc đóng vai reviewer lâm sàng.

## 7. Kế hoạch phân tích

Sau khi khóa điểm và giải mù:

1. Báo median và IQR cho các thang 1–5 theo provider.
2. Báo tỷ lệ approve/edit/reject, critical error và hallucination risk.
3. Báo median edit minutes; không gọi textual reference distance là edit time.
4. So sánh kết quả theo case và theo difficulty stratum, tránh chỉ báo trung bình.
5. Nếu có ít nhất hai reviewer độc lập, báo weighted Cohen's kappa cho biến
   thứ bậc hoặc agreement rate cho biến phân loại; ghi rõ cỡ mẫu.
6. Đối chiếu điểm người đánh giá với ROUGE-L, BERTScore, citation coverage,
   omission và hallucination proxy như phân tích khám phá, không kết luận nhân quả.

## 8. Tiêu chí hoàn tất

Human evaluation chỉ được ghi là “đã hoàn tất” khi:

- score sheet có reviewer thật và vai trò rõ ràng;
- toàn bộ case/output được chấm;
- bất đồng và critical errors đã được adjudicate;
- blinding key chỉ được mở sau khi khóa điểm;
- báo cáo giữ nguyên disclaimer và cỡ mẫu;
- không có dữ liệu nhận dạng hoặc thông tin bí mật trong gói chia sẻ.

Hiện tại trạng thái đúng là: **protocol và blinded review package đã sẵn sàng;
điểm reviewer thật đang chờ thực hiện**.
