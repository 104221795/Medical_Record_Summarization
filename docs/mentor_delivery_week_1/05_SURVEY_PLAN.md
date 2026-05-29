# 05 — Survey Plan: Problem Validation and Workflow Feedback

**Loại tài liệu:** Kế hoạch khảo sát
**Mục đích:** Xác thực nhu cầu người dùng, yêu cầu về niềm tin và các giả định workflow cho hệ thống Medical Record Summarization MVP

---

## 1. Mục tiêu khảo sát

Mục tiêu của khảo sát là xác thực xem các nhóm người dùng liên quan đến lĩnh vực y tế có gặp khó khăn khi review hồ sơ bệnh nhân dài hoặc phân tán hay không, đồng thời đánh giá liệu một hệ thống AI-generated summary có citation và human review có hữu ích, đáng tin cậy và phù hợp với workflow thực tế hay không.

Khảo sát này **không nhằm mục đích clinical validation**. Đây là khảo sát phục vụ **product discovery** và **problem validation** ở giai đoạn đầu của MVP.

Cụ thể, khảo sát giúp trả lời các câu hỏi:

* Người dùng có thực sự cảm thấy việc review hồ sơ bệnh nhân dài là tốn thời gian không?
* Người dùng có cần citation để tin tưởng một AI-generated medical summary không?
* Người dùng có kỳ vọng summary do AI tạo ra phải được bác sĩ kiểm duyệt trước khi sử dụng chính thức không?
* Các safety warnings như unsupported claim, weak citation hoặc missing information có làm tăng độ tin cậy của hệ thống không?
* Role-based access có cần thiết trong một hệ thống tóm tắt bệnh án không?

---

## 2. Nhóm người tham gia khảo sát

| Nhóm respondent                             | Số lượng mục tiêu | Mục đích                                                |
| ------------------------------------------- | ----------------: | ------------------------------------------------------- |
| Sinh viên y khoa / sinh viên ngành sức khỏe |              5–10 | Thu thập feedback có hiểu biết cơ bản về ngữ cảnh y tế  |
| Bác sĩ / điều dưỡng nếu tiếp cận được       |               3–5 | Thu thập feedback gần hơn với workflow lâm sàng thực tế |
| Health IT / Product reviewers               |               3–5 | Đánh giá workflow, hệ thống và tính khả thi sản phẩm    |
| Người dùng ngoài domain y tế                |              5–10 | Đánh giá usability, readability và độ rõ ràng của UI    |

Lưu ý: phản hồi từ non-domain users chỉ nên được dùng cho usability/readability feedback, không nên dùng để kết luận về tính đúng đắn lâm sàng.

---

## 3. Các giả định nghiên cứu cần xác thực

| Giả định                                               | Cách khảo sát xác thực                                                            |
| ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| A1: Hồ sơ bệnh nhân dài tạo gánh nặng khi review       | Hỏi về thời gian, mức độ khó khăn và khả năng bỏ sót thông tin khi review records |
| A2: Người dùng cần bằng chứng trước khi tin AI summary | Hỏi về mức độ hữu ích của citation và source evidence                             |
| A3: AI output nên giữ ở trạng thái draft               | Hỏi về kỳ vọng clinician approval trước khi sử dụng chính thức                    |
| A4: Safety warnings cải thiện niềm tin                 | Hỏi về unsupported/weak claim flags, missing information và conflict warnings     |
| A5: Summary workflow cần phân quyền theo vai trò       | Hỏi về ai được xem, tạo, chỉnh sửa, approve hoặc audit summary                    |

---

## 4. Cấu trúc khảo sát

### Section A — Thông tin nền của respondent

1. Mô tả nào phù hợp nhất với background của bạn?

   * Bác sĩ / clinician
   * Điều dưỡng
   * Sinh viên y khoa / sinh viên ngành sức khỏe
   * Health IT / Product
   * AI / Engineering
   * Khác

2. Bạn quen thuộc với electronic health records hoặc patient records ở mức độ nào?

   * Không quen thuộc
   * Hơi quen thuộc
   * Quen thuộc ở mức trung bình
   * Rất quen thuộc
   * Người dùng chuyên môn / professional user

---

### Section B — Problem validation

Sử dụng thang đo Likert 1–5:

```text
1 = Hoàn toàn không đồng ý
5 = Hoàn toàn đồng ý
```

| No. | Statement                                                                                                                    |
| --: | ---------------------------------------------------------------------------------------------------------------------------- |
|   1 | Việc review hồ sơ bệnh nhân dài có thể tốn nhiều thời gian.                                                                  |
|   2 | Thông tin quan trọng về bệnh nhân có thể bị bỏ sót khi dữ liệu nằm rải rác ở nhiều ghi chú, kết quả hoặc tài liệu khác nhau. |
|   3 | Một bản tóm tắt bệnh nhân có cấu trúc sẽ giúp tăng tốc quá trình review hồ sơ.                                               |
|   4 | Sẽ khó tin tưởng một bản summary nếu hệ thống không hiển thị nguồn thông tin.                                                |
|   5 | Summary nên hiển thị thông tin chưa chắc chắn hoặc dữ liệu còn thiếu, thay vì tự suy đoán.                                   |

