from __future__ import annotations

import hashlib
import json
import re
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
from .summary_providers import (
    BartProvider,
    PegasusCnnDailyMailProvider,
    PegasusPubMedProvider,
    PegasusProvider,
    PegasusXSumProvider,
    ProviderExecutionError,
    ProviderOutput,
    SummaryProvider,
)


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
        model_providers: dict[str, SummaryProvider] | None = None,
    ):
        self.repository = repository
        self.safety_service = safety_service
        self.audit_service = audit_service
        self.settings = settings
        self.gemini_client = gemini_client
        self.model_providers = model_providers or {}

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
        model_provider = _model_provider_label(existing.model_run)
        if model_provider not in {
            "deterministic",
            "gemini",
            "bart",
            "pegasus",
            "pegasus_pubmed",
            "pegasus_cnn_dailymail",
            "pegasus_xsum",
        }:
            model_provider = "deterministic"
        generate_request = SummaryGenerateRequest(
            encounter_id=existing.encounter_id,
            summary_type="patient_snapshot",
            language=existing.summary_language,
            model_provider=model_provider,
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
            metadata={
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
                "summary_id": str(summary.summary_id),
                "encounter_id": str(summary.encounter_id) if summary.encounter_id else None,
                "summary_type": summary.summary_type,
                "status": summary.status.value if summary.status else None,
                "provider": _model_provider_label(summary.model_run),
                "model_provider": _model_provider_label(summary.model_run),
                "model_name": summary.model_run.model_name if summary.model_run else None,
            },
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
        if generation_provider in {"bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail", "pegasus_xsum"}:
            return self._generate_with_text_provider(
                generation_provider,
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
                "summary_id": str(summary.summary_id),
                "encounter_id": str(summary.encounter_id) if summary.encounter_id else None,
                "summary_type": request.summary_type,
                "status": SummaryStatus.DRAFT.value,
                "llm_used": False,
                "provider": "deterministic",
                "model_provider": "deterministic",
                "model_name": model_run.model_name,
                "citation_coverage": str(safety.citation_coverage),
                "unsupported_claim_count": safety.unsupported_claim_count,
                "conflict_count": safety.conflict_count,
                "regeneration_reason": regeneration_reason,
            },
        )
        return self._summary_generate_response(summary)

    def _generation_provider(self, request: SummaryGenerateRequest) -> str:
        configured = self.settings.llm_provider if self.settings else "deterministic"
        provider = request.model_provider or request.provider or configured
        if provider in {"mock", "local", "deterministic"}:
            return "deterministic"
        if provider in {"bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail", "pegasus_xsum"}:
            return provider
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
            generated_payload = _load_and_normalize_gemini_payload(raw_output, request)
            generated = GeminiPersistedSummary.model_validate(generated_payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise SummaryGenerationError(
                "Gemini returned invalid structured JSON; no summary was created. "
                f"{_validation_hint(exc)}"
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
                "summary_id": str(summary.summary_id),
                "encounter_id": str(summary.encounter_id) if summary.encounter_id else None,
                "summary_type": request.summary_type,
                "status": SummaryStatus.DRAFT.value,
                "llm_used": True,
                "provider": "gemini",
                "model_provider": "gemini",
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

    def _generate_with_text_provider(
        self,
        provider_name: str,
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
        evidence_pack, citation_lookup = self._build_evidence_pack(
            patient,
            encounter,
            context,
            request,
        )
        context_hash = hashlib.sha256(
            json.dumps(evidence_pack, sort_keys=True, default=_json_default).encode("utf-8")
        ).hexdigest()
        provider = self._summary_provider(provider_name)
        try:
            provider_output = provider.generate_summary(
                patient=patient,
                encounter=encounter,
                context=context,
                evidence_pack=evidence_pack,
                summary_type=request.summary_type,
                language=request.language,
                options=request.options.model_dump(),
            )
        except ProviderExecutionError as exc:
            raise SummaryGenerationError(str(exc)) from exc
        except Exception as exc:
            raise SummaryGenerationError(
                f"{provider_name.upper()} generation failed safely: {exc}"
            ) from exc

        if provider_output.provider != provider_name:
            raise SummaryGenerationError(
                f"Provider output mismatch: expected {provider_name}, got {provider_output.provider}."
            )
        if not provider_output.summary_text.strip():
            raise SummaryGenerationError(f"{provider_name.upper()} returned an empty summary.")

        sections = self._text_provider_sections_to_drafts(
            provider_output,
            evidence_pack,
            citation_lookup,
        )
        claims = [claim for section in sections for claim in section.claims]
        safety = self.safety_service.calculate(claims)
        summary_text = "\n\n".join(f"{section.title}\n{section.text}" for section in sections)
        output_hash = hashlib.sha256(provider_output.summary_text.encode("utf-8")).hexdigest()
        latency_ms = provider_output.latency_ms or int((perf_counter() - started) * 1000)

        model_run = ModelRun(
            model_name=provider_output.model_name,
            model_version=provider_output.model_version or provider_output.model_name,
            provider=provider_name,
            prompt_template_id=provider_output.prompt_template_name
            or f"{provider_name}_text_normalizer",
            prompt_version=provider_output.prompt_template_version or "1.0.0",
            summary_type=request.summary_type,
            context_hash=context_hash,
            output_hash=output_hash,
            input_token_count=_rough_token_count(context),
            output_token_count=len(provider_output.summary_text.split()),
            latency_ms=latency_ms,
            status="completed",
            run_metadata={
                "llm_used": True,
                "provider_path": f"baseline/{provider_name}",
                "normalization": "sentence_overlap_citation",
                "require_citations": request.options.require_citations,
                "include_safety_check": request.options.include_safety_check,
                "raw_output": provider_output.raw_output,
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
                "summary_id": str(summary.summary_id),
                "encounter_id": str(summary.encounter_id) if summary.encounter_id else None,
                "summary_type": request.summary_type,
                "status": SummaryStatus.DRAFT.value,
                "llm_used": True,
                "provider": provider_name,
                "model_provider": provider_name,
                "model_name": provider_output.model_name,
                "citation_coverage": str(safety.citation_coverage),
                "unsupported_claim_count": safety.unsupported_claim_count,
                "conflict_count": safety.conflict_count,
                "regeneration_reason": regeneration_reason,
            },
        )
        return self._summary_generate_response(summary)

    def _summary_provider(self, provider_name: str) -> SummaryProvider:
        if provider_name in self.model_providers:
            return self.model_providers[provider_name]
        if provider_name == "bart":
            provider = BartProvider()
        elif provider_name == "pegasus":
            provider = PegasusProvider()
        elif provider_name == "pegasus_pubmed":
            provider = PegasusPubMedProvider()
        elif provider_name == "pegasus_cnn_dailymail":
            provider = PegasusCnnDailyMailProvider()
        elif provider_name == "pegasus_xsum":
            provider = PegasusXSumProvider()
        else:
            raise SummaryGenerationError(f"Unsupported summary provider: {provider_name}.")
        self.model_providers[provider_name] = provider
        return provider

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
            if _should_persist_safety_note(note):
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

    def _text_provider_sections_to_drafts(
        self,
        provider_output: ProviderOutput,
        evidence_pack: dict[str, Any],
        citation_lookup: dict[str, CitationDraft],
    ) -> list[SectionDraft]:
        generated = SectionDraft("Generated Summary", "generated_summary")
        needs_review = SectionDraft("Needs Clinician Review", "needs_clinician_review")
        claim_texts: list[str] = []
        for section in provider_output.sections:
            claim_texts.extend(section.claims)
        if not claim_texts:
            claim_texts = _split_claim_text(provider_output.summary_text)

        for text in claim_texts:
            claim_text = text.strip()
            if not claim_text:
                continue
            claim_type = _infer_claim_type(claim_text)
            citations = self._match_claim_citations(claim_text, evidence_pack, citation_lookup)
            clinical_risk_level = _risk_level(claim_type, None)
            confidence_score = Decimal("0.72") if citations else Decimal("0")
            support_status = (
                ClaimSupportStatus.SUPPORTED
                if citations
                else ClaimSupportStatus.INSUFFICIENT_EVIDENCE
            )
            if _contains_forbidden_clinical_advice(claim_text):
                support_status = ClaimSupportStatus.UNSUPPORTED
                clinical_risk_level = "critical"
                citations = []
                confidence_score = Decimal("0")
            draft = ClaimDraft(
                text=claim_text,
                claim_type=claim_type,
                support_status=support_status,
                clinical_risk_level=clinical_risk_level,
                citations=citations,
                confidence_score=confidence_score,
            )
            if support_status == ClaimSupportStatus.SUPPORTED:
                generated.claims.append(draft)
            else:
                needs_review.claims.append(draft)

        if not generated.claims and not needs_review.claims:
            needs_review.claims.append(
                ClaimDraft(
                    text=MISSING_INFORMATION,
                    claim_type="missing_information",
                    support_status=ClaimSupportStatus.INSUFFICIENT_EVIDENCE,
                    clinical_risk_level="low",
                    confidence_score=Decimal("0"),
                )
            )
        needs_review.claims.append(
            ClaimDraft(
                text="Provider output requires clinician review before clinical use.",
                claim_type="general",
                support_status=ClaimSupportStatus.UNCHECKED,
                clinical_risk_level="low",
                confidence_score=Decimal("0"),
            )
        )
        return [generated, needs_review]

    def _match_claim_citations(
        self,
        claim_text: str,
        evidence_pack: dict[str, Any],
        citation_lookup: dict[str, CitationDraft],
    ) -> list[CitationDraft]:
        claim_tokens = _token_set(claim_text)
        if len(claim_tokens) < 3:
            return []
        scored: list[tuple[float, str]] = []
        lowered_claim = claim_text.casefold()
        for item in evidence_pack.get("evidence", []):
            source_id = str(item.get("source_id") or "")
            source_text = str(item.get("text") or "")
            if source_id not in citation_lookup or not source_text.strip():
                continue
            source_tokens = _token_set(source_text)
            if not source_tokens:
                continue
            direct_match = lowered_claim in source_text.casefold()
            overlap = len(claim_tokens.intersection(source_tokens))
            score = 1.0 if direct_match else overlap / max(1, min(len(claim_tokens), len(source_tokens)))
            if score >= 0.55:
                scored.append((score, source_id))
        scored.sort(reverse=True)
        return [citation_lookup[source_id] for _score, source_id in scored[:2]]

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
            model_provider=_model_provider_label(summary.model_run),
            model_name=summary.model_run.model_name if summary.model_run else None,
            latency_ms=summary.model_run.latency_ms if summary.model_run else None,
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
            model_provider=_model_provider_label(summary.model_run),
            model_name=summary.model_run.model_name if summary.model_run else None,
            latency_ms=summary.model_run.latency_ms if summary.model_run else None,
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


def _model_provider_label(model_run: ModelRun | None) -> str | None:
    if model_run is None:
        return None
    if model_run.provider == "local":
        return "deterministic"
    return model_run.provider


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


ALLOWED_CLAIM_TYPES = {
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
}

CLAIM_TYPE_ALIASES = {
    "active_problem": "diagnosis",
    "active_problems": "diagnosis",
    "condition": "diagnosis",
    "diagnoses": "diagnosis",
    "diagnostic": "diagnosis",
    "problem": "diagnosis",
    "problems": "diagnosis",
    "med": "medication",
    "meds": "medication",
    "drug": "medication",
    "drugs": "medication",
    "lab": "lab_result",
    "labs": "lab_result",
    "laboratory": "lab_result",
    "observation": "lab_result",
    "vital": "vital_sign",
    "vitals": "vital_sign",
    "image": "imaging_finding",
    "imaging": "imaging_finding",
    "radiology": "imaging_finding",
    "course": "timeline_event",
    "timeline": "timeline_event",
    "clinical_course": "timeline_event",
    "missing": "missing_information",
    "missing_info": "missing_information",
    "review": "missing_information",
    "recommendation": "follow_up",
}

SUPPORT_STATUS_ALIASES = {
    "supported": "supported",
    "support": "supported",
    "cited": "supported",
    "evidenced": "supported",
    "unsupported": "unsupported",
    "not_supported": "unsupported",
    "no_support": "unsupported",
    "conflict": "conflicting",
    "conflicting": "conflicting",
    "contradictory": "conflicting",
    "contradiction": "conflicting",
    "insufficient": "insufficient_evidence",
    "insufficient_evidence": "insufficient_evidence",
    "missing": "insufficient_evidence",
    "not_found": "insufficient_evidence",
    "not found": "insufficient_evidence",
    "no_evidence": "insufficient_evidence",
    "unchecked": "unchecked",
    "unverified": "unchecked",
    "unknown": "unchecked",
}

ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}


def _load_and_normalize_gemini_payload(
    raw_output: str,
    request: SummaryGenerateRequest,
) -> dict[str, Any]:
    payload = json.loads(raw_output)
    if not isinstance(payload, dict):
        return {}

    summary_type = _normalize_token(payload.get("summary_type"))
    if summary_type in {"patient_snapshot", "patient", "snapshot"}:
        summary_type = request.summary_type

    language = _normalize_language(payload.get("language"), request.language)
    sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
    normalized_sections = [
        _normalize_gemini_section(section, index)
        for index, section in enumerate(sections, start=1)
        if isinstance(section, (dict, str))
    ]

    return {
        "summary_type": summary_type,
        "language": language,
        "requires_clinician_review": _normalize_boolean(payload.get("requires_clinician_review")),
        "sections": normalized_sections,
        "safety_notes": _normalize_string_list(payload.get("safety_notes")),
    }


def _normalize_gemini_section(section: dict[str, Any] | str, index: int) -> dict[str, Any]:
    if isinstance(section, str):
        return {
            "section_title": "Needs Clinician Review",
            "section_type": "needs_clinician_review",
            "section_order": index,
            "claims": [
                {
                    "claim_text": section,
                    "claim_type": "general",
                    "support_status": "unchecked",
                    "citation_ids": [],
                    "clinical_risk_level": "low",
                }
            ],
        }

    section_title = str(section.get("section_title") or section.get("title") or "").strip()
    section_type = _normalize_token(section.get("section_type") or section.get("type"))
    inferred_type = _section_type_from_title(section_title) if section_title else None
    if section_type not in {section_type for _, section_type in DeterministicSummaryService.REQUIRED_SECTIONS}:
        section_type = inferred_type or "needs_clinician_review"
    if not section_title:
        section_title = _section_title_from_type(section_type)

    raw_order = section.get("section_order") or section.get("order") or index
    try:
        section_order = max(1, int(raw_order))
    except (TypeError, ValueError):
        section_order = index

    claims = section.get("claims") if isinstance(section.get("claims"), list) else []
    normalized_claims = [
        _normalize_gemini_claim(claim)
        for claim in claims
        if isinstance(claim, (dict, str))
    ]

    return {
        "section_title": section_title,
        "section_type": section_type,
        "section_order": section_order,
        "claims": normalized_claims,
    }


def _normalize_gemini_claim(claim: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(claim, str):
        return {
            "claim_text": claim,
            "claim_type": "general",
            "support_status": "unchecked",
            "citation_ids": [],
            "clinical_risk_level": "low",
        }

    claim_text = str(
        claim.get("claim_text")
        or claim.get("text")
        or claim.get("statement")
        or claim.get("summary")
        or ""
    ).strip()
    claim_type = _normalize_claim_type(claim.get("claim_type") or claim.get("type"))
    support_status = _normalize_support_status(
        claim.get("support_status") or claim.get("evidence_status") or claim.get("status")
    )
    risk_level = _normalize_risk_level(
        claim.get("clinical_risk_level") or claim.get("risk_level"),
        claim_type,
    )
    return {
        "claim_text": claim_text,
        "claim_type": claim_type,
        "support_status": support_status,
        "citation_ids": _normalize_citation_ids(claim.get("citation_ids") or claim.get("evidence_ids")),
        "clinical_risk_level": risk_level,
        "confidence_score": _normalize_confidence_score(claim.get("confidence_score") or claim.get("confidence")),
    }


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _normalize_language(value: Any, requested_language: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return ""
    if normalized in {requested_language.casefold(), requested_language.replace("-", "_").casefold()}:
        return requested_language
    if requested_language == "vi" and ("vietnamese" in normalized or normalized.startswith("vi")):
        return "vi"
    return str(value).strip()


def _normalize_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "yes", "1", "required"}
    return False


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_claim_type(value: Any) -> str:
    normalized = _normalize_token(value)
    normalized = CLAIM_TYPE_ALIASES.get(normalized, normalized)
    return normalized if normalized in ALLOWED_CLAIM_TYPES else "general"


def _normalize_support_status(value: Any) -> str:
    normalized = _normalize_token(value)
    return SUPPORT_STATUS_ALIASES.get(normalized, "unchecked")


def _normalize_risk_level(value: Any, claim_type: str) -> str:
    normalized = _normalize_token(value)
    supplied = normalized if normalized in ALLOWED_RISK_LEVELS else None
    return _risk_level(claim_type, supplied)


def _normalize_citation_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    citation_ids: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            citation_ids.append(item.strip())
        elif isinstance(item, dict):
            source_id = item.get("source_id") or item.get("citation_id") or item.get("id")
            if source_id and str(source_id).strip():
                citation_ids.append(str(source_id).strip())
    return citation_ids


def _normalize_confidence_score(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        score = Decimal(str(value))
    except Exception:
        return None
    if Decimal("0") <= score <= Decimal("1"):
        return score
    return None


def _section_title_from_type(section_type: str) -> str:
    return {
        section_key: section_title
        for section_title, section_key in DeterministicSummaryService.REQUIRED_SECTIONS
    }.get(section_type, "Needs Clinician Review")


def _should_persist_safety_note(note: str) -> bool:
    text = note.strip()
    if not text:
        return False
    lowered = text.casefold()
    meta_markers = (
        "ai-generated",
        "assistant",
        "clinician review before",
        "do not ",
        "draft requires",
        "instruction",
        "json",
        "must summarize",
        "output schema",
        "prompt",
        "requires doctor review",
        "return valid",
        "schema",
        "trợ lý",
        "không đề xuất",
        "phải tóm tắt",
    )
    if any(marker in lowered for marker in meta_markers):
        return False
    clinical_safety_markers = (
        "citation",
        "conflict",
        "conflicting",
        "evidence",
        "insufficient",
        "missing",
        "unsupported",
        "dị ứng",
        "không tìm thấy",
        "mâu thuẫn",
        "thiếu",
    )
    return any(marker in lowered for marker in clinical_safety_markers)


def _validation_hint(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "The response was not valid JSON."
    if isinstance(exc, ValidationError):
        errors = exc.errors(include_input=False)[:3]
        if not errors:
            return "The response did not match the required schema."
        details = []
        for error in errors:
            location = ".".join(str(part) for part in error.get("loc", ())) or "root"
            details.append(f"{location}: {error.get('type', 'validation_error')}")
        return "Validation hints: " + "; ".join(details)
    return "The response did not match the required schema."


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


def _split_claim_text(text: str) -> list[str]:
    claims: list[str] = []
    for raw_line in text.replace("\r", "\n").splitlines():
        line = raw_line.strip().strip("-*•0123456789. ")
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        claims.extend(part.strip() for part in parts if part.strip())
    if not claims:
        claims = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return claims[:20]


def _token_set(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\wÀ-ỹ]+", text.casefold(), flags=re.UNICODE)
        if len(token) > 2 and token not in {"the", "and", "for", "with", "patient"}
    }


def _infer_claim_type(text: str) -> str:
    lowered = text.casefold()
    if any(marker in lowered for marker in ("medication", "medicine", "drug", "dose", "dosage", "thuá»‘c")):
        return "medication"
    if any(marker in lowered for marker in ("creatinine", "lab", "laboratory", "hemoglobin", "glucose", "result", "observation")):
        return "lab_result"
    if any(marker in lowered for marker in ("x-ray", "ct ", "mri", "imaging", "diagnostic report", "ultrasound")):
        return "imaging_finding"
    if any(marker in lowered for marker in ("condition", "problem", "diagnosis", "diagnosed", "active problem")):
        return "diagnosis"
    if any(marker in lowered for marker in ("follow-up", "follow up", "pending")):
        return "follow_up"
    if any(marker in lowered for marker in ("visit", "course", "reported", "noted", "recorded")):
        return "timeline_event"
    return "general"


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
