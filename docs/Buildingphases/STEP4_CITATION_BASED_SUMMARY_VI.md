# BƯỚC 4 - Citation-based Summary

## Phạm vi

Module này hiển thị bản tóm tắt theo từng câu và cho phép người dùng đối chiếu
ngay với đoạn bệnh án nguồn. Backend không tin citation do mô hình trả về một
cách mù quáng: citation phải qua guardrail của RAG trước khi trở thành
`source_chunks` có offset dùng để highlight.

## Architecture Logic

```text
ClinicalDocument[] -> Chunking giữ char_start / char_end -> Qdrant retrieval
                                                        |
                                                        v
                                                  LLM Generator
                                      claim.text + evidence_ids[]
                                                        |
                                                        v
                                               Grounding Guardrail
                                  ID tồn tại + hỗ trợ + contradiction check
                                                        |
                     accepted --------------------------+-------- blocked
                        |                                          |
                        v                                          v
        Citation response mapper                          sentences = []
 summary_sentence + citations + source_chunks         không hiển thị claim
                        |
                        v
        Browser hover/click -> highlight đoạn nguồn bằng source offsets
```

## Backend Contract

Endpoint:

```http
POST /api/v1/patients/{patient_id}/summaries:generate-cited
X-Tenant-ID: vinmec-sandbox
X-User-ID: clinician-demo
Content-Type: application/json
```

Request:

```json
{
  "clinical_question": "Summarize active findings and plan.",
  "workflow": "active_record",
  "top_k": 6
}
```

Response item đúng dạng câu tóm tắt kèm citation:

```json
{
  "summary_sentence": "No pulmonary edema.",
  "citations": ["b679c0a1-source-chunk-id"],
  "source_chunks": [
    {
      "citation_id": "b679c0a1-source-chunk-id",
      "document_id": "citation-source-note",
      "document_type": "clinical-note",
      "section": "Findings",
      "text": "Heart size is normal. No pulmonary edema.",
      "char_start": 320,
      "char_end": 364
    }
  ]
}
```

Response tổng:

```json
{
  "status": "accepted",
  "sentences": [
    {
      "summary_sentence": "No pulmonary edema.",
      "citations": ["b679c0a1-source-chunk-id"],
      "source_chunks": [
        {
          "citation_id": "b679c0a1-source-chunk-id",
          "document_id": "citation-source-note",
          "char_start": 320,
          "char_end": 364
        }
      ]
    }
  ],
  "guardrail": {
    "approved": true,
    "citation_coverage": 100.0
  }
}
```

Nếu guardrail phát hiện mâu thuẫn hoặc citation không hợp lệ:

```json
{
  "status": "blocked",
  "sentences": [],
  "guardrail": {
    "approved": false
  }
}
```

## Backend Code

| Path | Vai trò |
| --- | --- |
| `backend/app/schemas.py` | `SourceChunkCitation`, `CitedSummarySentence`, `CitationSummaryResponse` |
| `backend/app/services/generators.py` | Prompt/schema buộc LLM sinh claim với `evidence_ids` |
| `backend/app/services/rag.py` | Chuyển claim đã approved thành sentence và source offsets |
| `backend/app/routers/rag.py` | Endpoint `summaries:generate-cited` |

### Luồng mapping

1. RAG retrieve danh sách `EvidenceChunk`.
2. Generator sinh claim và `evidence_ids`.
3. `GroundingGuardrail` kiểm tra claim chỉ dựa trên evidence đã retrieve.
4. Với output accepted, `RagService` ánh xạ từng ID sang chunk:
   `document_id`, `section`, `text`, `char_start`, `char_end`.
5. Với output blocked, API không trả sentence có thể hiển thị.

## Frontend Demo

Trang demo:

```text
http://127.0.0.1:8080/citation-demo
```

Files:

| Path | Vai trò |
| --- | --- |
| `backend/ui/citation/index.html` | Layout hai cột |
| `backend/ui/citation/styles.css` | Clinical review styling và highlight |
| `backend/ui/citation/app.js` | Ingest, generate-cited và offset highlighting |

UI hoạt động như sau:

- Bên trái nhập hồ sơ thô và hiển thị preview nguồn.
- Bên phải hiển thị từng `summary_sentence` và chip citation.
- Hover tạm thời highlight source; click cố định câu đang review.
- Nếu nhiều source spans giao nhau, frontend gộp vùng highlight để không lặp
  nội dung.

## Chạy Thử

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8080
```

Mở `http://127.0.0.1:8080/citation-demo`, bấm `Tải mẫu`, rồi chọn
`Index and summarize`.

Backend mặc định sử dụng local extractive generator nên demo chạy mà không gửi
bệnh án ra ngoài. Khi bật Gemini trong môi trường đã được phê duyệt, output
vẫn phải qua cùng guardrail và citation mapper trước khi UI hiển thị.

## Production Hardening

- Lưu immutable document version; offset chỉ hợp lệ trên đúng version nguồn.
- Gắn citation vào FHIR `Composition.section` và provenance sau attestation.
- Audit sự kiện bác sĩ click, sửa, chấp nhận hoặc từ chối claim.
- Đánh giá entailment lâm sàng cho sentence-source, không chỉ existence của ID.
