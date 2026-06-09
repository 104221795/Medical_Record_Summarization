from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PersistenceModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", from_attributes=True)


class FhirIdentifierIn(PersistenceModel):
    system: str | None = None
    value: str = Field(min_length=1, max_length=100)


class FhirReferenceIn(PersistenceModel):
    reference: str = Field(min_length=1, max_length=255)


class FhirCodingIn(PersistenceModel):
    system: str | None = None
    code: str | None = None
    display: str | None = None


class FhirConceptIn(PersistenceModel):
    coding: list[FhirCodingIn] = Field(default_factory=list)
    text: str | None = None


class FhirPeriodIn(PersistenceModel):
    start: datetime | None = None
    end: datetime | None = None


class FhirPatientImport(PersistenceModel):
    resource_type: Literal["Patient"] = Field("Patient", alias="resourceType")
    id: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: list[FhirIdentifierIn] = Field(min_length=1)
    gender: str | None = Field(default=None, max_length=30)
    birth_date: date | None = Field(default=None, alias="birthDate")
    patient_hash: str | None = Field(default=None, max_length=255)
    is_deidentified: bool = True


class FhirEncounterImport(PersistenceModel):
    resource_type: Literal["Encounter"] = Field("Encounter", alias="resourceType")
    id: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: list[FhirIdentifierIn] = Field(min_length=1)
    subject: FhirReferenceIn
    status: str | None = Field(default=None, max_length=50)
    class_: FhirCodingIn | None = Field(default=None, alias="class")
    period: FhirPeriodIn | None = None
    reason_code: FhirConceptIn | None = Field(default=None, alias="reasonCode")
    department: str | None = Field(default=None, max_length=255)


class FhirConditionImport(PersistenceModel):
    resource_type: Literal["Condition"] = Field("Condition", alias="resourceType")
    id: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: list[FhirIdentifierIn] = Field(default_factory=list)
    subject: FhirReferenceIn
    encounter: FhirReferenceIn | None = None
    code: FhirConceptIn
    clinical_status: FhirConceptIn | None = Field(default=None, alias="clinicalStatus")
    verification_status: FhirConceptIn | None = Field(default=None, alias="verificationStatus")
    onset_date_time: datetime | None = Field(default=None, alias="onsetDateTime")
    recorded_date: datetime | None = Field(default=None, alias="recordedDate")

    @model_validator(mode="after")
    def require_name(self) -> "FhirConditionImport":
        if not self.code.text and not any(item.display for item in self.code.coding):
            raise ValueError("Condition code requires text or coding display.")
        return self


class ObservationValueQuantityIn(PersistenceModel):
    value: Decimal
    unit: str | None = Field(default=None, max_length=50)


class FhirObservationImport(PersistenceModel):
    resource_type: Literal["Observation"] = Field("Observation", alias="resourceType")
    id: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: list[FhirIdentifierIn] = Field(default_factory=list)
    subject: FhirReferenceIn
    encounter: FhirReferenceIn | None = None
    category: list[FhirConceptIn] = Field(default_factory=list)
    code: FhirConceptIn
    value_quantity: ObservationValueQuantityIn | None = Field(default=None, alias="valueQuantity")
    value_string: str | None = Field(default=None, alias="valueString", max_length=10000)
    interpretation: list[FhirConceptIn] = Field(default_factory=list)
    effective_date_time: datetime | None = Field(default=None, alias="effectiveDateTime")

    @model_validator(mode="after")
    def require_value_and_name(self) -> "FhirObservationImport":
        if not self.code.text and not any(item.display for item in self.code.coding):
            raise ValueError("Observation code requires text or coding display.")
        if self.value_quantity is None and self.value_string is None:
            raise ValueError("Observation requires valueQuantity or valueString.")
        return self


class FhirDosageInstructionIn(PersistenceModel):
    text: str | None = None
    route: FhirConceptIn | None = None


