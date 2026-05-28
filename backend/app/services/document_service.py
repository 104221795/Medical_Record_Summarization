import hashlib
import uuid

import tiktoken

from ..config import Settings
from ..models import ClinicalDocument as PersistedDocument
from ..models import DocumentChunk
from ..persistence_schemas import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
)
from ..repositories import DocumentRepository, PatientRepository
from ..schemas import ClinicalDocument as ChunkSourceDocument
from .chunking import ClinicalChunker
from .persistence_common import PersistedResourceNotFoundError, require_uuid


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        patients: PatientRepository,
        settings: Settings,
    ):
        self.repository = repository
        self.patients = patients
        self.chunker = ClinicalChunker(settings.chunk_max_chars, settings.chunk_overlap_sentences)
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def list_by_patient(
        self,
        patient_id: str,
        encounter_id: str | None = None,
        document_type: str | None = None,
    ) -> DocumentListResponse:
        resolved_patient_id = require_uuid(patient_id, "Patient")
        if self.patients.get(resolved_patient_id) is None:
            raise PersistedResourceNotFoundError("Patient was not found.")
        resolved_encounter_id = require_uuid(encounter_id, "Encounter") if encounter_id else None
        documents = self.repository.list_by_patient(
            resolved_patient_id, resolved_encounter_id, document_type
        )
        return DocumentListResponse(
            items=[DocumentListItem.model_validate(document) for document in documents]
        )

    def get(self, document_id: str) -> DocumentDetailResponse:
        document = self._require_document(document_id)
        return DocumentDetailResponse.model_validate(document)

    def list_chunks(self, document_id: str) -> DocumentChunkListResponse:
        document = self._require_document(document_id)
        return DocumentChunkListResponse(
            items=[
                DocumentChunkResponse.model_validate(chunk)
                for chunk in self.repository.list_chunks(document.document_id)
            ]
        )

    def create_chunks(self, document: PersistedDocument) -> int:
        chunk_source = ChunkSourceDocument(
            document_id=str(document.document_id),
            document_type=document.document_type,
            title=document.document_title,
            encounter_id=str(document.encounter_id) if document.encounter_id else None,
            authored_at=document.document_datetime,
            text=document.raw_text,
        )
        evidence_chunks = self.chunker.chunk_document(
            document.source_system or "database",
            str(document.patient_id),
            chunk_source,
        )
        chunks = [
            DocumentChunk(
                document_id=document.document_id,
                patient_id=document.patient_id,
                encounter_id=document.encounter_id,
                chunk_index=index,
                section_name=evidence.section,
                chunk_text=evidence.text,
                token_count=len(self.encoding.encode(evidence.text)),
                char_start=evidence.char_start,
                char_end=evidence.char_end,
                chunk_hash=hashlib.sha256(evidence.text.encode("utf-8")).hexdigest(),
            )
            for index, evidence in enumerate(evidence_chunks)
        ]
        self.repository.add_chunks(chunks)
        return len(chunks)

    def _require_document(self, document_id: str) -> PersistedDocument:
        document = self.repository.get(require_uuid(document_id, "Document"))
        if document is None:
            raise PersistedResourceNotFoundError("Document was not found.")
        return document
