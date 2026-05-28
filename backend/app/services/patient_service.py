from ..persistence_schemas import PatientDetailResponse, PatientListItem, PatientListResponse
from ..repositories import PatientRepository
from .persistence_common import PersistedResourceNotFoundError, pagination, require_uuid


class PatientService:
    def __init__(self, repository: PatientRepository):
        self.repository = repository

    def list(self, page: int, page_size: int, query: str | None = None) -> PatientListResponse:
        patients, total = self.repository.list(page, page_size, query)
        return PatientListResponse(
            items=[PatientListItem.model_validate(patient) for patient in patients],
            pagination=pagination(page, page_size, total),
        )

    def get(self, patient_id: str) -> PatientDetailResponse:
        patient = self.repository.get(require_uuid(patient_id, "Patient"))
        if patient is None:
            raise PersistedResourceNotFoundError("Patient was not found.")
        return PatientDetailResponse.model_validate(patient)