class FhirMedicationImport(PersistenceModel):
    resource_type: Literal["MedicationRequest", "MedicationStatement"] = Field(alias="resourceType")
    id: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: list[FhirIdentifierIn] = Field(default_factory=list)
    subject: FhirReferenceIn
    encounter: FhirReferenceIn | None = None
    medication: FhirConceptIn = Field(alias="medicationCodeableConcept")
    dosage_instruction: list[FhirDosageInstructionIn] = Field(
        default_factory=list, alias="dosageInstruction"
    )
    authored_on: date | None = Field(default=None, alias="authoredOn")
    status: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def require_medication_name(self) -> "FhirMedicationImport":
        if not self.medication.text and not any(item.display for item in self.medication.coding):
            raise ValueError("Medication requires text or coding display.")
        return self


class FhirDiagnosticReportImport(PersistenceModel):
    resource_type: Literal["DiagnosticReport"] = Field("DiagnosticReport", alias="resourceType")
    id: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: list[FhirIdentifierIn] = Field(default_factory=list)
    subject: FhirReferenceIn
    encounter: FhirReferenceIn | None = None
    status: str | None = Field(default=None, max_length=50)
    category: list[FhirConceptIn] = Field(default_factory=list)
    code: FhirConceptIn | None = None
    conclusion: str | None = None
    report_text: str | None = Field(default=None, min_length=1)
    effective_date_time: datetime | None = Field(default=None, alias="effectiveDateTime")
    issued: datetime | None = None

    @model_validator(mode="after")
    def require_report_text(self) -> "FhirDiagnosticReportImport":
        if not self.report_text and not self.conclusion:
            raise ValueError("DiagnosticReport requires report_text or conclusion.")
        return self


class FhirDocumentContextIn(PersistenceModel):
    encounter: list[FhirReferenceIn] = Field(default_factory=list)


class FhirDocumentImport(PersistenceModel):
    resource_type: Literal["DocumentReference", "Composition", "ClinicalDocument"] = Field(
        alias="resourceType"
    )
    id: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: list[FhirIdentifierIn] = Field(default_factory=list)
    subject: FhirReferenceIn
    encounter: FhirReferenceIn | None = None
    context: FhirDocumentContextIn | None = None
    document_type: str | None = Field(default=None, max_length=100)
    type: FhirConceptIn | None = None
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=500)
    date: datetime | None = None
    raw_text: str = Field(min_length=1, max_length=1_000_000)
    source_file_uri: str | None = Field(default=None, max_length=1000)
    confidentiality_level: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def require_document_type(self) -> "FhirDocumentImport":
        concept_text = self.type.text if self.type else None
        if not self.document_type and not concept_text:
            raise ValueError("Clinical document requires document_type or type.text.")
        return self

    def encounter_reference(self) -> FhirReferenceIn | None:
        if self.encounter:
            return self.encounter
        if self.context and self.context.encounter:
            return self.context.encounter[0]
        return None


class FhirLikeRecords(PersistenceModel):
    patients: list[FhirPatientImport] = Field(default_factory=list)
    encounters: list[FhirEncounterImport] = Field(default_factory=list)
    conditions: list[FhirConditionImport] = Field(default_factory=list)
    observations: list[FhirObservationImport] = Field(default_factory=list)
    medications: list[FhirMedicationImport] = Field(default_factory=list)
    diagnostic_reports: list[FhirDiagnosticReportImport] = Field(default_factory=list)
    documents: list[FhirDocumentImport] = Field(default_factory=list)

    def total_records(self) -> int:
        return sum(len(value) for value in self.__dict__.values() if isinstance(value, list))


class FhirLikeImportRequest(PersistenceModel):
    source_system: str = Field(min_length=1, max_length=100)
    ingestion_type: Literal["fhir_like_json"] = "fhir_like_json"
    records: FhirLikeRecords | None = None
    patients: list[FhirPatientImport] = Field(default_factory=list)
    encounters: list[FhirEncounterImport] = Field(default_factory=list)
    conditions: list[FhirConditionImport] = Field(default_factory=list)
    observations: list[FhirObservationImport] = Field(default_factory=list)
    medications: list[FhirMedicationImport] = Field(default_factory=list)
    diagnostic_reports: list[FhirDiagnosticReportImport] = Field(default_factory=list)
    documents: list[FhirDocumentImport] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "FhirLikeImportRequest":
        flat = FhirLikeRecords(
            patients=self.patients,
            encounters=self.encounters,
            conditions=self.conditions,
            observations=self.observations,
            medications=self.medications,
            diagnostic_reports=self.diagnostic_reports,
            documents=self.documents,
        )
        if self.records and flat.total_records():
            raise ValueError("Provide either records or top-level resource lists, not both.")
        resource_records = self.records or flat
        if resource_records.total_records() == 0:
            raise ValueError("Import payload does not contain records.")
        return self

    def resources(self) -> FhirLikeRecords:
        return self.records or FhirLikeRecords(
            patients=self.patients,
            encounters=self.encounters,
            conditions=self.conditions,
            observations=self.observations,
            medications=self.medications,
            diagnostic_reports=self.diagnostic_reports,
            documents=self.documents,
        )


