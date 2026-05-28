import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, Patient, Summary


class ClinicalRepository:
    """Small transaction-scoped repository for foundational persisted records."""

    def __init__(self, session: Session):
        self.session = session

    def find_patient_by_external_id(self, external_patient_id: str) -> Patient | None:
        return self.session.scalar(
            select(Patient).where(Patient.external_patient_id == external_patient_id)
        )

    def find_summary(self, summary_id: uuid.UUID) -> Summary | None:
        return self.session.get(Summary, summary_id)

    def record_audit_event(
        self,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        event = AuditLog(
            user_id=user_id,
            patient_id=patient_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata,
            timestamp=datetime.now(UTC),
        )
        self.session.add(event)
        return event
