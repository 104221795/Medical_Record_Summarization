import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Encounter


class EncounterRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_by_patient(self, patient_id: uuid.UUID) -> list[Encounter]:
        return list(
            self.session.scalars(
                select(Encounter)
                .where(Encounter.patient_id == patient_id)
                .order_by(Encounter.start_time.desc(), Encounter.created_at.desc())
            )
        )

    def get(self, encounter_id: uuid.UUID) -> Encounter | None:
        return self.session.get(Encounter, encounter_id)

    def find_source_identity(
        self, source_system: str, external_encounter_id: str | None, fhir_encounter_id: str | None
    ) -> Encounter | None:
        predicates = []
        if external_encounter_id:
            predicates.append(Encounter.external_encounter_id == external_encounter_id)
        if fhir_encounter_id:
            predicates.append(Encounter.fhir_encounter_id == fhir_encounter_id)
        if not predicates:
            return None
        return self.session.scalar(
            select(Encounter).where(Encounter.source_system == source_system, or_(*predicates))
        )

    def add(self, encounter: Encounter) -> Encounter:
        self.session.add(encounter)
        return encounter
