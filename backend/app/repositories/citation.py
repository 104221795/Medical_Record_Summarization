import uuid

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
)


class CitationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_citation(self, citation_id: uuid.UUID) -> ClaimCitation | None:
        return self.session.get(ClaimCitation, citation_id)

    def get_patient(self, patient_id: uuid.UUID) -> Patient | None:
        return self.session.get(Patient, patient_id)

    def get_encounter(self, encounter_id: uuid.UUID) -> Encounter | None:
        return self.session.get(Encounter, encounter_id)

    def get_document(self, document_id: uuid.UUID) -> ClinicalDocument | None:
        return self.session.get(ClinicalDocument, document_id)

    def get_chunk(self, chunk_id: uuid.UUID) -> DocumentChunk | None:
        return self.session.get(DocumentChunk, chunk_id)

    def get_condition(self, condition_id: uuid.UUID) -> Condition | None:
        return self.session.get(Condition, condition_id)

    def get_observation(self, observation_id: uuid.UUID) -> Observation | None:
        return self.session.get(Observation, observation_id)

    def get_medication(self, medication_id: uuid.UUID) -> Medication | None:
        return self.session.get(Medication, medication_id)

    def get_report(self, report_id: uuid.UUID) -> DiagnosticReport | None:
        return self.session.get(DiagnosticReport, report_id)
