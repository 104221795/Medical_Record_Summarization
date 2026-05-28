from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .fhir_models import FhirClinicalInputBundle, FhirTransactionBundle
from .medical_guardrail_schemas import MedicalGuardrailResult
from .schemas import CandidateSummary, ClinicalDocument, ClinicalNotesSummaryResponse, EvidenceChunk


class ConditionMappingInput(BaseModel):
    condition_id: str = Field(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    display: str = Field(min_length=2, max_length=500)
    code: str | None = Field(default=None, max_length=80)
    code_system: str | None = Field(default=None, max_length=300)
    clinical_status: Literal["active", "recurrence", "relapse", "inactive", "remission", "resolved"] = "active"
    verification_status: Literal[
        "unconfirmed", "provisional", "differential", "confirmed", "refuted", "entered-in-error"
    ] = "provisional"
    category: Literal["problem-list-item", "encounter-diagnosis"] = "encounter-diagnosis"
    evidence_document_ids: list[str] = Field(default_factory=list, max_length=100)


class FhirMappingRequest(BaseModel):
    patient_id: str = Field(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    encounter_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    author_reference: str | None = Field(default=None, max_length=300)
    composition_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    clinical_impression_id: str | None = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9._-]+$"
    )
    source_documents: list[ClinicalDocument] = Field(min_length=1, max_length=1000)
    retrieved_evidence: list[EvidenceChunk] = Field(min_length=1, max_length=1000)
    summary_status: Literal["accepted"]
    summary: CandidateSummary
    conditions: list[ConditionMappingInput] = Field(default_factory=list, max_length=100)

    @field_validator("summary")
    @classmethod
    def require_summary_claims(cls, value: CandidateSummary) -> CandidateSummary:
        if not value.claims:
            raise ValueError("An accepted summary must contain at least one claim.")
        if any(not item.evidence_ids for item in value.claims):
            raise ValueError("Each FHIR-mapped claim must retain evidence IDs.")
        return value

    @model_validator(mode="after")
    def require_retrieved_citations(self) -> "FhirMappingRequest":
        evidence_ids = {item.chunk_id for item in self.retrieved_evidence}
        unknown_ids = {
            evidence_id
            for claim in self.summary.claims
            for evidence_id in claim.evidence_ids
            if evidence_id not in evidence_ids
        }
        if unknown_ids:
            raise ValueError(
                "Summary citation IDs must belong to retrieved evidence: "
                + ", ".join(sorted(unknown_ids))
            )
        source_ids = {item.document_id for item in self.source_documents}
        if any(item.document_id not in source_ids for item in self.retrieved_evidence):
            raise ValueError("Retrieved evidence must originate from submitted source documents.")
        return self


class FhirMappingResponse(BaseModel):
    tenant_id: str
    patient_id: str
    generated_at: datetime
    validation_standard: str = "FHIR R4 scoped Pydantic profile"
    medical_guardrail: MedicalGuardrailResult
    bundle: FhirTransactionBundle


class FhirMockPushRequest(BaseModel):
    destination_base_url: str | None = None
    bundle: FhirTransactionBundle

    @field_validator("destination_base_url")
    @classmethod
    def validate_fhir_destination(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("FHIR destination must be an HTTP(S) base URL.")
        return value.rstrip("/") if value else value


class FhirMockPushResponse(BaseModel):
    status: Literal["accepted-for-mock-delivery"]
    destination_base_url: str
    transaction_id: str
    resources_received: int
    resource_types: list[str]
    persisted: bool = False
    message: str


class FhirBundleSummaryRequest(BaseModel):
    bundle: FhirClinicalInputBundle
    clinical_notes: str = Field(min_length=2, max_length=1_000_000)
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
    def require_non_blank_notes(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("clinical_notes must contain clinical content.")
        return value


class FhirBundleSummaryResponse(BaseModel):
    validation_standard: str = "FHIR R4 scoped Pydantic profile"
    source_bundle_id: str
    summary: ClinicalNotesSummaryResponse


class MedicalGuardrailRequest(BaseModel):
    raw_clinical_text: str = Field(min_length=2, max_length=2_000_000)
    ai_summary_json: dict[str, Any]
