import io
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.multimodal_schemas import SpeechSegment
from backend.app.services.multimodal import (
    ImageFeatureExtractor,
    ImageFeatureResult,
    HuggingFaceWhisperTranscriber,
    MultimodalService,
    SpeechTranscriber,
    TranscriptionResult,
)
from backend.app.services.rag import build_rag_service


HEADERS = {"X-Tenant-ID": "vinmec-sandbox", "X-User-ID": "clinician-demo"}


class FakeWhisper(SpeechTranscriber):
    model_name = "test-whisper"

    def transcribe(self, audio_bytes: bytes, filename: str, language: str | None) -> TranscriptionResult:
        assert audio_bytes
        return TranscriptionResult(
            text="Patient reports cough. Clinician documents no fever.",
            segments=[SpeechSegment(start_seconds=0.0, end_seconds=2.1, text="Patient reports cough.")],
            model=self.model_name,
        )


class FakeViT(ImageFeatureExtractor):
    model_name = "test-vit"

    def extract(self, image_bytes: bytes) -> ImageFeatureResult:
        assert image_bytes
        return ImageFeatureResult(vector=[0.1, 0.2, 0.3], model=self.model_name)


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        environment="test",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="multimodal_test_chunks",
        embedding_provider="hashing",
        generator_provider="extractive",
    )
    multimodal = MultimodalService(settings, FakeWhisper(), FakeViT())
    return TestClient(create_app(settings, build_rag_service(settings), multimodal))


def test_audio_transcription_endpoint_returns_clinical_text(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/v1/multimodal/patients/patient-demo/audio:transcribe",
        headers=HEADERS,
        data={"document_id": "audio-001", "language": "vi"},
        files={"audio": ("encounter.wav", b"RIFF-audio-content", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "test-whisper"
    assert "no fever" in response.json()["transcription"]


def test_combined_inputs_prepare_documents_ready_for_rag(tmp_path: Path) -> None:
    client = _client(tmp_path)
    report_text = "FINDINGS:\nNo focal consolidation.\nIMPRESSION:\nNo acute abnormality."

    prepared = client.post(
        "/api/v1/multimodal/patients/patient-demo/inputs:prepare",
        headers=HEADERS,
        data={
            "encounter_id": "enc-001",
            "audio_document_id": "audio-001",
            "image_document_id": "image-001",
            "attached_clinical_text": report_text,
        },
        files={
            "audio": ("encounter.wav", b"RIFF-audio-content", "audio/wav"),
            "image": ("xray.png", b"PNG-content", "image/png"),
        },
    )
    assert prepared.status_code == 200
    result = prepared.json()
    assert len(result["documents"]) == 2
    assert result["image_result"]["feature_dimension"] == 3
    assert "No focal consolidation" in result["documents"][1]["text"]

    indexed = client.post(
        "/api/v1/patients/patient-demo/records:ingest",
        headers=HEADERS,
        json={"documents": result["documents"], "replace_patient_index": True},
    )
    assert indexed.status_code == 200
    assert indexed.json()["documents_received"] == 2


def test_rejects_unsupported_audio_format(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/v1/multimodal/patients/patient-demo/audio:transcribe",
        headers=HEADERS,
        data={"document_id": "audio-001"},
        files={"audio": ("encounter.exe", b"not-audio", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert "extension" in response.json()["detail"]


def test_pcm_wav_is_decoded_locally_for_whisper() -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(b"\x00\x00" * 160)

    result = HuggingFaceWhisperTranscriber._decode_wav(buffer.getvalue())

    assert result["sampling_rate"] == 16000
    assert len(result["raw"]) == 160
