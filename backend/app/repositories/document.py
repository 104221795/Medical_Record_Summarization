import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import ClinicalDocument, DocumentChunk


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_by_patient(
        self,
        patient_id: uuid.UUID,
        encounter_id: uuid.UUID | None = None,
        document_type: str | None = None,
    ) -> list[ClinicalDocument]:
        statement = select(ClinicalDocument).where(ClinicalDocument.patient_id == patient_id)
        if encounter_id:
            statement = statement.where(ClinicalDocument.encounter_id == encounter_id)
        if document_type:
            statement = statement.where(ClinicalDocument.document_type == document_type)
        return list(
            self.session.scalars(
                statement.order_by(
                    ClinicalDocument.document_datetime.desc(), ClinicalDocument.created_at.desc()
                )
            )
        )

    def get(self, document_id: uuid.UUID) -> ClinicalDocument | None:
        return self.session.get(ClinicalDocument, document_id)

    def list_chunks(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        return list(
            self.session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )

    def find_duplicate(
        self,
        *,
        source_system: str,
        patient_id: uuid.UUID,
        external_document_id: str | None,
        fhir_document_reference_id: str | None,
        fhir_composition_id: str | None,
        raw_text_hash: str,
    ) -> ClinicalDocument | None:
        identity_predicates = []
        if external_document_id:
            identity_predicates.append(ClinicalDocument.external_document_id == external_document_id)
        if fhir_document_reference_id:
            identity_predicates.append(
                ClinicalDocument.fhir_document_reference_id == fhir_document_reference_id
            )
        if fhir_composition_id:
            identity_predicates.append(ClinicalDocument.fhir_composition_id == fhir_composition_id)
        identity_predicates.append(ClinicalDocument.raw_text_hash == raw_text_hash)
        return self.session.scalar(
            select(ClinicalDocument).where(
                ClinicalDocument.source_system == source_system,
                ClinicalDocument.patient_id == patient_id,
                or_(*identity_predicates),
            )
        )

    def add(self, document: ClinicalDocument) -> ClinicalDocument:
        self.session.add(document)
        return document

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        self.session.add_all(chunks)
