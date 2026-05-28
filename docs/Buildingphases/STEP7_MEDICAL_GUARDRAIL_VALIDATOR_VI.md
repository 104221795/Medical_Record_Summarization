# Step 7 - Medical Guardrail Validator

## Muc tieu safety

`MedicalGuardrail` la cong kiem tra cuoi cung truoc khi ban tom tat AI duoc
chuyen thanh FHIR transaction de ghi ve HIS/EMR. Validator mac dinh fail
closed neu phat hien noi dung moi khong co trong nguon.

## Cac kiem tra

- `medication_entity_presence_check`: chan ten thuoc chi co trong summary.
- `medication_dosage_exact_match_check`: chan thuoc co lieu khac text nguon.
- `clinical_measurement_exact_match_check`: chan vital/lab values moi hoac bi doi,
  gom huyet ap, HbA1c, SpO2, glucose, nhiet do, nhip tim va creatinine.
- `onnx-nli`: phan loai contradiction cho tung claim voi premise la clinical text goc.

Regex entity extraction la gate xac dinh, nhanh va audit duoc; danh muc medication
co the mo rong theo formulary cua benh vien. NLI bo sung kiem tra ngu nghia cho
nhung mau mau thuan khong nam trong cac thuc the cau truc.

## Code

- `backend/app/services/medical_guardrail.py`: `MedicalGuardrail`,
  `OnnxNliContradictionDetector`, schema report.
- `backend/app/services/fhir_mapper.py`: bat buoc validate truoc khi tao Bundle.
- `backend/app/routers/fhir.py`: API validate doc lap va writeback error report.

## API validation

```http
POST /api/v1/fhir/r4/guardrails:validate
X-Tenant-ID: vinmec-sandbox
X-User-ID: clinician-demo
Content-Type: application/json
```

```json
{
  "raw_clinical_text": "Dung metformin 500 mg moi ngay. HA: 145/92 mmHg.",
  "ai_summary_json": {
    "claims": [
      {"text": "Dung metformin 1000 mg va amlodipine 5 mg moi ngay."}
    ]
  }
}
```

Output bi chan:

```json
{
  "status": "failed",
  "allow_emr_writeback": false,
  "issues": [
    {"code": "UNSUPPORTED_MEDICATION_DOSAGE"},
    {"code": "UNSUPPORTED_MEDICATION"}
  ]
}
```

Endpoint `/api/v1/fhir/r4/summary-bundles:map` cung thuc thi validator. Khi
khong an toan, endpoint tra HTTP `422` va khong tao transaction cho EMR.

## NLI ONNX cuc bo

Cai dependency:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-guardrails-onnx.txt
```

Model directory can co:

```text
backend/models/deberta-v3-nli-small-onnx/
  model.onnx
  config.json
  tokenizer.json / tokenizer_config.json
```

Cau hinh:

```dotenv
RAG_MEDICAL_NLI_MODEL_PATH=./backend/models/deberta-v3-nli-small-onnx
RAG_MEDICAL_NLI_CONTRADICTION_THRESHOLD=0.80
RAG_MEDICAL_NLI_REQUIRED_FOR_WRITEBACK=true
```

Trong `production`, ung dung tu choi khoi dong neu chua bat NLI bat buoc va
chua cung cap model path. Kubernetes manifest mount model read-only tu PVC
`clinical-nli-model-pvc`.
