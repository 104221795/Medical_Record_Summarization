from __future__ import annotations

import uuid

from ..models import ClaimCitation, SummaryClaim
from ..persistence_schemas import (
    CitationDocumentMetadata,
    CitationHighlightedSpan,
    CitationSourceResponse,
    ClaimCitationListResponse,
    ClaimCitationResponse,
)
from ..repositories import CitationRepository, SummaryRepository
from .audit_service import AuditService
from .persistence_common import PersistedResourceNotFoundError


class CitationService:
    def __init__(
        self,
        summaries: SummaryRepository,
        citations: CitationRepository,
        audit_service: AuditService,
    ):
        self.summaries = summaries
        self.citations = citations
        self.audit_service = audit_service

    def list_by_claim(self, claim_id: str) -> ClaimCitationListResponse:
        claim = self._claim(claim_id)
        return ClaimCitationListResponse(
            claim_id=claim.claim_id,
            citations=[ClaimCitationResponse.model_validate(item) for item in claim.citations],
        )

    def source(
        self,
        citation_id: str,
        *,
        tenant_id: str,
        actor_external_id: str,
    ) -> CitationSourceResponse:
        citation = self._citation(citation_id)
        claim = citation.claim
        patient_id = claim.summary.patient_id
        response = self._source_response(citation, patient_id)
        self.audit_service.record(
            action="view_citation",
            patient_id=patient_id,
            resource_type="claim_citation",
            resource_id=citation.citation_id,
            metadata={"tenant_id": tenant_id, "actor_external_id": actor_external_id},
        )
        return response

    def _claim(self, claim_id: str) -> SummaryClaim:
        try:
            resolved_id = uuid.UUID(claim_id)
        except ValueError as exc:
            raise PersistedResourceNotFoundError("Claim was not found.") from exc
        claim = self.summaries.get_claim(resolved_id)
        if claim is None:
            raise PersistedResourceNotFoundError("Claim was not found.")
        return claim

    def _citation(self, citation_id: str) -> ClaimCitation:
        try:
            resolved_id = uuid.UUID(citation_id)
        except ValueError as exc:
            raise PersistedResourceNotFoundError("Citation was not found.") from exc
        citation = self.summaries.get_citation(resolved_id)
        if citation is None:
            raise PersistedResourceNotFoundError("Citation was not found.")
        return citation

    def _source_response(self, citation: ClaimCitation, patient_id: uuid.UUID) -> CitationSourceResponse:
        if citation.source_chunk_id:
            chunk = self.citations.get_chunk(citation.source_chunk_id)
            if chunk is None or chunk.patient_id != patient_id:
                raise PersistedResourceNotFoundError("Citation source was not found.")
            document = self.citations.get_document(chunk.document_id)
            return CitationSourceResponse(
                citation_id=citation.citation_id,
                claim_id=citation.claim_id,
                patient_id=patient_id,
                source_type=citation.source_type,
                document=_document_metadata(document) if document else None,
                highlighted_span=CitationHighlightedSpan(
                    text=citation.source_text_span or chunk.chunk_text,
                    char_start=citation.source_char_start,
                    char_end=citation.source_char_end,
                ),
                surrounding_context=chunk.chunk_text,
                source_metadata={"chunk_index": chunk.chunk_index, "section_name": chunk.section_name},
            )
        if citation.source_document_id:
            document = self.citations.get_document(citation.source_document_id)
            if document is None or document.patient_id != patient_id:
                raise PersistedResourceNotFoundError("Citation source was not found.")
            return CitationSourceResponse(
                citation_id=citation.citation_id,
                claim_id=citation.claim_id,
                patient_id=patient_id,
                source_type=citation.source_type,
                document=_document_metadata(document),
                highlighted_span=CitationHighlightedSpan(
                    text=citation.source_text_span,
                    char_start=citation.source_char_start,
                    char_end=citation.source_char_end,
                ),
                surrounding_context=_context_window(
                    document.raw_text,
                    citation.source_char_start,
                    citation.source_char_end,
                ),
            )
        structured = self._structured_source(citation, patient_id)
        if structured:
            return structured
        if citation.source_record_id and citation.source_record_type:
            return self._generic_source(citation, patient_id)
        raise PersistedResourceNotFoundError("Citation source was not found.")

    def _structured_source(
        self, citation: ClaimCitation, patient_id: uuid.UUID
    ) -> CitationSourceResponse | None:
        source = None
        metadata = {}
        if citation.source_condition_id:
            source = self.citations.get_condition(citation.source_condition_id)
            metadata = {
                "condition_name": source.condition_name if source else None,
                "clinical_status": source.clinical_status if source else None,
            }
        elif citation.source_observation_id:
            source = self.citations.get_observation(citation.source_observation_id)
            metadata = {
                "observation_name": source.observation_name if source else None,
                "value_text": source.value_text if source else None,
                "value_numeric": str(source.value_numeric) if source and source.value_numeric is not None else None,
                "unit": source.unit if source else None,
            }
        elif citation.source_medication_id:
            source = self.citations.get_medication(citation.source_medication_id)
            metadata = {
                "medication_name": source.medication_name if source else None,
                "status": source.status if source else None,
                "dosage_text": source.dosage_text if source else None,
            }
        elif citation.source_report_id:
            source = self.citations.get_report(citation.source_report_id)
            metadata = {
                "report_title": source.report_title if source else None,
                "report_status": source.report_status if source else None,
            }
        if source is None:
            return None
        if source.patient_id != patient_id:
            raise PersistedResourceNotFoundError("Citation source was not found.")
        return CitationSourceResponse(
            citation_id=citation.citation_id,
            claim_id=citation.claim_id,
            patient_id=patient_id,
            source_type=citation.source_type,
            highlighted_span=CitationHighlightedSpan(
                text=citation.source_text_span,
                char_start=citation.source_char_start,
                char_end=citation.source_char_end,
            ),
            surrounding_context=citation.source_text_span,
            source_metadata=metadata,
        )

    def _generic_source(
        self, citation: ClaimCitation, patient_id: uuid.UUID
    ) -> CitationSourceResponse:
        metadata = {}
        if citation.source_record_type == "patient":
            patient = self.citations.get_patient(citation.source_record_id)
            if patient is None or patient.patient_id != patient_id:
                raise PersistedResourceNotFoundError("Citation source was not found.")
            metadata = {
                "patient_hash": patient.patient_hash,
                "external_patient_id": patient.external_patient_id,
                "gender": patient.gender,
            }
        elif citation.source_record_type == "encounter":
            encounter = self.citations.get_encounter(citation.source_record_id)
            if encounter is None or encounter.patient_id != patient_id:
                raise PersistedResourceNotFoundError("Citation source was not found.")
            metadata = {
                "encounter_type": encounter.encounter_type,
                "status": encounter.status,
                "reason_for_visit": encounter.reason_for_visit,
            }
        else:
            raise PersistedResourceNotFoundError("Citation source was not found.")
        return CitationSourceResponse(
            citation_id=citation.citation_id,
            claim_id=citation.claim_id,
            patient_id=patient_id,
            source_type=citation.source_type,
            highlighted_span=CitationHighlightedSpan(
                text=citation.source_text_span,
                char_start=citation.source_char_start,
                char_end=citation.source_char_end,
            ),
            surrounding_context=citation.source_text_span,
            source_metadata=metadata,
        )


def _document_metadata(document) -> CitationDocumentMetadata:
    return CitationDocumentMetadata(
        document_id=document.document_id,
        document_title=document.document_title,
        document_type=document.document_type,
        document_datetime=document.document_datetime,
        source_system=document.source_system,
    )


def _context_window(text: str, start: int | None, end: int | None, radius: int = 120) -> str:
    if start is None or end is None:
        return text[: radius * 2]
    return text[max(0, start - radius) : min(len(text), end + radius)]
