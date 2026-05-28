from typing import Literal

from pydantic import BaseModel, Field


class ExtractedMedicalEntity(BaseModel):
    entity_type: Literal["medication", "medication_dose", "clinical_measurement"]
    name: str
    value: str | None = None
    normalized_key: str
    start_idx: int = Field(ge=0)
    end_idx: int = Field(gt=0)


class MedicalSafetyIssue(BaseModel):
    code: Literal[
        "UNSUPPORTED_MEDICATION",
        "UNSUPPORTED_MEDICATION_DOSAGE",
        "UNSUPPORTED_CLINICAL_MEASUREMENT",
        "NLI_CONTRADICTION",
        "NLI_VALIDATION_UNAVAILABLE",
    ]
    message: str
    entity: ExtractedMedicalEntity | None = None
    summary_claim: str | None = None
    confidence: float | None = None


class MedicalGuardrailResult(BaseModel):
    status: Literal["passed", "failed"]
    allow_emr_writeback: bool
    checks_applied: list[str]
    source_entities: list[ExtractedMedicalEntity]
    summary_entities: list[ExtractedMedicalEntity]
    issues: list[MedicalSafetyIssue]


class NliContradiction(BaseModel):
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
