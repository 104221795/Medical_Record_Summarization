# BƯỚC 3 - FHIR Data Mapper

## Phạm vi

Module chuyển dữ liệu bệnh án thô và bản tóm tắt đã vượt qua guardrail sang
JSON theo FHIR R4, sử dụng ba tài nguyên được yêu cầu:

- `Composition`: tài liệu tóm tắt AI ở trạng thái `preliminary`, chờ bác sĩ ký.
- `ClinicalImpression`: bản đánh giá có căn cứ evidence từ summary.
- `Condition`: vấn đề/chẩn đoán **do workflow lâm sàng cung cấp có cấu trúc**,
  không tự suy diễn từ văn bản hoặc từ LLM.

Module có mock endpoint nhận một FHIR `Bundle` kiểu `transaction` như một máy
chủ trung tâm kiểu HAPI FHIR, nhưng không truyền dữ liệu ra hệ thống bên ngoài.

## Architecture Logic

```text
Raw Clinical Text / ClinicalDocument[]         Accepted grounded Summary
                |                                      |
                +------------------+-------------------+
                                   v
                         FhirMapperService
                    validate patient / evidence links
                    validate summary retained citations
                    map structured conditions only
                                   |
                                   v
                       FHIR R4 Transaction Bundle
       Composition(preliminary) + ClinicalImpression + Condition[]
                                   |
                                   v
                 POST /fhir/r4/mock-server/$transaction
               validated acknowledgement, no external persistence
```

### Nguyên tắc an toàn

- Mapper chỉ nhận `summary_status="accepted"`; summary bị RAG guardrail
  `blocked` không thể chuyển sang luồng writeback.
- Mọi `evidence_id` của claim phải tồn tại trong `retrieved_evidence` và mỗi
  evidence phải bắt nguồn từ một `source_document` được nộp cùng request.
- `Composition.status="preliminary"` vì nội dung AI chưa được clinical
  attestation. Chỉ workflow ký duyệt của bác sĩ mới được đổi thành `final`.
- `Condition` không được tạo từ AI claim. Caller phải gửi condition dạng cấu
  trúc và chỉ được tham chiếu source document có mặt trong request.
- Mock push không phải kết nối HAPI thật; production cần OAuth2/SMART on FHIR,
  audit, consent và capability/profile validation.

## API Data Flow

Headers:

```http
X-Tenant-ID: vinmec-sandbox
X-User-ID: clinician-demo
```

### Mapping Endpoint

```http
POST /api/v1/fhir/r4/summary-bundles:map
Content-Type: application/json
```

Input mẫu nằm tại `backend/examples/fhir_summary_mapping_request.json`:

```json
{
  "patient_id": "patient-demo",
  "encounter_id": "enc-demo-002",
  "source_documents": [
    {
      "document_id": "report-2026-05-20",
      "document_type": "diagnostic-report",
      "text": "FINDINGS:\nNo pulmonary edema."
    }
  ],
  "retrieved_evidence": [
    {
      "chunk_id": "report-2026-05-20-findings-001",
      "patient_id": "patient-demo",
      "document_id": "report-2026-05-20",
      "document_type": "diagnostic-report",
      "section": "Findings",
      "text": "No pulmonary edema.",
      "char_start": 10,
      "char_end": 29
    }
  ],
  "summary_status": "accepted",
  "summary": {
    "claims": [
      {
        "text": "No pulmonary edema.",
        "evidence_ids": ["report-2026-05-20-findings-001"]
      }
    ]
  },
  "conditions": [
    {
      "condition_id": "bph-suspected-001",
      "display": "Suspected benign prostatic hyperplasia",
      "clinical_status": "active",
      "verification_status": "provisional",
      "category": "encounter-diagnosis",
      "evidence_document_ids": ["report-2026-05-20"]
    }
  ]
}
```

### Mock Central FHIR Push

```http
POST /api/v1/fhir/r4/mock-server/$transaction
Content-Type: application/json
```

Request:

```json
{
  "destination_base_url": "https://hapi-fhir.sandbox.local/fhir",
  "bundle": {
    "resourceType": "Bundle",
    "type": "transaction",
    "entry": []
  }
}
```

