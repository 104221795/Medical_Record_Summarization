import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Patient


class PatientRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self, page: int, page_size: int, query: str | None = None) -> tuple[list[Patient], int]:
        statement = select(Patient)
        count_statement = select(func.count()).select_from(Patient)
        if query:
            search = f"%{query}%"
            predicate = or_(
                Patient.external_patient_id.ilike(search),
                Patient.patient_hash.ilike(search),
                Patient.fhir_patient_id.ilike(search),
            )
            statement = statement.where(predicate)
            count_statement = count_statement.where(predicate)
        total = self.session.scalar(count_statement) or 0
        items = list(
            self.session.scalars(
                statement.order_by(Patient.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        return items, total

    def get(self, patient_id: uuid.UUID) -> Patient | None:
        return self.session.get(Patient, patient_id)

    def find_source_identity(
        self, source_system: str, external_patient_id: str | None, fhir_patient_id: str | None
    ) -> Patient | None:
        predicates = []
        if external_patient_id:
            predicates.append(Patient.external_patient_id == external_patient_id)
        if fhir_patient_id:
            predicates.append(Patient.fhir_patient_id == fhir_patient_id)
        if not predicates:
            return None
        return self.session.scalar(
            select(Patient).where(Patient.source_system == source_system, or_(*predicates))
        )

    def add(self, patient: Patient) -> Patient:
        self.session.add(patient)
        return patient
