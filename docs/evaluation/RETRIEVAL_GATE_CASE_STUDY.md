# Case study: retrieval gate chặn 2/50 hồ sơ

> Đây là phân tích proxy trên artifact đã lưu. Không có model hoặc retrieval
> benchmark nào được chạy lại. Kết quả không phải clinical validation.

## Kết luận chính

Retrieval gate không chặn vì hệ thống “không tìm thấy gì”. Cả hai hồ sơ đều có
MRR `1.0` và Recall@5 tương đối cao, nhưng không có evidence được phân loại vào
section `DIAGNOSIS`. Điều này cho thấy gate đang kiểm tra sự hiện diện của loại
bằng chứng bắt buộc, thay vì chỉ dựa vào một retrieval score tổng quát.

| Note ID | Recall@5 | MRR | Diagnosis evidence | Gate reason | Kết quả gated |
| --- | ---: | ---: | --- | --- | --- |
| `multiclinsum_ls_en_10012` | 1.0000 | 1.0000 | Không | `missing_diagnosis_evidence` | 5/5 provider không generate |
| `multiclinsum_ls_en_10018` | 0.8333 | 1.0000 | Không | `missing_diagnosis_evidence` | 5/5 provider không generate |

## So sánh với run không gate

Trong run không gate, cả hai hồ sơ vẫn tạo được output cho năm provider.
Citation coverage quan sát được:

| Note ID | Deterministic | BART | Pegasus | Qwen2.5 | Llama3.2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `10012` | 1.0000 | 0.2000 | 0.5000 | 0.9000 | 0.8571 |
| `10018` | 0.8889 | 0.6000 | 0.3333 | 0.7647 | 0.7500 |

Critical-omission proxy của BART và Pegasus trên `10018` là `1.0`; ba provider
còn lại là `0.0`. Trên `10012`, cả năm provider có omission proxy `0.0`.

## Diễn giải đúng

- Recall@5 cao không đảm bảo evidence bắt buộc đã được lấy đúng section.
- Gate tạo ra failure có chủ đích và có thể giải thích, thay vì ép model tạo
  summary khi thiếu evidence chẩn đoán.
- Run không gate hữu ích để đo đủ 50/50 outputs và so sánh provider.
- Run gated hữu ích để chứng minh policy boundary.
- Hai run trả lời hai câu hỏi khác nhau và không được trộn số liệu.

## Điều chưa được chứng minh

- Gate không chứng minh mọi output không gate đều sai lâm sàng.
- Omission proxy bằng `0.0` không chứng minh hồ sơ đã đầy đủ theo đánh giá bác sĩ.
- Hai case không đủ để xác nhận threshold tối ưu hoặc hiệu quả ngoài dữ liệu PoC.
- Trước triển khai thật cần reviewer lâm sàng, dữ liệu được quản trị và
  prospective evaluation.

Nguồn chi tiết:

```text
artifacts/evaluation/week5_analysis/retrieval_gate_case_analysis.csv
artifacts/evaluation/week5_analysis/retrieval_threshold_sensitivity.csv
```
