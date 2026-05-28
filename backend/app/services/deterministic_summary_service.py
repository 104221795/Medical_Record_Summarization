from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..config import Settings
from ..models import (
    ClaimCitation,
    ClaimSupportStatus,
    ClinicalDocument,
    Condition,
    DiagnosticReport,
    DocumentChunk,
    Encounter,
    Medication,
    ModelRun,
    Observation,
    Patient,
    Summary,
    SummaryClaim,
    SummarySection,
    SummaryStatus,
)
from ..persistence_schemas import (
    ClaimCitationResponse,
    SummaryClaimResponse,
    SummaryDetailResponse,
    SummaryGenerateRequest,
    SummaryGenerateResponse,
    SummaryRegenerateRequest,
    SummaryRegenerateResponse,
    SummarySafetyResponse,
    SummarySectionResponse,
)
from ..repositories import SummaryRepository
from .audit_service import AuditService
from .generators import GeminiJsonClient, GenerationError
from .persistence_common import PersistedResourceNotFoundError
from .safety_service import SafetyResult, SafetyService


MISSING_INFORMATION = "Không tìm thấy thông tin trong dữ liệu hiện có."


class SummaryGenerationError(ValueError):
    pass


class GeminiPersistedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_text: str = Field(min_length=1, max_length=5000)
    claim_type: Literal[
        "encounter_context",
        "diagnosis",
        "medication",
        "lab_result",
        "vital_sign",
        "timeline_event",
        "imaging_finding",
        "follow_up",
        "missing_information",
        "allergy",
        "procedure",
        "general",
    ] = "general"
    support_status: Literal[
        "supported",
        "unsupported",
        "conflicting",
        "insufficient_evidence",
        "unchecked",
    ]
    citation_ids: list[str] = Field(default_factory=list)
    clinical_risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1)


class GeminiPersistedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_title: str = Field(min_length=1, max_length=255)
    section_type: str = Field(min_length=1, max_length=100)
    section_order: int = Field(ge=1)
    claims: list[GeminiPersistedClaim] = Field(default_factory=list)


class GeminiPersistedSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_type: Literal["patient_snapshot"]
    language: str = Field(min_length=2, max_length=20)
    requires_clinician_review: bool
    sections: list[GeminiPersistedSection] = Field(min_length=1)
    safety_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_doctor_review(self) -> "GeminiPersistedSummary":
        if not self.requires_clinician_review:
            raise ValueError("Gemini output must declare requires_clinician_review=true.")
        return self


@dataclass
class CitationDraft:
    source_type: str
    source_text_span: str | None = None
    source_char_start: int | None = None
    source_char_end: int | None = None
    source_document_id: uuid.UUID | None = None
    source_chunk_id: uuid.UUID | None = None
    source_condition_id: uuid.UUID | None = None
    source_observation_id: uuid.UUID | None = None
    source_medication_id: uuid.UUID | None = None
    source_report_id: uuid.UUID | None = None
    source_record_type: str | None = None
    source_record_id: uuid.UUID | None = None
    citation_confidence: Decimal = Decimal("0.95")


@dataclass
class ClaimDraft:
    text: str
    claim_type: str
    support_status: ClaimSupportStatus
    clinical_risk_level: str
    citations: list[CitationDraft] = field(default_factory=list)
    confidence_score: Decimal | None = None


@dataclass
class SectionDraft:
    title: str
    section_type: str
    claims: list[ClaimDraft] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(f"- {claim.text}" for claim in self.claims) or MISSING_INFORMATION


