from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .schemas import ClinicalDocument


class SpeechSegment(BaseModel):
    start_seconds: float | None = None
    end_seconds: float | None = None
    text: str


class AudioTranscriptionResponse(BaseModel):
    tenant_id: str
    patient_id: str
    document_id: str
    original_filename: str
    media_type: str
    language: str | None = None
    model: str
    transcription: str
    segments: list[SpeechSegment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImageProcessingResponse(BaseModel):
    tenant_id: str
    patient_id: str
    document_id: str
    original_filename: str
    media_type: str
    model: str
    attached_clinical_text: str | None = None
    feature_vector: list[float]
    feature_dimension: int
    warnings: list[str] = Field(default_factory=list)


class PreparedModality(BaseModel):
    modality: Literal["audio_transcript", "diagnostic_image_text"]
    document_id: str
    source_filename: str
    model: str


class RawClinicalTextResponse(BaseModel):
    tenant_id: str
    patient_id: str
    encounter_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    documents: list[ClinicalDocument]
    prepared_modalities: list[PreparedModality]
    audio_result: AudioTranscriptionResponse | None = None
    image_result: ImageProcessingResponse | None = None
    warnings: list[str] = Field(default_factory=list)
