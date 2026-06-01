import io
import shutil
import tempfile
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import Settings
from ..multimodal_schemas import (
    AudioTranscriptionResponse,
    ImageProcessingResponse,
    PreparedModality,
    RawClinicalTextResponse,
    SpeechSegment,
)
from ..schemas import ClinicalDocument


AUDIO_EXTENSIONS = {".mp3", ".wav"}
AUDIO_MEDIA_TYPES = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
IMAGE_MEDIA_TYPES = {
    "image/png",
    "image/jpeg",
    "image/bmp",
    "image/tiff",
}


class MediaProcessingError(RuntimeError):
    pass


class MediaValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    segments: list[SpeechSegment]
    model: str


@dataclass(frozen=True)
class ImageFeatureResult:
    vector: list[float]
    model: str


class SpeechTranscriber(ABC):
    model_name: str

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, filename: str, language: str | None) -> TranscriptionResult:
        raise NotImplementedError


class ImageFeatureExtractor(ABC):
    model_name: str

    @abstractmethod
    def extract(self, image_bytes: bytes) -> ImageFeatureResult:
        raise NotImplementedError


class HuggingFaceWhisperTranscriber(SpeechTranscriber):
    """Lazy-loaded local Whisper ASR adapter for clinical conversation audio."""

    def __init__(self, model_name: str, device: int = -1):
        self.model_name = model_name
        self.device = device
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline
            except ImportError as exc:
                raise MediaProcessingError(
                    "Transformers is not installed; install requirements.txt."
                ) from exc
            try:
                self._pipeline = pipeline(
                    task="automatic-speech-recognition",
                    model=self.model_name,
                    device=self.device,
                )
            except Exception as exc:
                raise MediaProcessingError("Unable to load the configured Whisper model.") from exc
        return self._pipeline

    def transcribe(self, audio_bytes: bytes, filename: str, language: str | None) -> TranscriptionResult:
        suffix = Path(filename).suffix.casefold() or ".wav"
        temporary_path: Path | None = None
        try:
            pipeline_input: str | dict[str, object]
            if suffix == ".wav":
                pipeline_input = self._decode_wav(audio_bytes)
            else:
                if shutil.which("ffmpeg") is None:
                    raise MediaProcessingError(
                        "MP3 transcription requires ffmpeg installed on the API host."
                    )
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                    temporary.write(audio_bytes)
                    temporary_path = Path(temporary.name)
                pipeline_input = str(temporary_path)
            generate_kwargs = {"task": "transcribe"}
            if language:
                generate_kwargs["language"] = language
            raw = self._get_pipeline()(
                pipeline_input,
                generate_kwargs=generate_kwargs,
                return_timestamps=True,
            )
        except MediaProcessingError:
            raise
        except Exception as exc:
            raise MediaProcessingError("Speech-to-text inference failed.") from exc
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)

        text = str(raw.get("text", "")).strip()
        if not text:
            raise MediaProcessingError("Whisper returned an empty transcription.")
        segments = []
        for chunk in raw.get("chunks", []):
            timestamp = chunk.get("timestamp") or (None, None)
            segments.append(
                SpeechSegment(
                    start_seconds=timestamp[0],
                    end_seconds=timestamp[1],
                    text=str(chunk.get("text", "")).strip(),
                )
            )
        return TranscriptionResult(text=text, segments=segments, model=self.model_name)

    @staticmethod
    def _decode_wav(audio_bytes: bytes) -> dict[str, object]:
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as reader:
                if reader.getcomptype() != "NONE":
                    raise MediaValidationError("Compressed WAV audio is not supported.")
                channels = reader.getnchannels()
                sample_width = reader.getsampwidth()
                sampling_rate = reader.getframerate()
                frames = reader.readframes(reader.getnframes())
        except (wave.Error, EOFError) as exc:
            raise MediaValidationError("Uploaded WAV file cannot be decoded.") from exc
        if sample_width != 2:
            raise MediaValidationError("WAV audio must use 16-bit PCM samples.")
        waveform = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            waveform = waveform.reshape(-1, channels).mean(axis=1)
        return {"raw": waveform, "sampling_rate": sampling_rate}