---

### Section C — Trust and safety

| No. | Statement                                                                                    |
| --: | -------------------------------------------------------------------------------------------- |
|   6 | Tôi sẽ tin tưởng một AI-generated summary hơn nếu mỗi claim quan trọng đều có citation.      |
|   7 | Các claim không có bằng chứng hỗ trợ nên được flag rõ ràng.                                  |
|   8 | Khi có thông tin mâu thuẫn, hệ thống nên hiển thị conflict thay vì để AI tự động giải quyết. |
|   9 | AI-generated medical summaries nên cần clinician review trước khi được sử dụng chính thức.   |
|  10 | Hệ thống nên ghi audit logs về việc ai đã tạo, chỉnh sửa hoặc phê duyệt summary.             |

---

### Section D — Workflow and UI

| No. | Statement                                                                                    |
| --: | -------------------------------------------------------------------------------------------- |
|  11 | Giao diện side-by-side giữa summary và source evidence sẽ hữu ích.                           |
|  12 | Safety panel hiển thị unsupported claims sẽ giúp tăng sự tự tin khi review.                  |
|  13 | Role-based access là quan trọng trong một hệ thống tóm tắt bệnh án.                          |
|  14 | Bác sĩ nên có khả năng chỉnh sửa AI-generated summary trước khi phê duyệt.                   |
|  15 | Admin dashboard hiển thị citation coverage và rejection rate sẽ hữu ích cho việc monitoring. |

---

### Section E — Câu hỏi mở

1. Theo bạn, thông tin nào luôn cần xuất hiện trong một patient summary?
2. Điều gì sẽ khiến bạn không tin tưởng một AI-generated clinical summary?
3. Hành động nào trong hệ thống nên bắt buộc phải có human approval?
4. Loại safety warning nào sẽ hữu ích nhất đối với bạn?
5. Điều gì sẽ khiến hệ thống này hữu ích hơn trong workflow thực tế?

---

## 5. Kế hoạch phân tích kết quả khảo sát

### 5.1 Phân tích định lượng

Đối với các câu hỏi Likert-scale:

* Tính điểm trung bình cho từng câu hỏi.
* Nhóm câu hỏi theo các theme chính:

  * burden;
  * trust;
  * safety;
  * workflow;
  * UI usefulness.
* Xác định top 3 nhu cầu mạnh nhất.
* Xác định các giả định có điểm thấp hoặc gây tranh luận.
* So sánh phản hồi giữa các nhóm respondent nếu đủ mẫu, ví dụ:

  * healthcare-related respondents;
  * product/IT respondents;
  * non-domain respondents.

### 5.2 Phân tích định tính

Đối với các câu hỏi mở:

* Mã hóa câu trả lời theo theme:

  * missing data;
  * citation;
  * hallucination;
  * workflow;
  * trust;
  * UI clarity;
  * human approval;
  * auditability.
* Trích xuất một số representative quotes.
* Chuyển insight thành PRD changes hoặc UI changes.

Ví dụ:

| Insight từ khảo sát                                     | Cách chuyển thành yêu cầu sản phẩm                         |
| ------------------------------------------------------- | ---------------------------------------------------------- |
| Người dùng sợ AI tự thêm thông tin không có trong hồ sơ | Tăng ưu tiên cho unsupported claim detection               |
| Người dùng muốn xem nguồn ngay cạnh summary             | Thiết kế citation badge và evidence panel                  |
| Người dùng không muốn AI output tự động thành official  | Giữ summary ở trạng thái draft và bắt buộc doctor approval |
| Người dùng muốn biết ai đã chỉnh sửa/phê duyệt summary  | Bổ sung audit log và review history                        |

---

## 6. Cách kết quả khảo sát ảnh hưởng đến PRD

| Survey insight                                     | Ảnh hưởng đến PRD                                |
| -------------------------------------------------- | ------------------------------------------------ |
| Người dùng xác nhận record review là tốn thời gian | Củng cố problem statement                        |
| Người dùng yêu cầu citation                        | Ưu tiên citation panel và source evidence viewer |
| Người dùng lo ngại hallucination                   | Tăng trọng tâm cho safety requirements           |
| Người dùng muốn doctor approval                    | Giữ HITL review là core flow                     |
| Người dùng đánh giá cao dashboard                  | Duy trì monitoring/admin module                  |
| Người dùng thấy role-based access quan trọng       | Bổ sung role-based UI matrix                     |
| Người dùng muốn summary rõ ràng và dễ đọc          | Bổ sung readability vào human evaluation         |
| Người dùng muốn biết phần nào thiếu dữ liệu        | Bổ sung missing-information policy               |

---

## 7. Tiêu chí thành công tối thiểu của khảo sát

