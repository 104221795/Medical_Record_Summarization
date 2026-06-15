from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from ..models import (
    ClinicalDocument as PersistedClinicalDocument,
    Condition,
    DiagnosticReport,
    DocumentChunk,
    Encounter,
    Medication,
    Observation,
    Patient,
)
from ..schemas import ClinicalDocument, EvidenceChunk, IngestRequest
from ..evaluation.clinical_context_builder import (
    SECTION_QUERIES,
    classify_evidence_section,
    clinical_salience_score,
    normalize_evidence_section,
)
from .rag import RagService


REQUIRED_RETRIEVAL_SECTIONS = ("DIAGNOSIS", "MEDICATIONS", "TIMELINE")
OPTIONAL_RETRIEVAL_SECTIONS = ("DIAGNOSTICS", "ASSESSMENT", "PLAN")
CONFLICT_MARKER_RE = re.compile(
    r"\b(denies|denied|no evidence of|no known|without|negative for|contraindicat\w*|"
    r"allerg\w*|discontinu\w*|stopp\w*|resolved|rule out|r/o)\b",
    re.I,
)


class DoctorRagError(RuntimeError):
    pass


@dataclass
class RagCitationDraft:
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


@dataclass(frozen=True)
class SectionRetrievalResult:
    section: str
    query: str
    requested_top_k: int
    retrieved_count: int
    selected_count: int
    max_score: float | None = None


@dataclass(frozen=True)
class RetrievalQualityGate:
    status: str
    section_results: list[SectionRetrievalResult]
    missing_required_sections: list[str] = field(default_factory=list)
    missing_optional_sections: list[str] = field(default_factory=list)
    scope_errors: list[str] = field(default_factory=list)
    conflict_evidence: list[dict[str, Any]] = field(default_factory=list)

    @property
    def should_block_generation(self) -> bool:
        return self.status == "fail"

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "missing_required_sections": self.missing_required_sections,
            "missing_optional_sections": self.missing_optional_sections,
            "scope_errors": self.scope_errors,
            "conflict_evidence": self.conflict_evidence,
            "section_results": [
                {
                    "section": item.section,
                    "query": item.query,
                    "requested_top_k": item.requested_top_k,
                    "retrieved_count": item.retrieved_count,
                    "selected_count": item.selected_count,
                    "max_score": item.max_score,
                }
                for item in self.section_results
            ],
        }


@dataclass(frozen=True)
class DoctorRagEvidenceResult:
    evidence_pack: dict[str, Any]
    citation_lookup: dict[str, RagCitationDraft]
    quality_gate: RetrievalQualityGate
    ingestion: dict[str, Any]