Trong thực tế, trường `bundle` là Bundle nhận từ endpoint mapping. Response xác
nhận số resource đã validate và luôn trả `persisted=false` ở mock mode.

## FHIR JSON Structure

### Composition

```json
{
  "resourceType": "Composition",
  "status": "preliminary",
  "type": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "18842-5",
        "display": "Discharge summary"
      }
    ],
    "text": "AI-assisted medical record summary draft"
  },
  "subject": {"reference": "Patient/patient-demo"},
  "encounter": {"reference": "Encounter/enc-demo-002"},
  "author": [{"reference": "Device/clinical-summarization-service"}],
  "title": "AI-assisted Medical Record Summary - Clinician Review Required",
  "section": [
    {
      "title": "AI-assisted clinical summary - pending clinician attestation",
      "text": {
        "status": "generated",
        "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\"><ol><li>No pulmonary edema. <small>Evidence: report-2026-05-20-findings-001</small></li></ol></div>"
      },
      "entry": [{"reference": "urn:uuid:clinical-impression-reference"}]
    }
  ]
}
```

### Condition

```json
{
  "resourceType": "Condition",
  "id": "bph-suspected-001",
  "clinicalStatus": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
        "code": "active"
      }
    ]
  },
  "verificationStatus": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
        "code": "provisional"
      }
    ]
  },
  "code": {"text": "Suspected benign prostatic hyperplasia"},
  "subject": {"reference": "Patient/patient-demo"},
  "evidence": [
    {"detail": [{"reference": "DocumentReference/report-2026-05-20"}]}
  ]
}
```

### ClinicalImpression

```json
{
  "resourceType": "ClinicalImpression",
  "status": "completed",
  "subject": {"reference": "Patient/patient-demo"},
  "description": "AI-assisted grounded assessment draft pending clinician attestation.",
  "summary": "No pulmonary edema.",
  "finding": [
    {
      "itemCodeableConcept": {"text": "No pulmonary edema."},
      "basis": "Retrieved evidence chunks: report-2026-05-20-findings-001"
    }
  ],
  "note": [
    {"text": "AI-generated draft validated for evidence citations; not a signed diagnosis."}
  ]
}
```

### Transaction Bundle

Mỗi entry có `fullUrl` dạng `urn:uuid:` để các resources tham chiếu lẫn nhau
trong cùng transaction; `request.method="PUT"` tạo thao tác idempotent:

```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "fullUrl": "urn:uuid:...",
      "resource": {"resourceType": "Composition"},
      "request": {"method": "PUT", "url": "Composition/summary-id"}
    }
  ]
}
```

## Mã Nguồn

| Path | Vai trò |
| --- | --- |
| `backend/app/fhir_models.py` | Pydantic FHIR R4 scoped resource models/invariants |
| `backend/app/fhir_schemas.py` | API input/output schemas |
| `backend/app/services/fhir_mapper.py` | Mapping và mock push service |
| `backend/app/routers/fhir.py` | FastAPI FHIR endpoints |
| `backend/examples/fhir_summary_mapping_request.json` | Request mẫu |
| `backend/tests/test_fhir_api.py` | Validation và transaction API tests |

## Chạy Thử

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8080
$headers = @{"X-Tenant-ID"="vinmec-sandbox"; "X-User-ID"="clinician-demo"}
$payload = Get-Content backend\examples\fhir_summary_mapping_request.json -Raw
$mapped = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/fhir/r4/summary-bundles:map" -Headers $headers -ContentType "application/json" -Body $payload
$push = @{destination_base_url="https://hapi-fhir.sandbox.local/fhir"; bundle=$mapped.bundle} | ConvertTo-Json -Depth 30
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8080/api/v1/fhir/r4/mock-server/$transaction' -Headers $headers -ContentType "application/json" -Body $push
```

## Lưu Ý Validation

Các Pydantic model thực thi một profile hẹp cần cho module này và các invariant
FHIR R4 quan trọng; chúng không thay thế validator của implementation guide bệnh
viện. Trước production, cần kiểm tra Bundle bằng HAPI FHIR validator/Profile
chính thức của HIS/EMR đích.