class DeterministicSummaryService:
    """Generate a source-grounded draft summary without calling an LLM."""

    REQUIRED_SECTIONS = [
        ("Patient Snapshot", "patient_snapshot"),
        ("Active Problems", "active_problems"),
        ("Recent Clinical Course", "recent_clinical_course"),
        ("Medications", "medications"),
        ("Labs and Imaging Highlights", "labs_imaging"),
        ("Needs Clinician Review", "needs_clinician_review"),
    ]

    def __init__(
        self,
        repository: SummaryRepository,
        safety_service: SafetyService,
        audit_service: AuditService,
        settings: Settings | None = None,
        gemini_client: GeminiJsonClient | None = None,
    ):
        self.repository = repository
        self.safety_service = safety_service
        self.audit_service = audit_service
        self.settings = settings
        self.gemini_client = gemini_client

    def generate(
        self,
        patient_id: str,
        request: SummaryGenerateRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
    ) -> SummaryGenerateResponse:
        return self._generate(
            patient_id,
            request,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            audit_action="generate_summary",
            parent_summary_id=None,
            version_number=1,
            regeneration_reason=None,
        )

    def regenerate(
        self,
        summary_id: str,
        request: SummaryRegenerateRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
    ) -> SummaryRegenerateResponse:
        existing = self.get_summary_model(summary_id)
        next_version = self.repository.next_version(
            existing.patient_id,
            existing.encounter_id,
            existing.summary_type,
        )
        generate_request = SummaryGenerateRequest(
            encounter_id=existing.encounter_id,
            summary_type="patient_snapshot",
            language=existing.summary_language,
            options=request.options,
        )
        generated = self._generate(
            str(existing.patient_id),
            generate_request,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            audit_action="regenerate_summary",
            parent_summary_id=existing.summary_id,
            version_number=next_version,
            regeneration_reason=request.reason,
        )
        return SummaryRegenerateResponse(
            old_summary_id=existing.summary_id,
            new_summary_id=generated.summary_id,
            status=generated.status,
            version_number=next_version,
        )

    def detail(self, summary_id: str) -> SummaryDetailResponse:
        return self._summary_detail(self.get_summary_model(summary_id))

    def get_summary_model(self, summary_id: str) -> Summary:
        try:
            resolved_id = uuid.UUID(summary_id)
        except ValueError as exc:
            raise PersistedResourceNotFoundError("Summary was not found.") from exc
        summary = self.repository.get_summary(resolved_id)
        if summary is None:
            raise PersistedResourceNotFoundError("Summary was not found.")
        return summary

    def record_view(
        self,
        summary: Summary,
        *,
        tenant_id: str,
        actor_external_id: str,
    ) -> None:
        self.audit_service.record(
            action="view_summary",
            patient_id=summary.patient_id,
            resource_type="summary",
            resource_id=summary.summary_id,
            metadata={"tenant_id": tenant_id, "actor_external_id": actor_external_id},
        )

    def _generate(
        self,
        patient_id: str,
        request: SummaryGenerateRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
        audit_action: str,
        parent_summary_id: uuid.UUID | None,
        version_number: int,
        regeneration_reason: str | None,
    ) -> SummaryGenerateResponse:
        started = perf_counter()
        resolved_patient_id = _uuid_or_404(patient_id, "Patient")
        patient = self.repository.get_patient(resolved_patient_id)
        if patient is None:
            raise PersistedResourceNotFoundError("Patient was not found.")

        encounter = None
        if request.encounter_id:
            encounter = self.repository.get_encounter(request.encounter_id)
            if encounter is None or encounter.patient_id != resolved_patient_id:
                raise PersistedResourceNotFoundError("Encounter was not found for this patient.")

        context = self.repository.clinical_context(resolved_patient_id, request.encounter_id)
        if not any(context[key] for key in ("conditions", "observations", "medications", "diagnostic_reports", "documents", "chunks")):
            raise SummaryGenerationError("No clinical evidence is available for this patient.")

        generation_provider = self._generation_provider(request)
        if generation_provider == "gemini":
            return self._generate_with_gemini(
                patient,
                encounter,
                context,
                request,
                tenant_id=tenant_id,
                actor_external_id=actor_external_id,
                audit_action=audit_action,
                parent_summary_id=parent_summary_id,
                version_number=version_number,
                regeneration_reason=regeneration_reason,
                started=started,
            )

        sections = self._build_sections(patient, encounter, context)
        claims = [claim for section in sections for claim in section.claims]
        safety = self.safety_service.calculate(claims)
        summary_text = "\n\n".join(f"{section.title}\n{section.text}" for section in sections)
        context_hash = _context_hash(patient, encounter, context)
        output_hash = hashlib.sha256(summary_text.encode("utf-8")).hexdigest()

        model_run = ModelRun(
            model_name="deterministic_summary_service",
            model_version="phase3",
            provider="local",
            prompt_template_id="deterministic_patient_snapshot",
            prompt_version="1.0.0",
            summary_type=request.summary_type,
            context_hash=context_hash,
            output_hash=output_hash,
            input_token_count=_rough_token_count(context),
            output_token_count=len(summary_text.split()),
            latency_ms=int((perf_counter() - started) * 1000),
            status="completed",
            run_metadata={
                "llm_used": False,
                "require_citations": request.options.require_citations,
                "include_safety_check": request.options.include_safety_check,
            },
        )
        self.repository.add_model_run(model_run)
        self.repository.session.flush()

        summary = Summary(
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id if encounter else None,
            model_run_id=model_run.model_run_id,
            summary_type=request.summary_type,
            summary_text=summary_text,
            summary_language=request.language,
            status=SummaryStatus.DRAFT,
            citation_coverage=safety.citation_coverage,
            unsupported_claim_count=safety.unsupported_claim_count,
            conflict_count=safety.conflict_count,
            generated_at=datetime.now(UTC),
            version_number=version_number,
            parent_summary_id=parent_summary_id,
            context_hash=context_hash,
        )
        self.repository.session.add(summary)
        self.repository.session.flush()

        persisted_sections = self._persist_sections(summary, sections)
        self._persist_claims(summary, sections, persisted_sections)
        self.repository.session.flush()

        self.audit_service.record(
            action=audit_action,
            patient_id=summary.patient_id,
            resource_type="summary",
            resource_id=summary.summary_id,
            metadata={
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
                "summary_type": request.summary_type,
                "status": SummaryStatus.DRAFT.value,
                "llm_used": False,
                "citation_coverage": str(safety.citation_coverage),
                "unsupported_claim_count": safety.unsupported_claim_count,
                "conflict_count": safety.conflict_count,
                "regeneration_reason": regeneration_reason,
            },
        )
        return self._summary_generate_response(summary)

    def _generation_provider(self, request: SummaryGenerateRequest) -> str:
        configured = self.settings.llm_provider if self.settings else "deterministic"
        provider = request.provider or configured
        if provider in {"mock", "local", "deterministic"}:
            return "deterministic"
        if provider == "external":
            raise SummaryGenerationError(
                "Use provider='gemini' with RAG_LLM_PROVIDER=gemini for the governed external LLM path."
            )
        if provider == "gemini":
            if configured != "gemini":
                raise SummaryGenerationError(
                    "Gemini generation requires RAG_LLM_PROVIDER=gemini in the environment."
                )
            self._ensure_gemini_enabled()
            return "gemini"
        raise SummaryGenerationError(f"Unsupported summary provider: {provider}.")

    def _ensure_gemini_enabled(self) -> None:
        if self.settings is None:
            raise SummaryGenerationError("Gemini generation requires application settings.")
        if self.settings.llm_provider != "gemini":
            raise SummaryGenerationError("Gemini generation requires RAG_LLM_PROVIDER=gemini.")
        if not self.settings.llm_external_enabled:
            raise SummaryGenerationError(
                "Gemini generation requires RAG_LLM_EXTERNAL_ENABLED=true."
            )
        if not self.settings.llm_allow_phi_external:
            raise SummaryGenerationError(
                "Gemini generation requires RAG_LLM_ALLOW_PHI_EXTERNAL=true after governance approval."
            )
        if not self.settings.gemini_api_key:
            raise SummaryGenerationError("Gemini generation requires RAG_GEMINI_API_KEY.")

    def _generate_with_gemini(
        self,
        patient: Patient,
        encounter: Encounter | None,
        context: dict[str, list],
        request: SummaryGenerateRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
        audit_action: str,
        parent_summary_id: uuid.UUID | None,
        version_number: int,
        regeneration_reason: str | None,
        started: float,
    ) -> SummaryGenerateResponse:
        self._ensure_gemini_enabled()
        assert self.settings is not None
        assert self.settings.gemini_api_key is not None

        prompt_template = self._load_prompt_template(request.summary_type)
        evidence_pack, citation_lookup = self._build_evidence_pack(
            patient,
            encounter,
            context,
            request,
        )
        context_hash = hashlib.sha256(
            json.dumps(evidence_pack, sort_keys=True, default=_json_default).encode("utf-8")
        ).hexdigest()
        output_schema = prompt_template["output_schema"]
        user_text = self._render_gemini_prompt(prompt_template, evidence_pack, request)
        client = self.gemini_client or GeminiJsonClient(
            self.settings.gemini_api_key.get_secret_value(),
            self.settings.gemini_model,
        )
        try:
            raw_output = client.generate_json(
                system_instruction=prompt_template["system_instruction"],
                user_text=user_text,
                output_schema=output_schema,
                temperature=self.settings.llm_temperature,
            )
        except GenerationError as exc:
            raise SummaryGenerationError(f"Gemini generation failed safely: {exc}") from exc

        try:
            generated = GeminiPersistedSummary.model_validate_json(raw_output)
        except ValidationError as exc:
            raise SummaryGenerationError(
                "Gemini returned invalid structured JSON; no summary was created."
            ) from exc
        if generated.summary_type != request.summary_type:
            raise SummaryGenerationError("Gemini output summary_type does not match the request.")
        if generated.language != request.language:
            raise SummaryGenerationError("Gemini output language does not match the request.")

        sections = self._gemini_sections_to_drafts(generated, citation_lookup)
        claims = [claim for section in sections for claim in section.claims]
        safety = self.safety_service.calculate(claims)
        summary_text = "\n\n".join(f"{section.title}\n{section.text}" for section in sections)
        output_hash = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()

        model_run = ModelRun(
            model_name=self.settings.gemini_model,
            model_version=self.settings.gemini_model,
            provider="gemini",
            prompt_template_id=prompt_template["template_name"],
            prompt_version=prompt_template["template_version"],
            summary_type=request.summary_type,
            context_hash=context_hash,
            output_hash=output_hash,
            input_token_count=len(user_text.split()),
            output_token_count=len(raw_output.split()),
            latency_ms=int((perf_counter() - started) * 1000),
            status="completed",
            run_metadata={
                "llm_used": True,
                "provider_path": "model/gemini",
                "external_call": True,
                "llm_external_enabled": self.settings.llm_external_enabled,
                "allow_phi_external": self.settings.llm_allow_phi_external,
                "requires_deidentified_or_governed_data": True,
                "prompt_template_name": prompt_template["template_name"],
                "prompt_template_version": prompt_template["template_version"],
                "temperature": self.settings.llm_temperature,
                "require_citations": request.options.require_citations,
                "include_safety_check": request.options.include_safety_check,
            },
        )
        self.repository.add_model_run(model_run)
        self.repository.session.flush()

        summary = Summary(
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id if encounter else None,
            model_run_id=model_run.model_run_id,
            summary_type=request.summary_type,
            summary_text=summary_text,
            summary_language=request.language,
            status=SummaryStatus.DRAFT,
            citation_coverage=safety.citation_coverage,
            unsupported_claim_count=safety.unsupported_claim_count,
            conflict_count=safety.conflict_count,
            generated_at=datetime.now(UTC),
            version_number=version_number,
            parent_summary_id=parent_summary_id,
            context_hash=context_hash,
        )
        self.repository.session.add(summary)
        self.repository.session.flush()

        persisted_sections = self._persist_sections(summary, sections)
        self._persist_claims(summary, sections, persisted_sections)
        self.repository.session.flush()

        self.audit_service.record(
            action=audit_action,
            patient_id=summary.patient_id,
            resource_type="summary",
            resource_id=summary.summary_id,
            metadata={
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
                "summary_type": request.summary_type,
                "status": SummaryStatus.DRAFT.value,
                "llm_used": True,
                "provider": "gemini",
                "model_name": self.settings.gemini_model,
                "prompt_template_name": prompt_template["template_name"],
                "prompt_template_version": prompt_template["template_version"],
                "citation_coverage": str(safety.citation_coverage),
                "unsupported_claim_count": safety.unsupported_claim_count,
                "conflict_count": safety.conflict_count,
                "regeneration_reason": regeneration_reason,
            },
        )
        return self._summary_generate_response(summary)

    def _load_prompt_template(self, summary_type: str) -> dict[str, Any]:
        if self.settings is None:
            raise SummaryGenerationError("Prompt templates require application settings.")
        template_path = self.settings.prompt_templates_dir / f"{summary_type}_v1.json"
        if not template_path.exists():
            raise SummaryGenerationError(f"No active prompt template found for {summary_type}.")
        try:
            data = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SummaryGenerationError("Prompt template could not be loaded.") from exc
        required_keys = {
            "template_name",
            "template_version",
            "task_type",
            "is_active",
            "system_instruction",
            "prompt_text",
            "output_schema",
        }
        if missing := required_keys.difference(data):
            raise SummaryGenerationError(f"Prompt template is missing keys: {sorted(missing)}.")
        if not data["is_active"] or data["task_type"] != summary_type:
            raise SummaryGenerationError(f"No active prompt template found for {summary_type}.")
        return data

    def _render_gemini_prompt(
        self,
        prompt_template: dict[str, Any],
        evidence_pack: dict[str, Any],
        request: SummaryGenerateRequest,
    ) -> str:
        return "\n\n".join(
            [
                prompt_template["prompt_text"],
                f"Summary type: {request.summary_type}",
                f"Language: {request.language}",
                (
                    "Use only source_id values present in evidence_pack.evidence. "
                    "If a clinical statement has no direct source_id, set support_status "
                    "to unsupported or insufficient_evidence and place it in Needs Clinician Review."
                ),
                "Evidence pack JSON:",
                json.dumps(evidence_pack, ensure_ascii=False, sort_keys=True, default=_json_default),
                "Required output schema JSON:",
                json.dumps(prompt_template["output_schema"], ensure_ascii=False, sort_keys=True),
            ]
        )

    def _build_evidence_pack(
        self,
        patient: Patient,
        encounter: Encounter | None,
        context: dict[str, list],
        request: SummaryGenerateRequest,
    ) -> tuple[dict[str, Any], dict[str, CitationDraft]]:
        citation_lookup: dict[str, CitationDraft] = {}
        evidence: list[dict[str, Any]] = []

        def add_item(source_id: str, item: dict[str, Any], citation: CitationDraft) -> None:
            evidence.append(item | {"source_id": source_id, "patient_id": str(patient.patient_id)})
            citation_lookup[source_id] = citation

        age = _age(patient.date_of_birth)
        patient_text = _clean_join(
            [
                f"gender={patient.gender}" if patient.gender else None,
                f"age={age}" if age is not None else None,
                f"patient_hash={patient.patient_hash}" if patient.patient_hash else None,
            ]
        ) or "Patient record exists."
        add_item(
            f"patient:{patient.patient_id}",
            {
                "source_type": "patient",
                "text": patient_text,
                "timestamp": None,
                "metadata": {
                    "gender": patient.gender,
                    "age": age,
                    "is_deidentified": patient.is_deidentified,
                    "source_system": patient.source_system,
                },
            },
            CitationDraft(
                source_type="patient",
                source_record_type="patient",
                source_record_id=patient.patient_id,
                source_text_span=patient.patient_hash or patient.external_patient_id,
                citation_confidence=Decimal("0.90"),
            ),
        )

        if encounter:
            self._assert_patient_scope(encounter, patient.patient_id, "encounter")
            encounter_text = _clean_join(
                [
                    f"type={encounter.encounter_type}" if encounter.encounter_type else None,
                    f"status={encounter.status}" if encounter.status else None,
                    f"department={encounter.department}" if encounter.department else None,
                    f"reason={encounter.reason_for_visit}" if encounter.reason_for_visit else None,
                ]
            ) or "Encounter record exists."
            add_item(
                f"encounter:{encounter.encounter_id}",
                {
                    "source_type": "encounter",
                    "encounter_id": str(encounter.encounter_id),
                    "text": encounter_text,
                    "timestamp": encounter.start_time,
                    "metadata": {
                        "encounter_type": encounter.encounter_type,
                        "status": encounter.status,
                        "department": encounter.department,
                    },
                },
                CitationDraft(
                    source_type="encounter",
                    source_record_type="encounter",
                    source_record_id=encounter.encounter_id,
                    source_text_span=encounter.reason_for_visit,
                    citation_confidence=Decimal("0.92"),
                ),
            )

        for condition in context["conditions"]:
            self._assert_patient_scope(condition, patient.patient_id, "condition")
            text = _clean_join([condition.condition_name, condition.clinical_status])
            add_item(
                f"condition:{condition.condition_id}",
                {
                    "source_type": "condition",
                    "encounter_id": _string_or_none(condition.encounter_id),
                    "text": text,
                    "timestamp": condition.recorded_date,
                    "metadata": {
                        "condition_name": condition.condition_name,
                        "clinical_status": condition.clinical_status,
                        "verification_status": condition.verification_status,
                    },
                },
                CitationDraft(
                    source_type="condition",
                    source_condition_id=condition.condition_id,
                    source_text_span=condition.condition_name,
                    citation_confidence=Decimal("0.96"),
                ),
            )

        for observation in context["observations"]:
            self._assert_patient_scope(observation, patient.patient_id, "observation")
            value = observation.value_text
            if value is None and observation.value_numeric is not None:
                value = f"{observation.value_numeric:g}"
                if observation.unit:
                    value = f"{value} {observation.unit}"
            text = f"{observation.observation_name}: {value or MISSING_INFORMATION}"
            add_item(
                f"observation:{observation.observation_id}",
                {
                    "source_type": "observation",
                    "encounter_id": _string_or_none(observation.encounter_id),
                    "text": text,
                    "timestamp": observation.observed_at,
                    "metadata": {
                        "observation_name": observation.observation_name,
                        "observation_type": observation.observation_type,
                        "unit": observation.unit,
                        "interpretation": observation.interpretation,
                    },
                },
                CitationDraft(
                    source_type="observation",
                    source_observation_id=observation.observation_id,
                    source_text_span=text,
                    citation_confidence=Decimal("0.96"),
                ),
            )

        for medication in context["medications"]:
            self._assert_patient_scope(medication, patient.patient_id, "medication")
            text = _clean_join([medication.medication_name, medication.status, medication.dosage_text])
            add_item(
                f"medication:{medication.medication_id}",
                {
                    "source_type": "medication",
                    "encounter_id": _string_or_none(medication.encounter_id),
                    "text": text,
                    "timestamp": medication.start_date,
                    "metadata": {
                        "medication_name": medication.medication_name,
                        "status": medication.status,
                        "dosage_text": medication.dosage_text,
                    },
                },
                CitationDraft(
                    source_type="medication",
                    source_medication_id=medication.medication_id,
                    source_text_span=medication.medication_name,
                    citation_confidence=Decimal("0.96"),
                ),
            )

        for report in context["diagnostic_reports"]:
            self._assert_patient_scope(report, patient.patient_id, "diagnostic_report")
            text = report.conclusion_text or report.report_text
            add_item(
                f"diagnostic_report:{report.report_id}",
                {
                    "source_type": "diagnostic_report",
                    "encounter_id": _string_or_none(report.encounter_id),
                    "text": _shorten(text, 1200),
                    "timestamp": report.reported_at or report.performed_at,
                    "metadata": {
                        "report_type": report.report_type,
                        "report_title": report.report_title,
                        "report_status": report.report_status,
                    },
                },
                CitationDraft(
                    source_type="diagnostic_report",
                    source_report_id=report.report_id,
                    source_text_span=text,
                    citation_confidence=Decimal("0.94"),
                ),
            )

        for document in context["documents"]:
            self._assert_patient_scope(document, patient.patient_id, "clinical_document")
            add_item(
                f"document:{document.document_id}",
                {
                    "source_type": "clinical_document",
                    "encounter_id": _string_or_none(document.encounter_id),
                    "text": _shorten(document.raw_text, 1200),
                    "timestamp": document.document_datetime,
                    "metadata": {
                        "document_type": document.document_type,
                        "document_title": document.document_title,
                        "source_system": document.source_system,
                    },
                },
                CitationDraft(
                    source_type="clinical_document",
                    source_document_id=document.document_id,
                    source_text_span=_shorten(document.raw_text, 1200),
                    citation_confidence=Decimal("0.90"),
                ),
            )

        for chunk in context["chunks"]:
            self._assert_patient_scope(chunk, patient.patient_id, "document_chunk")
            add_item(
                f"chunk:{chunk.chunk_id}",
                {
                    "source_type": "document_chunk",
                    "encounter_id": _string_or_none(chunk.encounter_id),
                    "document_id": str(chunk.document_id),
                    "text": chunk.chunk_text,
                    "timestamp": chunk.created_at,
                    "metadata": {
                        "section_name": chunk.section_name,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                    },
                },
                _chunk_citation(chunk, Decimal("0.92")),
            )

        return (
            {
                "request": {
                    "summary_type": request.summary_type,
                    "language": request.language,
                    "patient_id": str(patient.patient_id),
                    "encounter_id": str(encounter.encounter_id) if encounter else None,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "external_provider_warning": (
                        "Use only de-identified or governed data when external Gemini is enabled."
                    ),
                },
                "patient_context": {
                    "age": age,
                    "gender": patient.gender,
                    "is_deidentified": patient.is_deidentified,
                    "encounter_type": encounter.encounter_type if encounter else None,
                    "department": encounter.department if encounter else None,
                    "reason_for_visit": encounter.reason_for_visit if encounter else None,
                },
                "evidence": evidence,
            },
            citation_lookup,
        )

    @staticmethod
    def _assert_patient_scope(item: Any, patient_id: uuid.UUID, label: str) -> None:
        item_patient_id = getattr(item, "patient_id", patient_id)
        if item_patient_id != patient_id:
            raise SummaryGenerationError(f"{label} evidence belongs to a different patient.")

    def _gemini_sections_to_drafts(
        self,
        generated: GeminiPersistedSummary,
        citation_lookup: dict[str, CitationDraft],
    ) -> list[SectionDraft]:
        sections = {section_type: SectionDraft(title, section_type) for title, section_type in self.REQUIRED_SECTIONS}
        allowed_section_types = set(sections)
        needs_review = sections["needs_clinician_review"]

        for generated_section in sorted(generated.sections, key=lambda item: item.section_order):
            section_type = generated_section.section_type
            if section_type not in allowed_section_types:
                section_type = _section_type_from_title(generated_section.section_title)
            if section_type not in allowed_section_types:
                section_type = "needs_clinician_review"
            target_section = sections[section_type]
            for generated_claim in generated_section.claims:
                citations = [
                    citation_lookup[source_id]
                    for source_id in generated_claim.citation_ids
                    if source_id in citation_lookup
                ]
                support_status = ClaimSupportStatus(generated_claim.support_status)
                clinical_risk_level = _risk_level(
                    generated_claim.claim_type,
                    generated_claim.clinical_risk_level,
                )
                if _contains_forbidden_clinical_advice(generated_claim.claim_text):
                    support_status = ClaimSupportStatus.UNSUPPORTED
                    clinical_risk_level = "critical"
                    citations = []
                if support_status == ClaimSupportStatus.SUPPORTED and not citations:
                    support_status = ClaimSupportStatus.INSUFFICIENT_EVIDENCE
                    clinical_risk_level = _risk_level(generated_claim.claim_type, clinical_risk_level)

                draft = ClaimDraft(
                    text=generated_claim.claim_text,
                    claim_type=generated_claim.claim_type,
                    support_status=support_status,
                    clinical_risk_level=clinical_risk_level,
                    citations=citations,
                    confidence_score=generated_claim.confidence_score,
                )
                if support_status != ClaimSupportStatus.SUPPORTED and section_type != "needs_clinician_review":
                    needs_review.claims.append(draft)
                else:
                    target_section.claims.append(draft)

        for note in generated.safety_notes:
            if note.strip():
                needs_review.claims.append(
                    ClaimDraft(
                        text=note.strip(),
                        claim_type="general",
                        support_status=ClaimSupportStatus.UNCHECKED,
                        clinical_risk_level="low",
                        confidence_score=Decimal("0"),
                    )
                )

        return [sections[section_type] for _, section_type in self.REQUIRED_SECTIONS]

    def _build_sections(
        self,
        patient: Patient,
        encounter: Encounter | None,
        context: dict[str, list],
    ) -> list[SectionDraft]:
        sections = [SectionDraft(title, section_type) for title, section_type in self.REQUIRED_SECTIONS]
        needs_review = sections[-1]

        self._patient_snapshot_section(sections[0], patient, encounter, needs_review)
        self._active_problems_section(sections[1], context["conditions"], needs_review)
        self._clinical_course_section(sections[2], context["documents"], context["chunks"], needs_review)
        self._medications_section(sections[3], context["medications"], needs_review)
        self._labs_imaging_section(
            sections[4],
            context["observations"],
            context["diagnostic_reports"],
            needs_review,
        )
        self._append_missing(needs_review, "allergy")
        for conflict in self.safety_service.detect_obvious_conflicts(context["chunks"]):
            needs_review.claims.append(
                ClaimDraft(
                    text=conflict.message,
                    claim_type="allergy",
                    support_status=ClaimSupportStatus.CONFLICTING,
                    clinical_risk_level="critical",
                    citations=[_chunk_citation(chunk, Decimal("0.90")) for chunk in conflict.chunks],
                    confidence_score=Decimal("0.90"),
                )
            )
        return sections

    def _patient_snapshot_section(
        self,
        section: SectionDraft,
        patient: Patient,
        encounter: Encounter | None,
        needs_review: SectionDraft,
    ) -> None:
        demographics = []
        if patient.gender:
            demographics.append(f"giới tính {patient.gender}")
        age = _age(patient.date_of_birth)
        if age is not None:
            demographics.append(f"{age} tuổi")
        if demographics:
            section.claims.append(
                ClaimDraft(
                    text=f"Bệnh nhân {'; '.join(demographics)}.",
                    claim_type="general",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    clinical_risk_level="low",
                    citations=[
                        CitationDraft(
                            source_type="patient",
                            source_record_type="patient",
                            source_record_id=patient.patient_id,
                            source_text_span=patient.patient_hash or patient.external_patient_id,
                            citation_confidence=Decimal("0.90"),
                        )
                    ],
                    confidence_score=Decimal("0.90"),
                )
            )
        else:
            self._append_missing(needs_review, "patient_demographics")
        if encounter:
            parts = []
            if encounter.encounter_type:
                parts.append(f"loại lượt khám {encounter.encounter_type}")
            if encounter.status:
                parts.append(f"trạng thái {encounter.status}")
            if encounter.reason_for_visit:
                parts.append(f"lý do ghi nhận: {encounter.reason_for_visit}")
            text = "Encounter được ghi nhận" + (": " + "; ".join(parts) if parts else ".")
            section.claims.append(
                ClaimDraft(
                    text=text,
                    claim_type="encounter_context",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    clinical_risk_level="medium",
                    citations=[
                        CitationDraft(
                            source_type="encounter",
                            source_record_type="encounter",
                            source_record_id=encounter.encounter_id,
                            source_text_span=encounter.reason_for_visit,
                            citation_confidence=Decimal("0.92"),
                        )
                    ],
                    confidence_score=Decimal("0.92"),
                )
            )

    def _active_problems_section(
        self,
        section: SectionDraft,
        conditions: list[Condition],
        needs_review: SectionDraft,
    ) -> None:
        if not conditions:
            self._append_missing(needs_review, "active_problems")
            return
        for condition in sorted(
            conditions,
            key=lambda item: item.recorded_date.isoformat() if item.recorded_date else "",
            reverse=True,
        )[:5]:
            status = f"; trạng thái {condition.clinical_status}" if condition.clinical_status else ""
            section.claims.append(
                ClaimDraft(
                    text=f"Dữ liệu nguồn ghi nhận vấn đề: {condition.condition_name}{status}.",
                    claim_type="diagnosis",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    clinical_risk_level="high",
                    citations=[
                        CitationDraft(
                            source_type="condition",
                            source_condition_id=condition.condition_id,
                            source_text_span=condition.condition_name,
                            citation_confidence=Decimal("0.96"),
                        )
                    ],
                    confidence_score=Decimal("0.96"),
                )
            )

    def _clinical_course_section(
        self,
        section: SectionDraft,
        documents: list[ClinicalDocument],
        chunks: list[DocumentChunk],
        needs_review: SectionDraft,
    ) -> None:
        if not documents and not chunks:
            self._append_missing(needs_review, "clinical_course")
            return
        for chunk in sorted(
            chunks,
            key=lambda item: item.created_at.isoformat() if item.created_at else "",
            reverse=True,
        )[:3]:
            section.claims.append(
                ClaimDraft(
                    text=f"Ghi chú lâm sàng ghi nhận: {_shorten(chunk.chunk_text)}",
                    claim_type="timeline_event",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    clinical_risk_level="medium",
                    citations=[_chunk_citation(chunk, Decimal("0.92"))],
                    confidence_score=Decimal("0.92"),
                )
            )

    def _medications_section(
        self,
        section: SectionDraft,
        medications: list[Medication],
        needs_review: SectionDraft,
    ) -> None:
        if not medications:
            self._append_missing(needs_review, "medications")
            return
        for medication in medications[:5]:
            parts = [medication.medication_name]
            if medication.status:
                parts.append(f"trạng thái {medication.status}")
            if medication.dosage_text:
                parts.append(f"liều/cách dùng {medication.dosage_text}")
            section.claims.append(
                ClaimDraft(
                    text=f"Dữ liệu thuốc ghi nhận: {'; '.join(parts)}.",
                    claim_type="medication",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    clinical_risk_level="critical",
                    citations=[
                        CitationDraft(
                            source_type="medication",
                            source_medication_id=medication.medication_id,
                            source_text_span=medication.medication_name,
                            citation_confidence=Decimal("0.96"),
                        )
                    ],
                    confidence_score=Decimal("0.96"),
                )
            )

    def _labs_imaging_section(
        self,
        section: SectionDraft,
        observations: list[Observation],
        reports: list[DiagnosticReport],
        needs_review: SectionDraft,
    ) -> None:
        if not observations and not reports:
            self._append_missing(needs_review, "labs_imaging")
            return
        for observation in observations[:5]:
            value = observation.value_text
            if value is None and observation.value_numeric is not None:
                value = f"{observation.value_numeric:g}"
                if observation.unit:
                    value = f"{value} {observation.unit}"
            claim_type = "vital_sign" if observation.observation_type == "vital" else "lab_result"
            section.claims.append(
                ClaimDraft(
                    text=f"Kết quả {observation.observation_name}: {value or MISSING_INFORMATION}.",
                    claim_type=claim_type,
                    support_status=ClaimSupportStatus.SUPPORTED,
                    clinical_risk_level="high",
                    citations=[
                        CitationDraft(
                            source_type="observation",
                            source_observation_id=observation.observation_id,
                            source_text_span=f"{observation.observation_name}: {value}",
                            citation_confidence=Decimal("0.96"),
                        )
                    ],
                    confidence_score=Decimal("0.96"),
                )
            )
        for report in reports[:3]:
            text = report.conclusion_text or report.report_text
            section.claims.append(
                ClaimDraft(
                    text=f"Báo cáo cận lâm sàng ghi nhận: {_shorten(text)}",
                    claim_type="imaging_finding",
                    support_status=ClaimSupportStatus.SUPPORTED,
                    clinical_risk_level="high",
                    citations=[
                        CitationDraft(
                            source_type="diagnostic_report",
                            source_report_id=report.report_id,
                            source_text_span=text,
                            citation_confidence=Decimal("0.94"),
                        )
                    ],
                    confidence_score=Decimal("0.94"),
                )
            )

    @staticmethod
    def _append_missing(section: SectionDraft, topic: str) -> None:
        section.claims.append(
            ClaimDraft(
                text=MISSING_INFORMATION,
                claim_type="missing_information",
                support_status=ClaimSupportStatus.INSUFFICIENT_EVIDENCE,
                clinical_risk_level="low",
                confidence_score=Decimal("0"),
            )
        )

    def _persist_sections(
        self, summary: Summary, section_drafts: list[SectionDraft]
    ) -> dict[str, SummarySection]:
        persisted: dict[str, SummarySection] = {}
        for index, draft in enumerate(section_drafts, start=1):
            section = SummarySection(
                summary_id=summary.summary_id,
                section_order=index,
                section_title=draft.title,
                section_text=draft.text,
                section_type=draft.section_type,
            )
            self.repository.session.add(section)
            persisted[draft.section_type] = section
        self.repository.session.flush()
        return persisted

    def _persist_claims(
        self,
        summary: Summary,
        section_drafts: list[SectionDraft],
        persisted_sections: dict[str, SummarySection],
    ) -> None:
        claim_order = 1
        for section_draft in section_drafts:
            section = persisted_sections[section_draft.section_type]
            for claim_draft in section_draft.claims:
                claim = SummaryClaim(
                    summary_id=summary.summary_id,
                    section_id=section.section_id,
                    claim_order=claim_order,
                    claim_text=claim_draft.text,
                    claim_type=claim_draft.claim_type,
                    support_status=claim_draft.support_status,
                    confidence_score=claim_draft.confidence_score,
                    clinical_risk_level=claim_draft.clinical_risk_level,
                )
                self.repository.session.add(claim)
                self.repository.session.flush()
                for citation_draft in claim_draft.citations:
                    self.repository.session.add(
                        ClaimCitation(
                            claim_id=claim.claim_id,
                            source_type=citation_draft.source_type,
                            source_document_id=citation_draft.source_document_id,
                            source_chunk_id=citation_draft.source_chunk_id,
                            source_condition_id=citation_draft.source_condition_id,
                            source_observation_id=citation_draft.source_observation_id,
                            source_medication_id=citation_draft.source_medication_id,
                            source_report_id=citation_draft.source_report_id,
                            source_record_type=citation_draft.source_record_type,
                            source_record_id=citation_draft.source_record_id,
                            source_text_span=citation_draft.source_text_span,
                            source_char_start=citation_draft.source_char_start,
                            source_char_end=citation_draft.source_char_end,
                            citation_confidence=citation_draft.citation_confidence,
                        )
                    )
                claim_order += 1

    @staticmethod
    def _summary_generate_response(summary: Summary) -> SummaryGenerateResponse:
        return SummaryGenerateResponse(
            summary_id=summary.summary_id,
            patient_id=summary.patient_id,
            encounter_id=summary.encounter_id,
            summary_type=summary.summary_type,
            status=summary.status.value,
            citation_coverage=summary.citation_coverage,
            unsupported_claim_count=summary.unsupported_claim_count,
            conflict_count=summary.conflict_count,
            generated_at=summary.generated_at,
        )

    def _summary_detail(self, summary: Summary) -> SummaryDetailResponse:
        sections = sorted(summary.sections, key=lambda section: section.section_order)
        reviews = sorted(
            summary.reviews,
            key=lambda review: (
                review.reviewed_at or review.created_at,
                review.created_at,
            ),
        )
        latest_edit = next(
            (review for review in reversed(reviews) if review.edited_summary_text),
            None,
        )
        latest_review = reviews[-1] if reviews else None
        return SummaryDetailResponse(
            summary_id=summary.summary_id,
            patient_id=summary.patient_id,
            encounter_id=summary.encounter_id,
            summary_type=summary.summary_type,
            summary_text=summary.summary_text,
            summary_language=summary.summary_language,
            status=summary.status.value,
            version_number=summary.version_number,
            parent_summary_id=summary.parent_summary_id,
            citation_coverage=summary.citation_coverage,
            unsupported_claim_count=summary.unsupported_claim_count,
            conflict_count=summary.conflict_count,
            generated_at=summary.generated_at,
            reviewed_by=summary.reviewed_by,
            approved_by=summary.approved_by,
            reviewed_at=summary.reviewed_at,
            approved_at=summary.approved_at,
            rejected_at=summary.rejected_at,
            rejection_reason=summary.rejection_reason,
            latest_edited_summary_text=latest_edit.edited_summary_text if latest_edit else None,
            latest_review_comment=latest_review.comment if latest_review else None,
            latest_edit_distance_score=latest_edit.edit_distance_score if latest_edit else None,
            citation_revalidation_required=latest_edit is not None and summary.status == SummaryStatus.EDITED,
            sections=[
                SummarySectionResponse(
                    section_id=section.section_id,
                    summary_id=section.summary_id,
                    section_order=section.section_order,
                    section_title=section.section_title,
                    section_text=section.section_text,
                    section_type=section.section_type,
                    claims=[
                        _claim_response(claim)
                        for claim in sorted(section.claims, key=lambda item: item.claim_order)
                    ],
                )
                for section in sections
            ],
            safety_summary=SummarySafetyResponse(
                citation_coverage=summary.citation_coverage,
                unsupported_claim_count=summary.unsupported_claim_count,
                conflict_count=summary.conflict_count,
                total_claim_count=len(summary.claims),
                supported_claim_count=sum(
                    1 for claim in summary.claims if claim.support_status == ClaimSupportStatus.SUPPORTED
                ),
            ),
        )


