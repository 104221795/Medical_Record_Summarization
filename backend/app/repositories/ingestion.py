from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Condition, DiagnosticReport, Medication, Observation


class IngestionRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_condition(self, source_system: str, external_id: str | None, fhir_id: str | None) -> Condition | None:
        return self._find(Condition, source_system, Condition.external_condition_id, external_id,
                          Condition.fhir_condition_id, fhir_id)

    def find_observation(
        self, source_system: str, external_id: str | None, fhir_id: str | None
    ) -> Observation | None:
        return self._find(Observation, source_system, Observation.external_observation_id, external_id,
                          Observation.fhir_observation_id, fhir_id)

    def find_medication(
        self, source_system: str, external_id: str | None, fhir_id: str | None
    ) -> Medication | None:
        return self._find(Medication, source_system, Medication.external_medication_id, external_id,
                          Medication.fhir_medication_request_id, fhir_id)

    def find_report(
        self, source_system: str, external_id: str | None, fhir_id: str | None
    ) -> DiagnosticReport | None:
        return self._find(DiagnosticReport, source_system, DiagnosticReport.external_report_id, external_id,
                          DiagnosticReport.fhir_diagnostic_report_id, fhir_id)

    def add(self, record: object) -> None:
        self.session.add(record)

    def _find(
        self,
        model: type,
        source_system: str,
        external_column: object,
        external_id: str | None,
        fhir_column: object,
        fhir_id: str | None,
    ) -> object | None:
        predicates = []
        if external_id:
            predicates.append(external_column == external_id)
        if fhir_id:
            predicates.append(fhir_column == fhir_id)
        if not predicates:
            return None
        return self.session.scalar(
            select(model).where(model.source_system == source_system, or_(*predicates))
        )