class DoctorRagWorkflow:
    """Build the doctor-facing evidence pack through the real MiniLM/Qdrant RAG path."""

    def __init__(self, rag_service: RagService):
        self.rag_service = rag_service

    def build_evidence_pack(
        self,
        *,
        tenant_id: str,
        patient: Patient,
        encounter: Encounter | None,
        context: dict[str, list],
        summary_type: str,
        language: str,
    ) -> DoctorRagEvidenceResult:
        patient_id = str(patient.patient_id)
        encounter_id = str(encounter.encounter_id) if encounter else None
        documents = self._source_documents(patient, encounter, context)
        if not documents:
            raise DoctorRagError("No patient/encounter scoped notes are available for RAG retrieval.")

        ingestion = self.rag_service.ingest(
            tenant_id,
            patient_id,
            IngestRequest(documents=documents, replace_patient_index=True),
        )
        selected, section_results, scope_errors = self._section_aware_retrieve(
            tenant_id=tenant_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
        )
        gate = self._quality_gate(selected, section_results, scope_errors)
        if gate.should_block_generation:
            raise DoctorRagError(
                "RAG retrieval quality gate failed before generation: "
                + "; ".join(gate.scope_errors or ["no patient-scoped evidence retrieved"])
            )

        evidence, citation_lookup = self._evidence_items(
            patient=patient,
            encounter=encounter,
            chunks=selected,
        )
        age = _age(patient.date_of_birth)
        return DoctorRagEvidenceResult(
            evidence_pack={
                "request": {
                    "summary_type": summary_type,
                    "language": language,
                    "patient_id": patient_id,
                    "encounter_id": encounter_id,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "generation_flow": "flow_2_rag_minilm_qdrant",
                    "proxy_warning": (
                        "AI-generated summary is a draft. Clinician review and citation validation are required."
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
                "retrieval_quality_gate": gate.model_dump(),
                "retrieval_config": {
                    "embedding_provider": self.rag_service.embedding_provider.name,
                    "embedding_model": getattr(self.rag_service.embedding_provider, "model_name", None),
                    "vector_collection": self.rag_service.settings.qdrant_collection,
                    "top_k_per_section": self._top_k_per_section(),
                    "section_queries": SECTION_QUERIES,
                    "reranking": "vector_score_plus_clinical_section_salience",
                },
                "evidence": evidence,
            },
            citation_lookup=citation_lookup,
            quality_gate=gate,
            ingestion={
                "documents_received": ingestion.documents_received,
                "chunks_indexed": ingestion.chunks_indexed,
                "embedding_provider": ingestion.embedding_provider,
                "vector_collection": ingestion.vector_collection,
            },
        )

    def _section_aware_retrieve(
        self,
        *,
        tenant_id: str,
        patient_id: str,
        encounter_id: str | None,
    ) -> tuple[list[EvidenceChunk], list[SectionRetrievalResult], list[str]]:
        selected_by_key: dict[str, EvidenceChunk] = {}
        section_results: list[SectionRetrievalResult] = []
        scope_errors: list[str] = []
        top_k = self._top_k_per_section()
        for section, query in SECTION_QUERIES.items():
            response = self.rag_service.retrieve(tenant_id, patient_id, query, top_k)
            scoped: list[EvidenceChunk] = []
            wrong_scope_count = 0
            for chunk in response.evidence:
                valid, reason = self._valid_scope(chunk, patient_id, encounter_id)
                if valid:
                    scoped.append(chunk)
                else:
                    wrong_scope_count += 1
                    if reason:
                        scope_errors.append(reason)
            ranked = self._rerank(section, scoped)
            for chunk in ranked[:3]:
                key = f"{chunk.document_id}:{chunk.char_start}:{chunk.char_end}"
                current = selected_by_key.get(key)
                if current is None or float(chunk.score or 0.0) > float(current.score or 0.0):
                    selected_by_key[key] = chunk
            section_results.append(
                SectionRetrievalResult(
                    section=section,
                    query=query,
                    requested_top_k=top_k,
                    retrieved_count=len(response.evidence),
                    selected_count=len(ranked[:3]),
                    max_score=max((float(item.score or 0.0) for item in ranked), default=None),
                )
            )
            if wrong_scope_count:
                scope_errors.append(f"{section}: dropped {wrong_scope_count} wrong-scope retrieval result(s).")

        selected = sorted(
            selected_by_key.values(),
            key=lambda item: float(item.score or 0.0),
            reverse=True,
        )
        return selected[: self._max_total_evidence()], section_results, sorted(set(scope_errors))

    def _quality_gate(
        self,
        chunks: list[EvidenceChunk],
        section_results: list[SectionRetrievalResult],
        scope_errors: list[str],
    ) -> RetrievalQualityGate:
        section_counts = {section: 0 for section in SECTION_QUERIES}
        for chunk in chunks:
            section = normalize_evidence_section(chunk.section) or classify_evidence_section(chunk)
            section_counts[section] = section_counts.get(section, 0) + 1
        missing_required = [
            section for section in REQUIRED_RETRIEVAL_SECTIONS if section_counts.get(section, 0) == 0
        ]
        missing_optional = [
            section for section in OPTIONAL_RETRIEVAL_SECTIONS if section_counts.get(section, 0) == 0
        ]
        conflicts = [
            {
                "chunk_id": chunk.chunk_id,
                "section": chunk.section,
                "text": _compact(chunk.text, 260),
            }
            for chunk in chunks
            if CONFLICT_MARKER_RE.search(chunk.text or "")
        ][:6]
        status = "pass"
        if not chunks or any("wrong patient" in item.casefold() for item in scope_errors):
            status = "fail"
        elif missing_required or missing_optional or conflicts or scope_errors:
            status = "warning"
        return RetrievalQualityGate(
            status=status,
            section_results=section_results,
            missing_required_sections=missing_required,
            missing_optional_sections=missing_optional,
            scope_errors=scope_errors,
            conflict_evidence=conflicts,
        )

    def _rerank(self, target_section: str, chunks: list[EvidenceChunk]) -> list[EvidenceChunk]:
        ranked: list[EvidenceChunk] = []
        for chunk in chunks:
            normalized = normalize_evidence_section(chunk.section) or classify_evidence_section(chunk)
            section_bonus = 1.5 if normalized == target_section else 0.0
            salience = clinical_salience_score(chunk, target_section)
            vector_score = float(chunk.score or 0.0)
            rerank_score = vector_score + section_bonus + (0.15 * salience)
            ranked.append(chunk.model_copy(update={"section": normalized, "score": round(rerank_score, 6)}))
        return sorted(ranked, key=lambda item: float(item.score or 0.0), reverse=True)

    def _valid_scope(
        self,
        chunk: EvidenceChunk,
        patient_id: str,
        encounter_id: str | None,
    ) -> tuple[bool, str | None]:
        if str(chunk.patient_id) != patient_id:
            return False, f"Wrong patient retrieval prevented for chunk {chunk.chunk_id}."
        if encounter_id:
            chunk_encounter = str(chunk.encounter_id or "")
            if chunk_encounter and chunk_encounter != encounter_id:
                return False, f"Wrong encounter retrieval prevented for chunk {chunk.chunk_id}."
        return True, None

    def _source_documents(
        self,
        patient: Patient,
        encounter: Encounter | None,
        context: dict[str, list],
    ) -> list[ClinicalDocument]:
        documents: list[ClinicalDocument] = []
        age = _age(patient.date_of_birth)
        documents.append(
            ClinicalDocument(
                document_id=str(patient.patient_id),
                document_type="patient",
                title="Patient snapshot",
                encounter_id=None,
                authored_at=None,
                text=_lines(
                    "PATIENT SNAPSHOT:",
                    f"Gender: {patient.gender}" if patient.gender else None,
                    f"Age: {age}" if age is not None else None,
                    "Data status: de-identified" if patient.is_deidentified else None,
                ),
            )
        )
        if encounter:
            documents.append(
                ClinicalDocument(
                    document_id=str(encounter.encounter_id),
                    document_type="encounter",
                    title="Encounter context",
                    encounter_id=str(encounter.encounter_id),
                    authored_at=encounter.start_time,
                    text=_lines(
                        "TIMELINE:",
                        f"Encounter type: {encounter.encounter_type}" if encounter.encounter_type else None,
                        f"Status: {encounter.status}" if encounter.status else None,
                        f"Department: {encounter.department}" if encounter.department else None,
                        f"Reason for visit: {encounter.reason_for_visit}" if encounter.reason_for_visit else None,
                    ),
                )
            )
        documents.extend(self._condition_documents(context.get("conditions", [])))
        documents.extend(self._medication_documents(context.get("medications", [])))
        documents.extend(self._observation_documents(context.get("observations", [])))
        documents.extend(self._diagnostic_report_documents(context.get("diagnostic_reports", [])))
        documents.extend(self._clinical_documents(context.get("documents", [])))
        if not any(item.document_type == "clinical_document" for item in documents):
            documents.extend(self._chunk_documents(context.get("chunks", [])))
        return [document for document in documents if document.text.strip()]

    def _condition_documents(self, conditions: list[Condition]) -> list[ClinicalDocument]:
        return [
            ClinicalDocument(
                document_id=str(item.condition_id),
                document_type="condition",
                title=item.condition_name,
                encounter_id=str(item.encounter_id) if item.encounter_id else None,
                authored_at=item.recorded_date,
                text=_lines(
                    "DIAGNOSIS:",
                    f"Condition: {item.condition_name}",
                    f"Clinical status: {item.clinical_status}" if item.clinical_status else None,
                    f"Verification status: {item.verification_status}" if item.verification_status else None,
                ),
            )
            for item in conditions
        ]

    def _medication_documents(self, medications: list[Medication]) -> list[ClinicalDocument]:
        return [
            ClinicalDocument(
                document_id=str(item.medication_id),
                document_type="medication",
                title=item.medication_name,
                encounter_id=str(item.encounter_id) if item.encounter_id else None,
                authored_at=datetime.combine(item.start_date, datetime.min.time(), tzinfo=UTC)
                if item.start_date
                else None,
                text=_lines(
                    "MEDICATIONS:",
                    f"Medication: {item.medication_name}",
                    f"Status: {item.status}" if item.status else None,
                    f"Dosage: {item.dosage_text}" if item.dosage_text else None,
                    f"Route: {item.route}" if item.route else None,
                    f"Frequency: {item.frequency}" if item.frequency else None,
                ),
            )
            for item in medications
        ]

    def _observation_documents(self, observations: list[Observation]) -> list[ClinicalDocument]:
        documents: list[ClinicalDocument] = []
        for item in observations:
            value = item.value_text
            if value is None and item.value_numeric is not None:
                value = f"{item.value_numeric:g}"
                if item.unit:
                    value = f"{value} {item.unit}"
            documents.append(
                ClinicalDocument(
                    document_id=str(item.observation_id),
                    document_type="observation",
                    title=item.observation_name,
                    encounter_id=str(item.encounter_id) if item.encounter_id else None,
                    authored_at=item.observed_at,
                    text=_lines(
                        "DIAGNOSTICS:",
                        f"Observation: {item.observation_name}",
                        f"Value: {value}" if value else None,
                        f"Type: {item.observation_type}" if item.observation_type else None,
                        f"Interpretation: {item.interpretation}" if item.interpretation else None,
                    ),
                )
            )
        return documents

    def _diagnostic_report_documents(self, reports: list[DiagnosticReport]) -> list[ClinicalDocument]:
        return [
            ClinicalDocument(
                document_id=str(item.report_id),
                document_type="diagnostic_report",
                title=item.report_title or item.report_type or "Diagnostic report",
                encounter_id=str(item.encounter_id) if item.encounter_id else None,
                authored_at=item.reported_at or item.performed_at,
                text=_lines(
                    "DIAGNOSTICS:",
                    f"Report: {item.report_title or item.report_type}" if (item.report_title or item.report_type) else None,
                    f"Status: {item.report_status}" if item.report_status else None,
                    f"Conclusion: {item.conclusion_text}" if item.conclusion_text else None,
                    item.report_text,
                ),
            )
            for item in reports
        ]

    def _clinical_documents(self, documents: list[PersistedClinicalDocument]) -> list[ClinicalDocument]:
        return [
            ClinicalDocument(
                document_id=str(item.document_id),
                document_type="clinical_document",
                title=item.document_title or item.document_type,
                encounter_id=str(item.encounter_id) if item.encounter_id else None,
                authored_at=item.document_datetime,
                text=item.raw_text,
            )
            for item in documents
            if item.raw_text
        ]

    def _chunk_documents(self, chunks: list[DocumentChunk]) -> list[ClinicalDocument]:
        return [
            ClinicalDocument(
                document_id=str(item.chunk_id),
                document_type="document_chunk",
                title=item.section_name or "Persisted document chunk",
                encounter_id=str(item.encounter_id) if item.encounter_id else None,
                authored_at=item.created_at,
                text=item.chunk_text,
            )
            for item in chunks
            if item.chunk_text
        ]

    def _evidence_items(
        self,
        *,
        patient: Patient,
        encounter: Encounter | None,
        chunks: list[EvidenceChunk],
    ) -> tuple[list[dict[str, Any]], dict[str, RagCitationDraft]]:
        evidence: list[dict[str, Any]] = []
        citation_lookup: dict[str, RagCitationDraft] = {}
        for chunk in chunks:
            source_id = f"chunk:{chunk.chunk_id}"
            source_type = _source_type_from_document_type(chunk.document_type)
            citation = _citation_for_retrieved_chunk(chunk, patient, encounter)
            citation_lookup[source_id] = citation
            evidence.append(
                {
                    "source_id": source_id,
                    "source_type": source_type,
                    "patient_id": str(patient.patient_id),
                    "encounter_id": chunk.encounter_id,
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "timestamp": chunk.authored_at,
                    "metadata": {
                        "rag_chunk_id": chunk.chunk_id,
                        "document_type": chunk.document_type,
                        "title": chunk.title,
                        "section_name": chunk.section,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                        "retrieval_score": chunk.score,
                    },
                }
            )
        return evidence, citation_lookup

    def _top_k_per_section(self) -> int:
        return max(4, min(12, int(self.rag_service.settings.retrieval_top_k or 6)))

    def _max_total_evidence(self) -> int:
        return max(10, min(24, self._top_k_per_section() * 3))


def _citation_for_retrieved_chunk(
    chunk: EvidenceChunk,
    patient: Patient,
    encounter: Encounter | None,
) -> RagCitationDraft:
    source_uuid = _uuid_or_none(chunk.document_id)
    document_type = chunk.document_type
    kwargs: dict[str, Any] = {
        "source_type": _source_type_from_document_type(document_type),
        "source_text_span": chunk.text,
        "source_char_start": chunk.char_start,
        "source_char_end": chunk.char_end,
        "citation_confidence": Decimal("0.92"),
    }
    if document_type == "condition" and source_uuid:
        kwargs["source_condition_id"] = source_uuid
    elif document_type == "observation" and source_uuid:
        kwargs["source_observation_id"] = source_uuid
    elif document_type == "medication" and source_uuid:
        kwargs["source_medication_id"] = source_uuid
    elif document_type == "diagnostic_report" and source_uuid:
        kwargs["source_report_id"] = source_uuid
    elif document_type == "clinical_document" and source_uuid:
        kwargs["source_document_id"] = source_uuid
    elif document_type == "document_chunk" and source_uuid:
        kwargs["source_chunk_id"] = source_uuid
    elif document_type == "encounter" and encounter:
        kwargs["source_record_type"] = "encounter"
        kwargs["source_record_id"] = encounter.encounter_id
    else:
        kwargs["source_record_type"] = "patient"
        kwargs["source_record_id"] = patient.patient_id
    return RagCitationDraft(**kwargs)


def _source_type_from_document_type(document_type: str) -> str:
    if document_type in {
        "condition",
        "observation",
        "medication",
        "diagnostic_report",
        "clinical_document",
        "document_chunk",
        "patient",
        "encounter",
    }:
        return document_type
    return "document_chunk"


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _lines(*values: str | None) -> str:
    return "\n".join(str(value).strip() for value in values if value and str(value).strip())


def _compact(value: str | None, limit: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."
