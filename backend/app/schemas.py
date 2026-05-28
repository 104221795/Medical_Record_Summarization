from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ClinicalDocument(BaseModel):
    document_id: str = Field(min_length=1, max_length=128)
    document_type: str = Field(default="clinical-note", max_length=80)
    title: str | None = Field(default=None, max_length=200)
    encounter_id: str | None = Field(default=None, max_length=128)
    authored_at: datetime | None = None
    text: str = Field(min_length=1, max_length=1_000_000)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def require_non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Document text must contain clinical content.")
        return value


class IngestRequest(BaseModel):
    documents: list[ClinicalDocument] = Field(min_length=1, max_length=1000)
    replace_patient_index: bool = False


class IngestResponse(BaseModel):
    tenant_id: str
    patient_id: str
    documents_received: int
    chunks_indexed: int
    embedding_provider: str
    vector_collection: str


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    top_k: int = Field(default=6, ge=1, le=30)


class EvidenceChunk(BaseModel):
    chunk_id: str
    patient_id: str
    document_id: str
    document_type: str
    title: str | None = None
    encounter_id: str | None = None
    authored_at: datetime | None = None
    section: str
    text: str
    char_start: int
    char_end: int
    score: float | None = None


class RetrieveResponse(BaseModel):
    tenant_id: str
    patient_id: str
    query: str
    evidence: list[EvidenceChunk]


class SummaryRequest(BaseModel):
    clinical_question: str = Field(
        default="Summarize the active clinical record.",
        min_length=2,
        max_length=4000,
    )
    workflow: Literal["active_record", "diagnostic_report", "handoff"] = "active_record"
    top_k: int = Field(default=6, ge=1, le=30)


class GeneratedClaim(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class CandidateSummary(BaseModel):
    claims: list[GeneratedClaim] = Field(default_factory=list, max_length=30)
    missing_information: list[str] = Field(default_factory=list, max_length=20)


class GuardrailIssue(BaseModel):
    claim: str
    code: Literal[
        "MISSING_CITATION",
        "INVALID_CITATION",
        "LOW_SUPPORT",
        "POSSIBLE_CONTRADICTION",
    ]
    detail: str


class GuardrailReport(BaseModel):
    approved: bool
    checks_applied: list[str]
    citation_coverage: float
    issues: list[GuardrailIssue]
    disposition: str


class SummaryResponse(BaseModel):
    tenant_id: str
    patient_id: str
    status: Literal["accepted", "blocked"]
    workflow: str
    generator_provider: str
    evidence: list[EvidenceChunk]
    summary: CandidateSummary | None = None
    guardrail: GuardrailReport


class SourceChunkCitation(BaseModel):
    citation_id: str
    document_id: str
    document_type: str
    section: str
    text: str
    char_start: int
    char_end: int


class CitedSummarySentence(BaseModel):
    summary_sentence: str
    citations: list[str] = Field(min_length=1, max_length=20)
    source_chunks: list[SourceChunkCitation] = Field(min_length=1, max_length=20)


class CitationSummaryResponse(BaseModel):
    tenant_id: str
    patient_id: str
    status: Literal["accepted", "blocked"]
    workflow: str
    generator_provider: str
    sentences: list[CitedSummarySentence] = Field(default_factory=list)
    evidence: list[EvidenceChunk]
    guardrail: GuardrailReport


class ClinicalNotesSummaryRequest(BaseModel):
    patient_id: str = Field(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    clinical_notes: str = Field(min_length=2, max_length=1_000_000)
    document_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    encounter_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    clinical_question: str = Field(
        default="Summarize the active clinical record.",
        min_length=2,
        max_length=4000,
    )
    workflow: Literal["active_record", "diagnostic_report", "handoff"] = "active_record"
    top_k: int = Field(default=6, ge=1, le=30)
    replace_patient_index: bool = True

    @field_validator("clinical_notes")
    @classmethod
    def require_clinical_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("clinical_notes must contain clinical content.")
        return value


class CitationSpan(BaseModel):
    document_id: str
    source_chunk_id: str
    section: str
    start_idx: int = Field(ge=0)
    end_idx: int = Field(gt=0)
    source_text: str

    @model_validator(mode="after")
    def validate_offset_range(self) -> "CitationSpan":
        if self.end_idx <= self.start_idx:
            raise ValueError("Citation end_idx must be greater than start_idx.")
        return self


class GroundedSummarySentence(BaseModel):
    summary_sentence: str
    citations: list[CitationSpan] = Field(min_length=1, max_length=20)


class ClinicalNotesSummaryResponse(BaseModel):
    tenant_id: str
    patient_id: str
    status: Literal["accepted", "blocked"]
    workflow: str
    ingestion: IngestResponse
    sentences: list[GroundedSummarySentence] = Field(default_factory=list)
    guardrail: GuardrailReport
    clinical_disclaimer: str = (
        "AI-generated draft grounded in submitted evidence; clinician review is required."
    )


class HealthResponse(BaseModel):
    status: str
    service: str
    embedding_provider: str
    generator_provider: str
    speech_model: str | None = None
    vision_model: str | None = None
    fhir_endpoint_mode: str | None = None
    ort_execution_provider: str | None = None
    mlflow_enabled: bool | None = None


class ErrorResponse(BaseModel):
    detail: str
    context: dict[str, Any] = Field(default_factory=dict)
