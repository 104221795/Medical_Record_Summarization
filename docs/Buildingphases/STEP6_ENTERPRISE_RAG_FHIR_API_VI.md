# Step 6 - Enterprise RAG va FHIR R4 Input API

## Kien truc xu ly

```text
Clinical notes / FHIR Bundle
        |
        v
Pydantic validation + FHIR reference safety checks
        |
        v
Section-aware ClinicalChunker (retains start/end offsets)
        |
        v
Embedding -> Qdrant, filtered by tenant_id and patient_id
        |
        v
Retriever -> grounded generator -> hallucination guardrail
        |
        +--> MLflow operational telemetry
        v
JSON summary sentences with source document citation spans
```

API chi tao ban nhap AI. Dau ra can bac si xem xet va ky xac nhan truoc khi
ghi tro lai HIS/EMR.

## Raw clinical notes endpoint

```http
POST /api/v1/clinical-summaries:generate-cited
X-Tenant-ID: vinmec-sandbox
X-User-ID: clinician-demo
Content-Type: application/json
```

```json
{
  "patient_id": "patient-demo",
  "clinical_notes": "TIEN SU: ...\nCHAN DOAN: ...\nKE HOACH: ...",
  "clinical_question": "Tom tat tinh trang va ke hoach dieu tri",
  "workflow": "active_record",
  "top_k": 6,
  "replace_patient_index": true
}
```

Moi cau tom tat duoc tra theo cau truc:

```json
{
  "summary_sentence": "Noi dung da duoc grounded.",
  "citations": [
    {
      "document_id": "clinical-notes-patient-demo",
      "source_chunk_id": "uuid",
      "section": "Chan Doan",
      "start_idx": 20,
      "end_idx": 57,
      "source_text": "Doan text nguon chinh xac."
    }
  ]
}
```

## FHIR R4 Bundle endpoint

```http
POST /api/v1/fhir/r4/bundles:ingest-and-summarize
X-Tenant-ID: vinmec-sandbox
X-User-ID: clinician-demo
Content-Type: application/json
```

Payload chay duoc co san tai
`backend/examples/fhir_clinical_input_bundle.json`. Bundle bat buoc co:

- Dung mot resource `Patient`.
- It nhat mot `Encounter` tham chieu dung `Patient`.
- It nhat mot `Observation` tham chieu dung `Patient`; neu tham chieu
  `Encounter`, encounter do phai co trong Bundle.

Moi `Observation` duoc index thanh tai lieu co ID
`fhir-observation-{observation.id}`. Vi vay citation tren ban tom tat truy
vet duoc dung resource nguon.

## FHIR writeback

Sau khi ban tom tat co `status=accepted` va bac si phe duyet, endpoint da co:

```http
POST /api/v1/fhir/r4/summary-bundles:map
POST /api/v1/fhir/r4/mock-server/$transaction
```

se validate va chuyen thanh `Composition`, `ClinicalImpression`,
`Condition` trong transaction Bundle FHIR R4.

## Chay local

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8080
```

Mo Swagger UI tai `http://127.0.0.1:8000/docs`.