| Tiêu chí                                                 |              Mục tiêu |
| -------------------------------------------------------- | --------------------: |
| Số lượng respondents                                     | 10+ cho MVP discovery |
| Điểm trung bình cho summary usefulness                   |   >= 4/5 là desirable |
| Điểm trung bình cho citation usefulness                  |   >= 4/5 là desirable |
| Điểm trung bình cho nhu cầu clinician approval           |   >= 4/5 là desirable |
| Có ít nhất 5 câu trả lời mở hữu ích                      |                    Có |
| Có ít nhất 2 nhóm respondent khác nhau                   |             Desirable |
| Có ít nhất một insight có thể chuyển thành PRD/UI change |              Bắt buộc |

Các tiêu chí này không nhằm chứng minh clinical safety, mà nhằm xác định xem hướng sản phẩm có phù hợp với nhu cầu người dùng ban đầu hay không.

---

## 8. Định dạng báo cáo kết quả khảo sát

Survey findings nên được tóm tắt trong final report theo format sau:

```text
Survey results indicate that respondents perceive patient record review as time-consuming and consider citation visibility important for trust. The majority of respondents prefer AI-generated medical summaries to remain draft until reviewed by a clinician. These findings support the MVP design decisions: citation-based summary, safety panel, and doctor-in-the-loop review workflow.
```

Bản tiếng Việt đề xuất:

```text
Kết quả khảo sát cho thấy respondents nhìn nhận việc review hồ sơ bệnh nhân là tốn thời gian và cho rằng citation visibility là yếu tố quan trọng để tạo niềm tin đối với AI-generated summaries. Phần lớn respondents mong muốn medical summaries do AI tạo ra phải giữ ở trạng thái draft cho đến khi được clinician review. Các kết quả này củng cố các quyết định thiết kế chính của MVP: citation-based summary, safety panel và doctor-in-the-loop review workflow.
```

Trong final report, kết quả khảo sát nên được trình bày theo ba phần:

1. **Key quantitative findings**
   Ví dụ: điểm trung bình cho usefulness, citation trust, approval requirement.

2. **Key qualitative insights**
   Ví dụ: người dùng muốn thấy nguồn, muốn cảnh báo missing information, không muốn AI tự suy đoán.

3. **Product implications**
   Ví dụ: giữ citation panel, giữ HITL review, bổ sung role-based UI và safety panel.

---

## 9. Giới hạn của khảo sát

Khảo sát này có một số giới hạn:

* Cỡ mẫu có thể nhỏ và chưa đại diện cho toàn bộ người dùng y tế.
* Survey sample có thể không bao gồm đủ bác sĩ hoặc clinician đang hành nghề.
* Kết quả khảo sát chỉ validate user perception, không chứng minh clinical safety.
* Non-domain respondents chỉ nên được dùng cho usability feedback.
* Survey không thể thay thế human evaluation trên generated summaries.
* Survey không thể thay thế benchmark evaluation trên real EHR note-level datasets.
* Kết quả có thể bị ảnh hưởng bởi cách diễn đạt câu hỏi và mức độ hiểu biết của respondent về AI trong y tế.

---

## 10. Cách sử dụng survey trong dự án

Kết quả khảo sát sẽ được sử dụng để:

1. Điều chỉnh problem statement trong PRD.
2. Ưu tiên các tính năng quan trọng như citation, safety panel và HITL review.
3. Xác nhận vai trò của role-based access trong workflow.
4. Bổ sung insight vào UI design.
5. Hỗ trợ phần research validation trong final report.
6. Xây dựng câu chuyện demo có tính thuyết phục hơn.

Survey không nên được diễn giải như bằng chứng lâm sàng, mà nên được xem là **bằng chứng product discovery** cho giai đoạn MVP.

---

## 11. Expected Survey Deliverables

Sau khi thực hiện khảo sát, các output nên bao gồm:

| Deliverable                 | Nội dung                                   |
| --------------------------- | ------------------------------------------ |
| Raw survey responses        | File gốc từ Google Forms/Microsoft Forms   |
| Cleaned response table      | Dữ liệu đã làm sạch để phân tích           |
| Survey summary report       | Tổng hợp kết quả định lượng và định tính   |
| PRD update notes            | Những thay đổi PRD dựa trên survey insight |
| UI/design implication notes | Những điểm cần cải thiện trong UI/workflow |
| Final report section        | Phần tóm tắt survey đưa vào final report   |

---

## 12. Recommended Mentor-facing Statement

> The survey is used as a product discovery tool to validate whether users experience difficulty reviewing long or fragmented medical records, and whether citation-grounded AI summaries with clinician review would be considered useful and trustworthy. It is not used as clinical validation, but as early evidence to support PRD scope, user flow design and trust-related requirements.

Bản tiếng Việt đề xuất:

> Khảo sát được sử dụng như một công cụ product discovery nhằm xác thực liệu người dùng có gặp khó khăn khi review hồ sơ bệnh án dài hoặc phân tán hay không, và liệu AI-generated summaries có citation cùng clinician review có được xem là hữu ích và đáng tin cậy hay không. Khảo sát không được sử dụng như clinical validation, mà là bằng chứng ban đầu để hỗ trợ phạm vi PRD, thiết kế user flow và các yêu cầu liên quan đến trust.
