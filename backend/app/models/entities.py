from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base, CreatedAtMixin, TimestampMixin


class SummaryStatus(str, enum.Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ClaimSupportStatus(str, enum.Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNCHECKED = "unchecked"


class ReviewAction(str, enum.Enum):
    START_REVIEW = "start_review"
    EDIT = "edit"
    APPROVE = "approve"
    REJECT = "reject"
    COMMENT = "comment"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _workflow_enum(enum_type: type[enum.Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_type,
        name=name,
        values_callable=lambda values: [item.value for item in values],
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class Role(Base, CreatedAtMixin):
    __tablename__ = "roles"

    role_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = _uuid_pk()
    external_user_id: Mapped[str | None] = mapped_column(String(100), index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    auth_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="password")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    department: Mapped[str | None] = mapped_column(String(255))
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.role_code"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    role: Mapped[Role] = relationship(back_populates="users")


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    patient_id: Mapped[uuid.UUID] = _uuid_pk()
    external_patient_id: Mapped[str | None] = mapped_column(String(100), index=True)
    patient_hash: Mapped[str | None] = mapped_column(String(255), unique=True)
    full_name_encrypted: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(30))
    phone_encrypted: Mapped[str | None] = mapped_column(Text)
    address_encrypted: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str | None] = mapped_column(String(100))
    fhir_patient_id: Mapped[str | None] = mapped_column(String(100), index=True)
    is_deidentified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    encounters: Mapped[list[Encounter]] = relationship(back_populates="patient")
    documents: Mapped[list[ClinicalDocument]] = relationship(back_populates="patient")
    summaries: Mapped[list[Summary]] = relationship(back_populates="patient")


class Encounter(Base, TimestampMixin):
    __tablename__ = "encounters"

    encounter_id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    external_encounter_id: Mapped[str | None] = mapped_column(String(100), index=True)
    fhir_encounter_id: Mapped[str | None] = mapped_column(String(100), index=True)
    encounter_type: Mapped[str | None] = mapped_column(String(50))
    department: Mapped[str | None] = mapped_column(String(255))
    attending_doctor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(String(50))
    reason_for_visit: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str | None] = mapped_column(String(100))

    patient: Mapped[Patient] = relationship(back_populates="encounters")
    attending_doctor: Mapped[User | None] = relationship()
    documents: Mapped[list[ClinicalDocument]] = relationship(back_populates="encounter")
    summaries: Mapped[list[Summary]] = relationship(back_populates="encounter")


class ClinicalDocument(Base, TimestampMixin):
    __tablename__ = "clinical_documents"

    document_id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("encounters.encounter_id"), index=True
    )
    external_document_id: Mapped[str | None] = mapped_column(String(100), index=True)
    fhir_document_reference_id: Mapped[str | None] = mapped_column(String(100), index=True)
    fhir_composition_id: Mapped[str | None] = mapped_column(String(100), index=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_title: Mapped[str | None] = mapped_column(Text)
    document_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"))
    department: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text_hash: Mapped[str | None] = mapped_column(String(255))
    source_file_uri: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str | None] = mapped_column(String(100))
    confidentiality_level: Mapped[str | None] = mapped_column(String(50))

    patient: Mapped[Patient] = relationship(back_populates="documents")
    encounter: Mapped[Encounter | None] = relationship(back_populates="documents")
    author: Mapped[User | None] = relationship()
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base, CreatedAtMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
    )

    chunk_id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_documents.document_id"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.encounter_id"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_name: Mapped[str | None] = mapped_column(String(255))
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    embedding_id: Mapped[str | None] = mapped_column(String(255))
    vector_store: Mapped[str | None] = mapped_column(String(100))
    chunk_hash: Mapped[str | None] = mapped_column(String(255))

    document: Mapped[ClinicalDocument] = relationship(back_populates="chunks")


# Structured clinical records are included now so citations can preserve typed
# FHIR/HIS provenance while their API ingestion behavior remains Phase 2 work.
class Condition(Base, TimestampMixin):
    __tablename__ = "conditions"

    condition_id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.encounter_id"))
    external_condition_id: Mapped[str | None] = mapped_column(String(100))
    fhir_condition_id: Mapped[str | None] = mapped_column(String(100), index=True)
    condition_code: Mapped[str | None] = mapped_column(String(100))
    coding_system: Mapped[str | None] = mapped_column(String(100))
    condition_name: Mapped[str] = mapped_column(Text, nullable=False)
    clinical_status: Mapped[str | None] = mapped_column(String(50))
    verification_status: Mapped[str | None] = mapped_column(String(50))
    onset_date: Mapped[date | None] = mapped_column(Date)
    recorded_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clinical_documents.document_id")
    )
    source_system: Mapped[str | None] = mapped_column(String(100))


