# BƯỚC 1 - Hallucination Mitigation & RAG Setup

## Phạm vi

Bước này xây dựng backend FastAPI nhận hồ sơ thô của một bệnh nhân, lập chỉ mục
evidence trong Vector Database và chỉ trả về bản nháp tóm tắt khi mọi claim đều
có evidence truy xuất được hỗ trợ.

Không một guardrail dựa trên phần mềm nào có thể chứng minh tuyệt đối rằng mô
hình sinh không bao giờ sai trong mọi tình huống. Vì vậy thiết kế này áp dụng
nguyên tắc **fail closed**: claim không có trích dẫn, trích dẫn không thuộc
context, thiếu hỗ trợ hoặc mâu thuẫn phủ định sẽ làm toàn bộ summary bị giữ lại
với trạng thái `blocked`. Bản nháp được chấp nhận vẫn cần bác sĩ xác nhận.

FHIR mapping, giao diện bấm-highlight citation và ghi trả HIS/EMR thuộc bước
tiếp theo; Step 1 đã giữ sẵn `document_id`, `encounter_id`, `char_start` và
`char_end` để nối vào citation chính xác.

## Architecture Logic

```text
Raw EMR documents of one patient
        |
        v
POST /records:ingest -- tenant/patient scope validation
        |
        v
ClinicalChunker -- section aware, stable source offsets
        |
        v
EmbeddingProvider
  - development/test: deterministic hashing only
  - private deployment: FastEmbed / ONNX multilingual embeddings
        |
        v
Qdrant collection: clinical_record_chunks
  - every point filtered by tenant_id + patient_id
        |
        +---------------------------+
                                    |
POST /summaries:generate            v
Clinical question --> retrieval --> retrieved evidence chunks
                                    |
                                    v
                         SummaryGenerator
                          - default: extractive/local
                          - optional: governed Gemini adapter
                                    |
                                    v
                         GroundingGuardrail
                          citation ID exists
                          textual/semantic support
                          negation contradiction rule
                          fail-closed output gate
                                    |
                  accepted AI draft | blocked, summary withheld
```

### Quyết định an toàn

- Mặc định không gửi bệnh án ra API LLM: `RAG_GENERATOR_PROVIDER=extractive`
  trả lại các đoạn nguồn nguyên văn có citation.
- Adapter Gemini chỉ dành cho demo đã khử định danh hoặc luồng đã được phê
  duyệt quản trị dữ liệu; guardrail vẫn chạy sau generation.
- `hashing` embedding giúp chạy test không tải model, không dùng cho production.
  Cấu hình production từ chối khởi động nếu vẫn đặt `hashing`.
- Development mặc định dùng Qdrant in-memory để chạy an toàn với Uvicorn
  `--reload`; chỉ đặt `RAG_QDRANT_PATH` khi chạy local một process và cần giữ dữ liệu.
- Production nên chạy Qdrant cluster riêng qua `RAG_QDRANT_URL`, mã hóa dữ liệu, RBAC/OIDC, audit
  log bất biến và network policy nội viện.

## Data Schema

### Request ingest

`POST /api/v1/patients/{patient_id}/records:ingest`

Headers bắt buộc:

| Header | Ý nghĩa |
| --- | --- |
| `X-Tenant-ID` | Bệnh viện/cơ sở hoặc không gian dữ liệu |
| `X-User-ID` | Danh tính người dùng/service để gắn audit sau này |

```json
{
  "replace_patient_index": true,
  "documents": [
    {
      "document_id": "report-2026-05-20",
      "document_type": "diagnostic-report",
      "title": "Chest X-ray report",
      "encounter_id": "enc-demo-002",
      "authored_at": "2026-05-20T14:10:00+07:00",
      "text": "FINDINGS:\nNo pulmonary edema.\n\nIMPRESSION:\nNo acute findings.",
      "metadata": {"source_system": "ris-demo"}
    }
  ]
}
```

### Vector payload trong Qdrant