def _claim_response(claim: SummaryClaim) -> SummaryClaimResponse:
    citations = [_citation_response(citation) for citation in claim.citations]
    return SummaryClaimResponse(
        claim_id=claim.claim_id,
        summary_id=claim.summary_id,
        section_id=claim.section_id,
        claim_order=claim.claim_order,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type,
        support_status=claim.support_status.value,
        confidence_score=claim.confidence_score,
        clinical_risk_level=claim.clinical_risk_level,
        citation_count=len(citations),
        citations=citations,
    )


def _citation_response(citation: ClaimCitation) -> ClaimCitationResponse:
    return ClaimCitationResponse.model_validate(citation)


def _chunk_citation(chunk: DocumentChunk, confidence: Decimal) -> CitationDraft:
    return CitationDraft(
        source_type="document_chunk",
        source_document_id=chunk.document_id,
        source_chunk_id=chunk.chunk_id,
        source_text_span=chunk.chunk_text,
        source_char_start=chunk.char_start,
        source_char_end=chunk.char_end,
        citation_confidence=confidence,
    )


def _uuid_or_404(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise PersistedResourceNotFoundError(f"{label} was not found.") from exc


def _age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _shorten(text: str | None, limit: int = 220) -> str:
    if not text:
        return MISSING_INFORMATION
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 3].rstrip()}..."