class Observation(Base, CreatedAtMixin):
    __tablename__ = "observations"

    observation_id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.encounter_id"))
    external_observation_id: Mapped[str | None] = mapped_column(String(100))
    fhir_observation_id: Mapped[str | None] = mapped_column(String(100), index=True)
    observation_type: Mapped[str | None] = mapped_column(String(50))
    observation_code: Mapped[str | None] = mapped_column(String(100))
    coding_system: Mapped[str | None] = mapped_column(String(100))
    observation_name: Mapped[str] = mapped_column(Text, nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(String(50))
    reference_range_low: Mapped[Decimal | None] = mapped_column(Numeric)
    reference_range_high: Mapped[Decimal | None] = mapped_column(Numeric)
    interpretation: Mapped[str | None] = mapped_column(String(50))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clinical_documents.document_id")
    )
    source_system: Mapped[str | None] = mapped_column(String(100))


class Medication(Base, TimestampMixin):
    __tablename__ = "medications"

    medication_id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.encounter_id"))
    external_medication_id: Mapped[str | None] = mapped_column(String(100))
    fhir_medication_request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    medication_name: Mapped[str] = mapped_column(Text, nullable=False)
    medication_code: Mapped[str | None] = mapped_column(String(100))
    coding_system: Mapped[str | None] = mapped_column(String(100))
    dosage_text: Mapped[str | None] = mapped_column(Text)
    route: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(50))
    medication_action: Mapped[str | None] = mapped_column(String(50))
    prescribed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clinical_documents.document_id")
    )
    source_system: Mapped[str | None] = mapped_column(String(100))


class DiagnosticReport(Base, CreatedAtMixin):
    __tablename__ = "diagnostic_reports"

    report_id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encounters.encounter_id"))
    external_report_id: Mapped[str | None] = mapped_column(String(100))
    fhir_diagnostic_report_id: Mapped[str | None] = mapped_column(String(100), index=True)
    report_type: Mapped[str | None] = mapped_column(String(100))
    report_title: Mapped[str | None] = mapped_column(Text)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    conclusion_text: Mapped[str | None] = mapped_column(Text)
    report_status: Mapped[str | None] = mapped_column(String(50))
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clinical_documents.document_id")
    )
    source_system: Mapped[str | None] = mapped_column(String(100))


class ModelRun(Base, CreatedAtMixin):
    __tablename__ = "model_runs"

    model_run_id: Mapped[uuid.UUID] = _uuid_pk()
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(100))
    prompt_template_id: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    summary_type: Mapped[str | None] = mapped_column(String(100))
    context_hash: Mapped[str | None] = mapped_column(String(255))
    output_hash: Mapped[str | None] = mapped_column(String(255))
    input_token_count: Mapped[int | None] = mapped_column(Integer)
    output_token_count: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(Text)
    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ModelJobRecord(Base, TimestampMixin):
    __tablename__ = "model_jobs"

    job_id: Mapped[uuid.UUID] = _uuid_pk()
    job_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_step: Mapped[str | None] = mapped_column(String(100))
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Summary(Base, TimestampMixin):
    __tablename__ = "summaries"

    summary_id: Mapped[uuid.UUID] = _uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("encounters.encounter_id"), index=True
    )
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_runs.model_run_id"))
    summary_type: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_language: Mapped[str] = mapped_column(String(20), nullable=False, default="vi")
    status: Mapped[SummaryStatus] = mapped_column(
        _workflow_enum(SummaryStatus, "summary_status"),
        nullable=False,
        default=SummaryStatus.DRAFT,
    )
    citation_coverage: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    unsupported_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_summary_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("summaries.summary_id"))
    context_hash: Mapped[str | None] = mapped_column(String(255))

    patient: Mapped[Patient] = relationship(back_populates="summaries")
    encounter: Mapped[Encounter | None] = relationship(back_populates="summaries")
    model_run: Mapped[ModelRun | None] = relationship()
    parent_summary: Mapped[Summary | None] = relationship(remote_side="Summary.summary_id")
    sections: Mapped[list[SummarySection]] = relationship(
        back_populates="summary", cascade="all, delete-orphan"
    )
    claims: Mapped[list[SummaryClaim]] = relationship(
        back_populates="summary", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[SummaryReview]] = relationship(
        back_populates="summary", cascade="all, delete-orphan"
    )
    human_evaluations: Mapped[list[HumanEvaluation]] = relationship(
        back_populates="summary", cascade="all, delete-orphan"
    )


class SummarySection(Base, CreatedAtMixin):
    __tablename__ = "summary_sections"
    __table_args__ = (
        UniqueConstraint("summary_id", "section_order", name="uq_summary_sections_order"),
    )

    section_id: Mapped[uuid.UUID] = _uuid_pk()
    summary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("summaries.summary_id"), nullable=False, index=True
    )
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_type: Mapped[str | None] = mapped_column(String(100))

    summary: Mapped[Summary] = relationship(back_populates="sections")
    claims: Mapped[list[SummaryClaim]] = relationship(back_populates="section")


