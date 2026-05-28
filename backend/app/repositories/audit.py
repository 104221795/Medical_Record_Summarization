import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AuditLog, User


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
