from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import (
    ClaimCitation,
    ClinicalDocument,
    Condition,
    DiagnosticReport,
    DocumentChunk,
    Encounter,
    Medication,
    Observation,
    Patient,
    Summary,
)


@dataclass(frozen=True)
class CitationScopeViolation:
    claim_id: uuid.UUID
    citation_id: uuid.UUID
    violation_type: str
    source_type: str
    expected_patient_id: uuid.UUID
    actual_patient_id: uuid.UUID | None = None
    expected_encounter_id: uuid.UUID | None = None
    actual_encounter_id: uuid.UUID | None = None
    message: str = ""

    def as_dict(self) -> dict[str, str | None]:
        return {
            "claim_id": str(self.claim_id),
            "citation_id": str(self.citation_id),
            "violation_type": self.violation_type,
            "source_type": self.source_type,
            "expected_patient_id": str(self.expected_patient_id),
            "actual_patient_id": str(self.actual_patient_id) if self.actual_patient_id else None,
            "expected_encounter_id": str(self.expected_encounter_id) if self.expected_encounter_id else None,
            "actual_encounter_id": str(self.actual_encounter_id) if self.actual_encounter_id else None,
            "message": self.message,
        }


@dataclass(frozen=True)
class _CitationSourceScope:
    source_type: str
    patient_id: uuid.UUID | None
    encounter_id: uuid.UUID | None


def validate_summary_citation_scope(
    summary: Summary,
    session: Session,
    *,
    enforce_encounter_scope: bool = True,
) -> list[CitationScopeViolation]:
    """Validate that every cited source belongs to the summary patient/encounter.

    Patient scope is strict. Encounter scope is enforced when both the summary and
    source are encounter-specific, which keeps patient-level evidence usable while
    blocking wrong-encounter citations.
    """

    violations: list[CitationScopeViolation] = []
    for claim in summary.claims:
        for citation in claim.citations:
            source = _citation_source_scope(citation, session)
            if source.patient_id is None:
                violations.append(
                    CitationScopeViolation(
                        claim_id=claim.claim_id,
                        citation_id=citation.citation_id,
                        violation_type="missing_source",
                        source_type=source.source_type,
                        expected_patient_id=summary.patient_id,
                        expected_encounter_id=summary.encounter_id,
                        message="Citation source could not be resolved.",
                    )
                )
                continue
            if source.patient_id != summary.patient_id:
                violations.append(
                    CitationScopeViolation(
                        claim_id=claim.claim_id,
                        citation_id=citation.citation_id,
                        violation_type="wrong_patient",
                        source_type=source.source_type,
                        expected_patient_id=summary.patient_id,
                        actual_patient_id=source.patient_id,
                        expected_encounter_id=summary.encounter_id,
                        actual_encounter_id=source.encounter_id,
                        message="Citation source belongs to a different patient.",
                    )
                )
            if (
                enforce_encounter_scope
                and summary.encounter_id is not None
                and source.encounter_id is not None
                and source.encounter_id != summary.encounter_id
            ):
                violations.append(
                    CitationScopeViolation(
                        claim_id=claim.claim_id,
                        citation_id=citation.citation_id,
                        violation_type="wrong_encounter",
                        source_type=source.source_type,
                        expected_patient_id=summary.patient_id,
                        actual_patient_id=source.patient_id,
                        expected_encounter_id=summary.encounter_id,
                        actual_encounter_id=source.encounter_id,
                        message="Citation source belongs to a different encounter.",
                    )
                )
    return violations


def summarize_scope_violations(
    violations: list[CitationScopeViolation],
    *,
    limit: int = 3,
) -> str:
    if not violations:
        return "No citation scope violations detected."
    examples = ", ".join(
        f"{item.violation_type}:{item.citation_id}" for item in violations[:limit]
    )
    suffix = f" (+{len(violations) - limit} more)" if len(violations) > limit else ""
    return f"{len(violations)} citation scope violation(s): {examples}{suffix}"


def _citation_source_scope(citation: ClaimCitation, session: Session) -> _CitationSourceScope:
    if citation.source_chunk_id:
        return _scope_from_model(
            "document_chunk",
            session.get(DocumentChunk, citation.source_chunk_id),
        )
    if citation.source_document_id:
        return _scope_from_model(
            "clinical_document",
            session.get(ClinicalDocument, citation.source_document_id),
        )
    if citation.source_condition_id:
        return _scope_from_model(
            "condition",
            session.get(Condition, citation.source_condition_id),
        )
    if citation.source_observation_id:
        return _scope_from_model(
            "observation",
            session.get(Observation, citation.source_observation_id),
        )
    if citation.source_medication_id:
        return _scope_from_model(
            "medication",
            session.get(Medication, citation.source_medication_id),
        )
    if citation.source_report_id:
        return _scope_from_model(
            "diagnostic_report",
            session.get(DiagnosticReport, citation.source_report_id),
        )
    if citation.source_record_id and citation.source_record_type == "patient":
        patient = session.get(Patient, citation.source_record_id)
        return _CitationSourceScope(
            source_type="patient",
            patient_id=patient.patient_id if patient else None,
            encounter_id=None,
        )
    if citation.source_record_id and citation.source_record_type == "encounter":
        encounter = session.get(Encounter, citation.source_record_id)
        return _CitationSourceScope(
            source_type="encounter",
            patient_id=encounter.patient_id if encounter else None,
            encounter_id=encounter.encounter_id if encounter else None,
        )
    return _CitationSourceScope(
        source_type=citation.source_type or citation.source_record_type or "unknown",
        patient_id=None,
        encounter_id=None,
    )


def _scope_from_model(source_type: str, source: object | None) -> _CitationSourceScope:
    return _CitationSourceScope(
        source_type=source_type,
        patient_id=getattr(source, "patient_id", None),
        encounter_id=getattr(source, "encounter_id", None),
    )