class SummaryClaim(Base, TimestampMixin):
    __tablename__ = "summary_claims"
    __table_args__ = (
        UniqueConstraint("summary_id", "claim_order", name="uq_summary_claims_order"),
    )

    claim_id: Mapped[uuid.UUID] = _uuid_pk()
    summary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("summaries.summary_id"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("summary_sections.section_id"))
    claim_order: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str | None] = mapped_column(String(100))
    support_status: Mapped[ClaimSupportStatus] = mapped_column(
        _workflow_enum(ClaimSupportStatus, "claim_support_status"),
        nullable=False,
        default=ClaimSupportStatus.UNCHECKED,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    clinical_risk_level: Mapped[str | None] = mapped_column(String(50))

    summary: Mapped[Summary] = relationship(back_populates="claims")
    section: Mapped[SummarySection | None] = relationship(back_populates="claims")
    citations: Mapped[list[ClaimCitation]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimCitation(Base, CreatedAtMixin):
    __tablename__ = "claim_citations"
    __table_args__ = (
        CheckConstraint(
            "source_document_id IS NOT NULL OR source_chunk_id IS NOT NULL "
            "OR source_condition_id IS NOT NULL OR source_observation_id IS NOT NULL "
            "OR source_medication_id IS NOT NULL OR source_report_id IS NOT NULL "
            "OR source_record_id IS NOT NULL",
            name="ck_claim_citations_source_required",
        ),
    )

    citation_id: Mapped[uuid.UUID] = _uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("summary_claims.claim_id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clinical_documents.document_id")
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_chunks.chunk_id"))
    source_condition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conditions.condition_id"))
    source_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("observations.observation_id")
    )
    source_medication_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("medications.medication_id")
    )
    source_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("diagnostic_reports.report_id")
    )
    source_record_type: Mapped[str | None] = mapped_column(String(100))
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_text_span: Mapped[str | None] = mapped_column(Text)
    source_char_start: Mapped[int | None] = mapped_column(Integer)
    source_char_end: Mapped[int | None] = mapped_column(Integer)
    citation_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    claim: Mapped[SummaryClaim] = relationship(back_populates="citations")


class SummaryReview(Base, CreatedAtMixin):
    __tablename__ = "summary_reviews"

    review_id: Mapped[uuid.UUID] = _uuid_pk()
    summary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("summaries.summary_id"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    action: Mapped[ReviewAction] = mapped_column(
        _workflow_enum(ReviewAction, "review_action"), nullable=False
    )
    previous_status: Mapped[SummaryStatus | None] = mapped_column(
        _workflow_enum(SummaryStatus, "review_previous_summary_status")
    )
    resulting_status: Mapped[SummaryStatus | None] = mapped_column(
        _workflow_enum(SummaryStatus, "review_resulting_summary_status")
    )
    comment: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(String(100))
    edited_summary_text: Mapped[str | None] = mapped_column(Text)
    edit_distance_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    summary: Mapped[Summary] = relationship(back_populates="reviews")
    reviewer: Mapped[User] = relationship()


class HumanEvaluation(Base, CreatedAtMixin):
    __tablename__ = "human_evaluations"
    __table_args__ = (
        CheckConstraint(
            "factual_correctness_score BETWEEN 1 AND 5",
            name="ck_human_eval_factual_score_range",
        ),
        CheckConstraint(
            "completeness_score BETWEEN 1 AND 5",
            name="ck_human_eval_completeness_score_range",
        ),
        CheckConstraint(
            "conciseness_score BETWEEN 1 AND 5",
            name="ck_human_eval_conciseness_score_range",
        ),
        CheckConstraint(
            "readability_score BETWEEN 1 AND 5",
            name="ck_human_eval_readability_score_range",
        ),
        CheckConstraint(
            "citation_usefulness_score BETWEEN 1 AND 5",
            name="ck_human_eval_citation_score_range",
        ),
        CheckConstraint(
            "hallucination_risk IN ('low', 'medium', 'high')",
            name="ck_human_eval_hallucination_risk",
        ),
    )

    evaluation_id: Mapped[uuid.UUID] = _uuid_pk()
    summary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("summaries.summary_id"), nullable=False, index=True
    )
    evaluator_id: Mapped[str | None] = mapped_column(String(100))
    evaluator_name: Mapped[str | None] = mapped_column(String(255))
    model_provider: Mapped[str | None] = mapped_column(String(100))
    factual_correctness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    completeness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    conciseness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    readability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    citation_usefulness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    hallucination_risk: Mapped[str] = mapped_column(String(20), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)

    summary: Mapped[Summary] = relationship(back_populates="human_evaluations")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"), index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.patient_id"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    ip_address: Mapped[str | None] = mapped_column(String(100))
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index("idx_summaries_patient_status", Summary.patient_id, Summary.status)
Index("idx_audit_logs_timestamp", AuditLog.timestamp)
Index("idx_model_jobs_created_status", ModelJobRecord.created_at, ModelJobRecord.status)
