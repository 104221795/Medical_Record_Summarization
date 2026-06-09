import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AuditLog, ModelRun, Summary, User


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, event: AuditLog) -> AuditLog:
        self.session.add(event)
        return event

    def get(self, audit_id: uuid.UUID) -> AuditLog | None:
        return self.session.get(AuditLog, audit_id)

    def list(
        self,
        *,
        page: int,
        page_size: int,
        patient_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        statement = select(AuditLog)
        count_statement = select(func.count()).select_from(AuditLog)
        for predicate in self._predicates(
            patient_id, user_id, action, resource_type, resource_id, from_date, to_date
        ):
            statement = statement.where(predicate)
            count_statement = count_statement.where(predicate)
        total = self.session.scalar(count_statement) or 0
        items = list(
            self.session.scalars(
                statement.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        return items, total

    def user_display_names(self, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        rows = self.session.execute(
            select(User.user_id, User.full_name).where(User.user_id.in_(user_ids))
        )
        return {user_id: full_name for user_id, full_name in rows}

    def summary_contexts(self, summary_ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
        if not summary_ids:
            return {}
        rows = self.session.execute(
            select(
                Summary.summary_id,
                Summary.patient_id,
                Summary.encounter_id,
                Summary.status,
                Summary.summary_type,
                ModelRun.provider,
                ModelRun.model_name,
                ModelRun.latency_ms,
            )
            .outerjoin(ModelRun, Summary.model_run_id == ModelRun.model_run_id)
            .where(Summary.summary_id.in_(summary_ids))
        )
        contexts: dict[uuid.UUID, dict[str, Any]] = {}
        for (
            summary_id,
            patient_id,
            encounter_id,
            status,
            summary_type,
            provider,
            model_name,
            latency_ms,
        ) in rows:
            provider_label = _model_provider_label(provider)
            contexts[summary_id] = {
                "summary_id": str(summary_id),
                "patient_id": str(patient_id) if patient_id else None,
                "encounter_id": str(encounter_id) if encounter_id else None,
                "summary_type": summary_type,
                "status": status.value if hasattr(status, "value") else status,
                "provider": provider_label,
                "model_provider": provider_label,
                "model_name": model_name,
                "latency_ms": latency_ms,
            }
        return contexts

    @staticmethod
    def _predicates(
        patient_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        action: str | None,
        resource_type: str | None,
        resource_id: uuid.UUID | None,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> list:
        predicates = []
        if patient_id:
            predicates.append(AuditLog.patient_id == patient_id)
        if user_id:
            predicates.append(AuditLog.user_id == user_id)
        if action:
            predicates.append(AuditLog.action == action)
        if resource_type:
            predicates.append(AuditLog.resource_type == resource_type)
        if resource_id:
            predicates.append(AuditLog.resource_id == resource_id)
        if from_date:
            predicates.append(AuditLog.timestamp >= from_date)
        if to_date:
            predicates.append(AuditLog.timestamp <= to_date)
        return predicates


def _model_provider_label(provider: str | None) -> str | None:
    if provider == "local":
        return "deterministic"
    return provider