| Field | Mục đích |
| --- | --- |
| `tenant_id`, `patient_id` | Bộ lọc bắt buộc cho mọi retrieve/delete |
| `chunk_id` | ID ổn định sinh từ patient, document và offset |
| `document_id`, `document_type`, `encounter_id` | Nối về tài liệu EMR nguồn |
| `section`, `text` | Evidence được truy xuất |
| `char_start`, `char_end` | Vị trí nguyên văn trong document để highlight sau này |
| `authored_at` | Bối cảnh thời gian của evidence |

### API flow

| Endpoint | Kết quả |
| --- | --- |
| `GET /healthz` | Provider đang chạy và tình trạng API |
| `POST /patients/{id}/records:ingest` | Chunk và index bệnh án của bệnh nhân |
| `POST /patients/{id}/evidence:retrieve` | Trả evidence đã lọc theo tenant/patient |
| `POST /patients/{id}/summaries:generate` | Trả `accepted` hoặc `blocked` kèm guardrail report |

## Guardrail Pipeline

Mỗi `GeneratedClaim` phải có `evidence_ids`. Backend thực hiện:

1. Kiểm tra ID citation tồn tại trong chính tập evidence được retrieve.
2. Kiểm tra claim là đoạn nguyên văn hoặc vượt ngưỡng hỗ trợ lexical/embedding.
3. Chặn mâu thuẫn phủ định rõ ràng, ví dụ evidence `No pulmonary edema` nhưng
   claim nói `Pulmonary edema is present`.
4. Nếu có một lỗi, response vẫn cung cấp evidence để điều tra nhưng trường
   `summary` là `null`; nội dung sinh không được phát hành như bản tóm tắt.

Rule phủ định là guardrail bảo thủ ban đầu, không thay thế clinical NLI,
terminology service, medication reconciliation hay thẩm định bác sĩ. Các lớp
đó là hardening tiếp theo trước triển khai thực tế.

## Chạy Local

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rag.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8080
```

Mặc định dùng Qdrant in-memory và extractive generator để development/UI không
vướng lock khi dùng `--reload`. Nếu cần lưu local giữa các lần chạy, đặt
`RAG_QDRANT_PATH=backend/var/qdrant` và chỉ chạy một Uvicorn process; nhiều
worker hoặc production phải cấu hình `RAG_QDRANT_URL` tới Qdrant server.
Gọi ingest từ terminal khác:

```powershell
$headers = @{"X-Tenant-ID"="vinmec-sandbox"; "X-User-ID"="clinician-demo"}
$body = Get-Content backend\examples\raw_emr_patient_demo.json -Raw
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/patients/patient-demo/records:ingest" -Headers $headers -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/patients/patient-demo/summaries:generate" -Headers $headers -ContentType "application/json" -Body '{"clinical_question":"pulmonary edema","workflow":"diagnostic_report","top_k":6}'
```

Để dùng embedding ONNX nội bộ:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rag-onnx.txt
$env:RAG_EMBEDDING_PROVIDER = "fastembed"
$env:RAG_FASTEMBED_MODEL = "intfloat/multilingual-e5-large"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8080
```

Model embedding sẽ được tải lần đầu; trong môi trường bệnh viện cần mirror và
kiểm duyệt artifact model trước khi triển khai.

## Tệp triển khai

| Path | Vai trò |
| --- | --- |
| `backend/app/main.py` | FastAPI application factory |
| `backend/app/services/chunking.py` | Section-aware chunking và source offset |
| `backend/app/services/embeddings.py` | Hashing test provider / ONNX FastEmbed provider |
| `backend/app/services/vector_store.py` | Qdrant store với tenant/patient isolation |
| `backend/app/services/generators.py` | Extractive mặc định / Gemini có kiểm soát |
| `backend/app/services/guardrails.py` | Grounding và contradiction gate |
| `backend/tests/` | Kiểm thử offset, isolation và blocked output |

## Chưa thuộc Step 1

- Chuẩn hóa resource FHIR (`Patient`, `Encounter`, `DiagnosticReport`,
  `DocumentReference`, `Composition`, `Provenance`).
- UI click-to-highlight evidence.
- SSO, RBAC theo vai trò lâm sàng, audit trail và ký duyệt/ghi trả HIS.
- Clinical NLI benchmark, monitoring MLflow và deployment Kubernetes/Edge.