def _context_hash(patient: Patient, encounter: Encounter | None, context: dict[str, list]) -> str:
    ids: list[str] = [str(patient.patient_id)]
    if encounter:
        ids.append(str(encounter.encounter_id))
    for key in sorted(context):
        for item in context[key]:
            ids.append(_identity(item))
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()


def _identity(item: Any) -> str:
    for attr in (
        "condition_id",
        "observation_id",
        "medication_id",
        "report_id",
        "document_id",
        "chunk_id",
    ):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return repr(item)


def _rough_token_count(context: dict[str, list]) -> int:
    total = 0
    for items in context.values():
        for item in items:
            for attr in ("condition_name", "observation_name", "medication_name", "report_text", "raw_text", "chunk_text"):
                text = getattr(item, attr, None)
                if text:
                    total += len(str(text).split())
    return total


def _json_default(value: Any) -> str | int | float:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _clean_join(parts: list[str | None]) -> str:
    return "; ".join(str(part).strip() for part in parts if part and str(part).strip())


def _section_type_from_title(title: str) -> str | None:
    normalized = title.strip().lower().replace("&", "and")
    if "patient" in normalized and "snapshot" in normalized:
        return "patient_snapshot"
    if "active" in normalized and ("problem" in normalized or "diagnos" in normalized):
        return "active_problems"
    if "course" in normalized or "timeline" in normalized:
        return "recent_clinical_course"
    if "medication" in normalized or "thuoc" in normalized:
        return "medications"
    if "lab" in normalized or "imaging" in normalized or "highlight" in normalized:
        return "labs_imaging"
    if "review" in normalized or "missing" in normalized or "safety" in normalized:
        return "needs_clinician_review"
    return None


def _risk_level(claim_type: str, supplied: str | None) -> str:
    floor = {
        "diagnosis": "critical",
        "medication": "critical",
        "allergy": "critical",
        "procedure": "high",
        "lab_result": "high",
        "vital_sign": "high",
        "imaging_finding": "high",
        "timeline_event": "medium",
        "encounter_context": "medium",
        "follow_up": "medium",
    }.get(claim_type, "low")
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    supplied_value = supplied if supplied in order else floor
    return supplied_value if order[supplied_value] >= order[floor] else floor


def _contains_forbidden_clinical_advice(text: str) -> bool:
    lowered = text.lower()
    forbidden_markers = (
        "recommend treatment",
        "treatment recommendation",
        "should start",
        "should prescribe",
        "prescribe ",
        "start medication",
        "increase dose",
        "decrease dose",
        "approve discharge",
        "diagnose ",
        "nên điều trị",
        "khuyến nghị điều trị",
        "kê đơn",
        "nên dùng",
        "tăng liều",
        "giảm liều",
        "phê duyệt xuất viện",
        "chẩn đoán là",
    )
    return any(marker in lowered for marker in forbidden_markers)
