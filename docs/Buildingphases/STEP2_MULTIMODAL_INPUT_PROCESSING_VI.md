# BƯỚC 2 - Multi-modal Input Processing

## Phạm vi

Module này tiếp nhận dữ liệu trước khi đưa vào RAG:

- File ghi âm `.wav` / `.mp3` của hội thoại bác sĩ - bệnh nhân được phiên âm
  bằng Whisper local.
- Ảnh chẩn đoán `.png` / `.jpg` / `.tiff` được mã hóa thành feature vector
  bằng Vision Transformer (ViT).
- Text báo cáo chẩn đoán hoặc OCR do RIS/HIS đính kèm được bảo toàn nguyên văn
  để tạo `ClinicalDocument` và đưa sang API ingest của Bước 1.

ViT trong thiết kế này **không phải OCR và không tự sinh kết luận X-quang/siêu
âm**. Feature vector có thể phục vụ retrieval hoặc mô hình đa phương thức sau
này; chỉ text nguồn đã được cung cấp mới đi vào tóm tắt lâm sàng.

## Architecture Logic

```text
                     +-------------------------------+
Audio .wav/.mp3 ---> | FastAPI audio:transcribe      |
                     | validate -> Whisper ASR       |
                     +---------------+---------------+
                                     | transcript + timestamps
                                     v
                         Raw Clinical Text Builder
                                     ^
                                     | attached report/OCR text
                     +---------------+---------------+
Image .png/.jpg ---> | FastAPI images:process        |
                     | validate -> ViT feature vector|
                     +-------------------------------+
                                     |
                                     v
            documents[] compatible with POST /records:ingest
                                     |
                                     v
                   Qdrant RAG + grounding guardrail (Step 1)
```

### An toàn dữ liệu

- Model được lazy-load trên server; file upload không được gửi tới Gemini hoặc
  dịch vụ ngoài trong cấu hình mặc định.
- File được kiểm tra extension, MIME type và giới hạn kích thước trước inference.
- `.wav` PCM 16-bit được giải mã trong process; `.mp3` yêu cầu `ffmpeg` trên
  máy chủ và file audio tạm dùng cho inference được xóa ngay sau xử lý.
- Transcript và text báo cáo chỉ là tài liệu nguồn nháp; bác sĩ phải xác nhận
  trước khi dùng lâm sàng hoặc ghi trả HIS/EMR.

## API Data Flow

Mọi endpoint yêu cầu headers:

```http
X-Tenant-ID: vinmec-sandbox
X-User-ID: clinician-demo
```

### 1. Speech-to-Text

```http
POST /api/v1/multimodal/patients/{patient_id}/audio:transcribe
Content-Type: multipart/form-data
```

| Form field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `audio` | file | Có | `.wav` hoặc `.mp3` |
| `document_id` | string | Có | ID tài liệu transcript |
| `language` | string | Không | Mặc định `vi` |

Response chứa `transcription`, các `segments` có timestamp và model Whisper.

### 2. Image Feature Processing

```http
POST /api/v1/multimodal/patients/{patient_id}/images:process
Content-Type: multipart/form-data
```

| Form field | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `image` | file | Có | Ảnh chẩn đoán |
| `document_id` | string | Có | ID ảnh/báo cáo |
| `attached_clinical_text` | string | Không | Report/OCR text nguồn |

Response chứa `feature_vector`, `feature_dimension` và text nguồn nếu có.

### 3. Combine thành Raw Clinical Text

```http
POST /api/v1/multimodal/patients/{patient_id}/inputs:prepare
Content-Type: multipart/form-data
```

Endpoint nhận audio, image hoặc cả hai; trả về:

```json
{
  "documents": [
    {
      "document_id": "audio-001",
      "document_type": "audio-transcript",
      "text": "..."
    },
    {
      "document_id": "image-001",
      "document_type": "diagnostic-image-report-text",
      "text": "..."
    }
  ],
  "prepared_modalities": ["..."],
  "audio_result": {},
  "image_result": {}
}
```

Mảng `documents` tương thích trực tiếp với:

```http
POST /api/v1/patients/{patient_id}/records:ingest
```

## Mã Nguồn

| Path | Trách nhiệm |
| --- | --- |
| `backend/app/multimodal_schemas.py` | Response/schema của modalities và Raw Clinical Text |
| `backend/app/services/multimodal.py` | Whisper, ViT, validation và document builder |
| `backend/app/routers/multimodal.py` | FastAPI multipart endpoints |
| `backend/app/main.py` | Đăng ký router và model health metadata |
| `backend/tests/test_multimodal_api.py` | Kiểm thử upload, compose và nối sang RAG |

## Chạy Module

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8080
```

Các model mặc định:

```dotenv
RAG_WHISPER_MODEL=openai/whisper-small
RAG_WHISPER_DEVICE=-1
RAG_VIT_MODEL=google/vit-base-patch16-224-in21k
RAG_VISION_DEVICE=cpu
```

Trọng số Hugging Face được tải ở lần inference đầu tiên. Trong triển khai nội
viện, cần mirror artifact đã phê duyệt vào registry nội bộ và chạy offline.
Container xử lý `.mp3` cần cài `ffmpeg`; có thể ưu tiên `.wav` PCM 16-bit để
giảm phụ thuộc codec trong vùng mạng bệnh viện.

Ví dụ gọi endpoint kết hợp:

```powershell
$headers = @{"X-Tenant-ID"="vinmec-sandbox"; "X-User-ID"="clinician-demo"}
curl.exe -X POST "http://127.0.0.1:8080/api/v1/multimodal/patients/patient-demo/inputs:prepare" `
  -H "X-Tenant-ID: vinmec-sandbox" -H "X-User-ID: clinician-demo" `
  -F "encounter_id=enc-001" -F "audio_document_id=audio-001" `
  -F "image_document_id=image-001" -F "audio=@consultation.wav;type=audio/wav" `
  -F "image=@xray.png;type=image/png" `
  -F "attached_clinical_text=FINDINGS: No acute cardiopulmonary abnormality."
```

## Hardening Trước Production

- Thêm antivirus/malware scan và DICOM de-identification trước processing.
- Tích hợp VAD/diarization để phân biệt bác sĩ và bệnh nhân.
- Benchmark Whisper tiếng Việt cho thuật ngữ y khoa và danh mục thuốc.
- Dùng OCR chuyên dụng cho ảnh/report scan; không sử dụng ViT feature thay OCR.
- Lưu provenance và consent khi audio/video xuất phát từ encounter thật.
