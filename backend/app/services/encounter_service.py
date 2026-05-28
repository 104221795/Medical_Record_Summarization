from ..persistence_schemas import EncounterListResponse, EncounterResponse
from ..repositories import EncounterRepository, PatientRepository
from .persistence_common import PersistedResourceNotFoundError, require_uuid


class EncounterService:
    def __init__(self, repository: EncounterRepository, patients: PatientRepository):
        self.repository = repository
        self.patients = patients

    def list_by_patient(self, patient_id: str) -> EncounterListResponse:
        resolved_id = require_uuid(patient_id, "Patient")
        if self.patients.get(resolved_id) is None:
            raise PersistedResourceNotFoundError("Patient was not found.")
        return EncounterListResponse(
            items=[
                EncounterResponse.model_validate(encounter)
                for encounter in self.repository.list_by_patient(resolved_id)
            ]
        )

    def get(self, encounter_id: str) -> EncounterResponse:
        encounter = self.repository.get(require_uuid(encounter_id, "Encounter"))
        if encounter is None:
            raise PersistedResourceNotFoundError("Encounter was not found.")
        return EncounterResponse.model_validate(encounter)