class HuggingFaceViTFeatureExtractor(ImageFeatureExtractor):
    """Extracts a ViT representation; associated report text remains source text."""

    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._processor = None
        self._model = None

    def _load(self):
        if self._processor is None or self._model is None:
            try:
                import torch
                from transformers import AutoImageProcessor, ViTModel
            except ImportError as exc:
                raise MediaProcessingError(
                    "Transformers and PyTorch are required for ViT image processing."
                ) from exc
            try:
                self._processor = AutoImageProcessor.from_pretrained(self.model_name)
                self._model = ViTModel.from_pretrained(self.model_name).to(self.device)
                self._model.eval()
            except Exception as exc:
                raise MediaProcessingError("Unable to load the configured ViT model.") from exc
            return torch
        import torch

        return torch

    def extract(self, image_bytes: bytes) -> ImageFeatureResult:
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise MediaValidationError("Uploaded image cannot be decoded.") from exc
        torch = self._load()
        try:
            inputs = self._processor(images=image, return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with torch.inference_mode():
                output = self._model(**inputs)
            pooled = output.pooler_output
            if pooled is None:
                pooled = output.last_hidden_state[:, 0, :]
            vector = pooled[0].detach().cpu().float().tolist()
        except Exception as exc:
            raise MediaProcessingError("Vision feature extraction failed.") from exc
        return ImageFeatureResult(vector=vector, model=self.model_name)


class MultimodalService:
    def __init__(
        self,
        settings: Settings,
        transcriber: SpeechTranscriber | None = None,
        image_extractor: ImageFeatureExtractor | None = None,
    ):
        self.settings = settings
        self.transcriber = transcriber or HuggingFaceWhisperTranscriber(
            settings.whisper_model, settings.whisper_device
        )
        self.image_extractor = image_extractor or HuggingFaceViTFeatureExtractor(
            settings.vit_model, settings.vision_device
        )

    def transcribe_audio(
        self,
        tenant_id: str,
        patient_id: str,
        document_id: str,
        filename: str,
        media_type: str,
        audio_bytes: bytes,
        language: str | None,
    ) -> AudioTranscriptionResponse:
        self._validate_file(filename, media_type, audio_bytes, AUDIO_EXTENSIONS, AUDIO_MEDIA_TYPES,
                            self.settings.maximum_audio_bytes, "audio")
        result = self.transcriber.transcribe(audio_bytes, filename, language)
        return AudioTranscriptionResponse(
            tenant_id=tenant_id,
            patient_id=patient_id,
            document_id=document_id,
            original_filename=filename,
            media_type=media_type,
            language=language,
            model=result.model,
            transcription=result.text,
            segments=result.segments,
            warnings=["Transcript is an AI draft and requires clinician verification."],
        )

    def process_image(
        self,
        tenant_id: str,
        patient_id: str,
        document_id: str,
        filename: str,
        media_type: str,
        image_bytes: bytes,
        attached_clinical_text: str | None,
    ) -> ImageProcessingResponse:
        self._validate_file(filename, media_type, image_bytes, IMAGE_EXTENSIONS, IMAGE_MEDIA_TYPES,
                            self.settings.maximum_image_bytes, "image")
        result = self.image_extractor.extract(image_bytes)
        text = attached_clinical_text.strip() if attached_clinical_text else None
        warnings = [
            "ViT features are not a radiology diagnosis and require clinical review.",
            "ViT does not perform OCR; attached clinical text is preserved as the textual source.",
        ]
        if not text:
            warnings.append("No attached clinical report text was provided for summarization.")
        return ImageProcessingResponse(
            tenant_id=tenant_id,
            patient_id=patient_id,
            document_id=document_id,
            original_filename=filename,
            media_type=media_type,
            model=result.model,
            attached_clinical_text=text,
            feature_vector=result.vector,
            feature_dimension=len(result.vector),
            warnings=warnings,
        )

    def prepare_raw_clinical_text(
        self,
        tenant_id: str,
        patient_id: str,
        encounter_id: str | None,
        audio_result: AudioTranscriptionResponse | None,
        image_result: ImageProcessingResponse | None,
    ) -> RawClinicalTextResponse:
        documents: list[ClinicalDocument] = []
        modalities: list[PreparedModality] = []
        warnings: list[str] = []
        if audio_result:
            documents.append(
                ClinicalDocument(
                    document_id=audio_result.document_id,
                    document_type="audio-transcript",
                    title="Clinical conversation transcription",
                    encounter_id=encounter_id,
                    text=audio_result.transcription,
                    metadata={
                        "modality": "audio",
                        "source_filename": audio_result.original_filename,
                        "model": audio_result.model,
                    },
                )
            )
            modalities.append(
                PreparedModality(
                    modality="audio_transcript",
                    document_id=audio_result.document_id,
                    source_filename=audio_result.original_filename,
                    model=audio_result.model,
                )
            )
        if image_result and image_result.attached_clinical_text:
            documents.append(
                ClinicalDocument(
                    document_id=image_result.document_id,
                    document_type="diagnostic-image-report-text",
                    title="Attached diagnostic imaging text",
                    encounter_id=encounter_id,
                    text=image_result.attached_clinical_text,
                    metadata={
                        "modality": "diagnostic-image",
                        "source_filename": image_result.original_filename,
                        "model": image_result.model,
                    },
                )
            )
            modalities.append(
                PreparedModality(
                    modality="diagnostic_image_text",
                    document_id=image_result.document_id,
                    source_filename=image_result.original_filename,
                    model=image_result.model,
                )
            )
        elif image_result:
            warnings.append("Image features were produced, but no image text can be sent to RAG.")
        if not documents:
            raise MediaValidationError("No textual clinical content is available for RAG ingestion.")
        return RawClinicalTextResponse(
            tenant_id=tenant_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            documents=documents,
            prepared_modalities=modalities,
            audio_result=audio_result,
            image_result=image_result,
            warnings=warnings,
        )

    @staticmethod
    def _validate_file(
        filename: str,
        media_type: str,
        content: bytes,
        allowed_extensions: set[str],
        allowed_media_types: set[str],
        max_bytes: int,
        label: str,
    ) -> None:
        if not filename or Path(filename).suffix.casefold() not in allowed_extensions:
            raise MediaValidationError(f"Unsupported {label} file extension.")
        if media_type.casefold() not in allowed_media_types:
            raise MediaValidationError(f"Unsupported {label} media type.")
        if not content:
            raise MediaValidationError(f"Uploaded {label} file is empty.")
        if len(content) > max_bytes:
            raise MediaValidationError(f"Uploaded {label} file exceeds the configured size limit.")