class PaginationResponse(PersistenceModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PatientListItem(PersistenceModel):
    patient_id: uuid.UUID
    external_patient_id: str | None
    patient_hash: str | None
    gender: str | None
    fhir_patient_id: str | None
    source_system: str | None
    is_deidentified: bool


class PatientListResponse(PersistenceModel):
    items: list[PatientListItem]
    pagination: PaginationResponse


class PatientDetailResponse(PatientListItem):
    date_of_birth: date | None
    created_at: datetime
    updated_at: datetime


class EncounterResponse(PersistenceModel):
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    external_encounter_id: str | None
    fhir_encounter_id: str | None
    encounter_type: str | None
    department: str | None
    attending_doctor_id: uuid.UUID | None
    start_time: datetime | None
    end_time: datetime | None
    status: str | None
    reason_for_visit: str | None
    source_system: str | None


class EncounterListResponse(PersistenceModel):
    items: list[EncounterResponse]


class DocumentListItem(PersistenceModel):
    document_id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    external_document_id: str | None
    fhir_document_reference_id: str | None
    fhir_composition_id: str | None
    document_type: str
    document_title: str | None
    document_datetime: datetime | None
    department: str | None
    source_system: str | None


class DocumentListResponse(PersistenceModel):
    items: list[DocumentListItem]


class DocumentDetailResponse(DocumentListItem):
    raw_text: str
    raw_text_hash: str | None
    source_file_uri: str | None
    confidentiality_level: str | None


class DocumentChunkResponse(PersistenceModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    section_name: str | None
    chunk_text: str
    token_count: int | None
    char_start: int | None
    char_end: int | None
    chunk_hash: str | None


class DocumentChunkListResponse(PersistenceModel):
    items: list[DocumentChunkResponse]


class ImportResponse(PersistenceModel):
    ingestion_batch_id: uuid.UUID
    status: Literal["completed"] = "completed"
    total_records: int
    accepted_records: int
    skipped_duplicates: int
    failed_records: int = 0
    chunks_created: int


class AuditLogResponse(PersistenceModel):
    audit_id: uuid.UUID
    user_id: uuid.UUID | None
    user_display_name: str | None = None
    patient_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    metadata: dict | None = Field(default=None, validation_alias="metadata_json")
    action_metadata: dict | None = None
    ip_address: str | None = None
    timestamp: datetime
    created_at: datetime


class AuditLogListResponse(PersistenceModel):
    items: list[AuditLogResponse]
    pagination: PaginationResponse


class AuthLoginRequest(PersistenceModel):
    user_id: str | None = Field(default=None, min_length=2, max_length=128)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    role: Literal["doctor", "admin"] = "doctor"
    tenant_id: str = Field(default="sandbox", min_length=1, max_length=128)


class AuthGoogleLoginRequest(PersistenceModel):
    credential: str = Field(min_length=20, max_length=8192)
    role: Literal["doctor", "admin"] = "doctor"
    tenant_id: str = Field(default="sandbox", min_length=1, max_length=128)


class AuthSignupRequest(PersistenceModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=10, max_length=255)
    confirm_password: str = Field(min_length=10, max_length=255)
    role: Literal["doctor", "admin"] = "doctor"
    tenant_id: str = Field(default="sandbox", min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_password_match(self) -> "AuthSignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("password and confirm_password must match.")
        if "@" not in self.email or "." not in self.email.rsplit("@", 1)[-1]:
            raise ValueError("email must be a valid email address.")
        if not _password_policy_errors(self.password) == []:
            raise ValueError("password must be at least 10 characters and include uppercase, lowercase, number, and symbol.")
        return self


class AuthSessionResponse(PersistenceModel):
    authenticated: bool
    user_id: str
    full_name: str
    email: str | None = None
    role: Literal["doctor", "admin"]
    role_code: str
    tenant_id: str
    token: str
    message: str
    google_client_id_configured: bool = False


class AuthLogoutResponse(PersistenceModel):
    authenticated: bool = False
    message: str


class AuthConfigResponse(PersistenceModel):
    google_client_id_configured: bool
    google_client_id: str | None = None
    auth_mode: str


def _password_policy_errors(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 10:
        errors.append("minimum_length")
    if not any(char.islower() for char in password):
        errors.append("lowercase")
    if not any(char.isupper() for char in password):
        errors.append("uppercase")
    if not any(char.isdigit() for char in password):
        errors.append("number")
    if not any(not char.isalnum() for char in password):
        errors.append("symbol")
    return errors


class MetricCountItem(PersistenceModel):
    key: str
    count: int


class SafetyGateItem(PersistenceModel):
    name: str
    status: Literal["pass", "warning", "fail", "not_available"]
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    explanation: str | None = None


class SafetyGateResponse(PersistenceModel):
    mvp_readiness_status: Literal["pass", "warning", "fail"]
    gates: list[SafetyGateItem]


class SummaryQualityMetricsResponse(PersistenceModel):
    total_summaries: int
    draft_count: int
    under_review_count: int
    edited_count: int
    approved_count: int
    rejected_count: int
    archived_count: int
    approval_rate: float
    rejection_rate: float
    average_citation_coverage: float | None
    average_unsupported_claim_count: float | None
    average_conflict_count: float | None
    average_edit_distance: float | None
    critical_unsupported_claim_count: int
    summaries_by_type: list[MetricCountItem]
    top_rejection_reasons: list[MetricCountItem]


class UsageMetricsResponse(PersistenceModel):
    total_patients: int
    total_encounters: int
    total_documents: int
    total_document_chunks: int
    total_summaries_generated: int
    summaries_generated_today: int
    active_users: int | None
    most_active_roles: list[MetricCountItem]
    average_generation_latency_ms: float | None
    model_run_count: int


class SafetyMetricsResponse(PersistenceModel):
    citation_coverage_average: float | None
    unsupported_claim_total: int
    unsupported_claim_rate: float | None
    conflicting_claim_total: int
    weak_citation_count: int
    missing_citation_count: int
    critical_hallucination_proxy_count: int
    wrong_patient_retrieval_count: int | str
    safety_gate_status: SafetyGateResponse


class ReviewMetricsResponse(PersistenceModel):
    total_reviews: int
    approvals: int
    rejections: int
    edits: int
    average_edit_distance: float | None
    average_time_to_review_hours: float | None
    rejection_reasons_distribution: list[MetricCountItem]
    reviewer_activity: list[MetricCountItem]


class EvaluationProviderStatus(PersistenceModel):
    provider: str
    configured: bool
    enabled: bool
    status: str
    model_name: str | None = None
    last_run_status: str | None = None
    latency_ms: int | None = None
    message: str | None = None


class EvaluationReadinessItem(PersistenceModel):
    name: str
    status: str
    message: str | None = None


class EvaluationLayerStatus(PersistenceModel):
    layer: str
    status: str
    message: str
    expected_path: str | None = None


class EvaluationStatusResponse(PersistenceModel):
    provider_readiness: list[EvaluationProviderStatus]
    golden_path_readiness: str
    citation_readiness: str
    safety_readiness: str
    hitl_readiness: str
    audit_readiness: str
    metrics_readiness: str
    evaluation_layers: list[EvaluationLayerStatus]


class DemoReadinessResponse(PersistenceModel):
    golden_path: list[EvaluationReadinessItem]
    provider_readiness: list[EvaluationProviderStatus]
    evaluation_layers: list[EvaluationLayerStatus]
    message: str


class FunctionalValidationCheck(PersistenceModel):
    name: str
    status: Literal["passed", "failed", "not_tested"]
    message: str


class FunctionalValidationResponse(PersistenceModel):
    status: Literal["passed", "failed", "partial", "runnable"]
    checks: list[FunctionalValidationCheck]
    message: str


class BenchmarkStatusResponse(PersistenceModel):
    status: str
    message: str
    dataset_path: str
    dataset_exists: bool
    schema_valid: bool | None = None
    benchmark_runner_exists: bool
    model_comparison_output_path: str
    model_comparison_output_exists: bool


class HumanEvaluationCreateRequest(PersistenceModel):
    summary_id: uuid.UUID
    evaluator_name: str | None = Field(default=None, max_length=255)
    evaluator_id: str | None = Field(default=None, max_length=100)
    model_provider: str | None = Field(default=None, max_length=100)
    factual_correctness_score: int = Field(ge=1, le=5)
    completeness_score: int = Field(ge=1, le=5)
    conciseness_score: int = Field(ge=1, le=5)
    readability_score: int = Field(ge=1, le=5)
    citation_usefulness_score: int = Field(ge=1, le=5)
    hallucination_risk: Literal["low", "medium", "high"]
    comments: str | None = Field(default=None, max_length=5000)


class HumanEvaluationResponse(PersistenceModel):
    evaluation_id: uuid.UUID
    summary_id: uuid.UUID
    evaluator_name: str | None
    evaluator_id: str | None
    model_provider: str | None
    factual_correctness_score: int
    completeness_score: int
    conciseness_score: int
    readability_score: int
    citation_usefulness_score: int
    hallucination_risk: str
    comments: str | None
    created_at: datetime


class HumanEvaluationSummaryResponse(PersistenceModel):
    total_evaluations: int
    average_factual_correctness_score: float | None
    average_completeness_score: float | None
    average_conciseness_score: float | None
    average_readability_score: float | None
    average_citation_usefulness_score: float | None
    hallucination_risk_distribution: list[MetricCountItem]
    evaluations_by_provider: list[MetricCountItem]
    recent_evaluations: list[HumanEvaluationResponse]


class HumanEvaluationListResponse(PersistenceModel):
    summary_id: uuid.UUID
    evaluations: list[HumanEvaluationResponse]


class SummaryGenerateOptions(PersistenceModel):
    require_citations: bool = True
    include_safety_check: bool = True


SummaryProviderName = Literal[
    "deterministic",
    "gemini",
    "bart",
    "pegasus",
    "pegasus_pubmed",
    "pegasus_cnn_dailymail",
    "pegasus_xsum",
]


class ProviderInfo(PersistenceModel):
    provider_name: str
    display_name: str
    model_name: str
    provider_type: str
    status: str
    requires_api_key: bool
    local_model: bool
    domain_fit: str
    description: str


class ProviderListResponse(PersistenceModel):
    providers: list[ProviderInfo]


class BenchmarkResultRow(PersistenceModel):
    model_provider: str
    model_name: str
    status: str
    record_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    rouge1: float | None = None
    rouge2: float | None = None
    rougeL: float | None = None
    bertscore_precision: float | None = None
    bertscore_recall: float | None = None
    bertscore_f1: float | None = None
    bertscore_status: str | None = None
    bertscore_model_type: str | None = None
    average_latency_ms: float | None = None
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    citation_coverage: float | None = None
    unsupported_claim_rate: float | None = None
    factuality_proxy_score: float | None = None
    missing_diagnosis_rate: float | None = None
    missing_medication_rate: float | None = None
    timeline_completeness: float | None = None
    hallucinated_clinical_entity_count: float | None = None
    critical_info_omission_rate: float | None = None
    stage_name: str | None = None
    checkpoint: str | None = None
    provider_type: str | None = None
    domain_fit: str | None = None
    total_runtime_seconds: float | None = None
    failure_counts: dict[str, int] | None = None
    notes: str | None = None
    error_message: str | None = None


class BenchmarkResultsResponse(PersistenceModel):
    output_dir: str
    selected_output_dir: str | None = None
    benchmark_type: str | None = None
    discovered_benchmark_folders: list[dict[str, Any]] = Field(default_factory=list)
    models: list[BenchmarkResultRow]
    per_record_metric_summary: dict[str, Any] = Field(default_factory=dict)
    clinical_metric_summary: dict[str, Any] = Field(default_factory=dict)
    per_record_failure_examples: list[dict[str, Any]] = Field(default_factory=list)
    prediction_file_availability: dict[str, Any] = Field(default_factory=dict)
    failure_analysis_summary: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: dict[str, str | None] = Field(default_factory=dict)
    data_freshness_timestamp: str | None = None
    best_model_by_rougeL: str | None = None
    report_path: str
    failure_analysis_path: str
    report_exists: bool
    failure_analysis_exists: bool
    proxy_warning: str


class ModelJobCreateRequest(PersistenceModel):
    job_type: Literal["summarization_generation", "model_warmup"] = "model_warmup"
    model_provider: str = Field(default="bart", min_length=1, max_length=100)
    model_name: str = Field(default="facebook/bart-large-cnn", min_length=1, max_length=255)
    timeout_seconds: int = Field(default=900, ge=1, le=24 * 60 * 60)
    payload: dict[str, Any] = Field(default_factory=dict)


class ModelJobResponse(PersistenceModel):
    job_id: str
    job_type: str
    model_provider: str
    model_name: str
    status: Literal["queued", "running", "completed", "failed", "cancelled", "timed_out"]
    progress: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    timeout_seconds: int
    result: dict[str, Any] | None = None
    error_message: str | None = None


class ModelJobListResponse(PersistenceModel):
    jobs: list[ModelJobResponse]


class ModelReadinessResponse(PersistenceModel):
    cache_paths: dict[str, str | None]
    models: list[dict[str, Any]]


class SummaryGenerateRequest(PersistenceModel):
    encounter_id: uuid.UUID | None = None
    summary_type: Literal["patient_snapshot"] = "patient_snapshot"
    language: str = Field(default="vi", min_length=2, max_length=20)
    provider: SummaryProviderName | None = None
    model_provider: SummaryProviderName | None = None
    options: SummaryGenerateOptions = Field(default_factory=SummaryGenerateOptions)

    @model_validator(mode="after")
    def normalize_provider_aliases(self) -> "SummaryGenerateRequest":
        if self.provider and self.model_provider and self.provider != self.model_provider:
            raise ValueError("provider and model_provider must match when both are supplied.")
        selected = self.model_provider or self.provider
        self.model_provider = selected
        self.provider = selected
        return self


class SummaryGenerateResponse(PersistenceModel):
    summary_id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    summary_type: str
    status: str
    model_provider: str | None = None
    model_name: str | None = None
    latency_ms: int | None = None
    citation_coverage: Decimal | None
    unsupported_claim_count: int
    conflict_count: int
    generated_at: datetime


class SummarySafetyResponse(PersistenceModel):
    citation_coverage: Decimal | None
    unsupported_claim_count: int
    conflict_count: int
    total_claim_count: int
    supported_claim_count: int


class ClaimCitationResponse(PersistenceModel):
    citation_id: uuid.UUID
    claim_id: uuid.UUID
    source_type: str
    source_document_id: uuid.UUID | None
    source_chunk_id: uuid.UUID | None
    source_condition_id: uuid.UUID | None
    source_observation_id: uuid.UUID | None
    source_medication_id: uuid.UUID | None
    source_report_id: uuid.UUID | None
    source_record_type: str | None
    source_record_id: uuid.UUID | None
    source_text_span: str | None
    source_char_start: int | None
    source_char_end: int | None
    citation_confidence: Decimal | None


class SummaryClaimResponse(PersistenceModel):
    claim_id: uuid.UUID
    summary_id: uuid.UUID
    section_id: uuid.UUID | None
    claim_order: int
    claim_text: str
    claim_type: str | None
    support_status: str
    confidence_score: Decimal | None
    clinical_risk_level: str | None
    citation_count: int
    citations: list[ClaimCitationResponse] = Field(default_factory=list)


class SummarySectionResponse(PersistenceModel):
    section_id: uuid.UUID
    summary_id: uuid.UUID
    section_order: int
    section_title: str
    section_text: str
    section_type: str | None
    claims: list[SummaryClaimResponse] = Field(default_factory=list)


class SummaryDetailResponse(PersistenceModel):
    summary_id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    summary_type: str
    summary_text: str
    summary_language: str
    status: str
    model_provider: str | None = None
    model_name: str | None = None
    latency_ms: int | None = None
    version_number: int
    parent_summary_id: uuid.UUID | None
    citation_coverage: Decimal | None
    unsupported_claim_count: int
    conflict_count: int
    generated_at: datetime
    reviewed_by: uuid.UUID | None = None
    approved_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    latest_edited_summary_text: str | None = None
    latest_review_comment: str | None = None
    latest_edit_distance_score: Decimal | None = None
    citation_revalidation_required: bool = False
    sections: list[SummarySectionResponse]
    safety_summary: SummarySafetyResponse


class ClaimCitationListResponse(PersistenceModel):
    claim_id: uuid.UUID
    citations: list[ClaimCitationResponse]


class CitationDocumentMetadata(PersistenceModel):
    document_id: uuid.UUID
    document_title: str | None
    document_type: str | None
    document_datetime: datetime | None
    source_system: str | None


class CitationHighlightedSpan(PersistenceModel):
    text: str | None
    char_start: int | None
    char_end: int | None


class CitationSourceResponse(PersistenceModel):
    citation_id: uuid.UUID
    claim_id: uuid.UUID
    patient_id: uuid.UUID
    source_type: str
    document: CitationDocumentMetadata | None = None
    highlighted_span: CitationHighlightedSpan | None = None
    surrounding_context: str | None = None
    source_metadata: dict | None = None


class SummaryRegenerateRequest(PersistenceModel):
    reason: str | None = Field(default=None, max_length=1000)
    options: SummaryGenerateOptions = Field(default_factory=SummaryGenerateOptions)


class SummaryRegenerateResponse(PersistenceModel):
    old_summary_id: uuid.UUID
    new_summary_id: uuid.UUID
    status: str
    version_number: int


class SummaryReviewStartResponse(PersistenceModel):
    summary_id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    previous_status: str | None
    reviewed_by: uuid.UUID
    reviewed_at: datetime
    review_id: uuid.UUID


class SummaryEditRequest(PersistenceModel):
    edited_summary_text: str = Field(min_length=1, max_length=200_000)
    edit_comment: str | None = Field(default=None, max_length=2000)


class SummaryApproveRequest(PersistenceModel):
    approval_comment: str | None = Field(default=None, max_length=2000)


class SummaryRejectRequest(PersistenceModel):
    rejection_reason: Literal[
        "unsupported_claim",
        "wrong_citation",
        "missing_critical_info",
        "incorrect_clinical_fact",
        "conflicting_evidence",
        "poor_readability",
        "too_generic",
        "unsafe_output",
        "other",
    ]
    rejection_comment: str = Field(min_length=1, max_length=2000)


class SummaryReviewActionResponse(PersistenceModel):
    summary_id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    previous_status: str | None
    reviewed_by: uuid.UUID
    reviewed_at: datetime
    review_id: uuid.UUID
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    edit_distance_score: Decimal | None = None
    citation_revalidation_required: bool = False
    final_locked: bool = False
    reviewer_signature: str | None = None
    audit_trail_ready: bool = True


class SummaryReviewResponse(PersistenceModel):
    review_id: uuid.UUID
    summary_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_role: str | None = None
    review_action: str
    previous_status: str | None
    resulting_status: str | None
    comment: str | None
    rejection_reason: str | None
    edited_summary_text: str | None
    edit_distance_score: Decimal | None
    reviewed_at: datetime
    reviewer_signature: str | None = None
    audit_trail_ready: bool = True


class SummaryReviewListResponse(PersistenceModel):
    summary_id: uuid.UUID
    reviews: list[SummaryReviewResponse]


class DemoSeedResponse(PersistenceModel):
    patient_id: uuid.UUID
    encounter_id: uuid.UUID
    summary_id: uuid.UUID
    created: bool
    message: str
