from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    AuditLog,
    ClaimCitation,
    ClinicalDocument,
    DocumentChunk,
    Encounter,
    ModelRun,
    Patient,
    Summary,
    SummaryClaim,
    SummaryReview,
    User,
)


class MetricsRepository:
    def __init__(self, session: Session):
        self.session = session

    def summaries(
        self,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        department: str | None = None,
        summary_type: str | None = None,
        status: str | None = None,
    ) -> list[Summary]:
        statement = select(Summary).options(
            selectinload(Summary.claims).selectinload(SummaryClaim.citations),
            selectinload(Summary.reviews).selectinload(SummaryReview.reviewer),
        )
        if department:
            statement = statement.join(Encounter, Summary.encounter_id == Encounter.encounter_id).where(
                Encounter.department == department
            )
        if from_date:
            statement = statement.where(Summary.generated_at >= from_date)
        if to_date:
            statement = statement.where(Summary.generated_at <= to_date)
        if summary_type:
            statement = statement.where(Summary.summary_type == summary_type)
        if status:
            statement = statement.where(Summary.status == status)
        return list(self.session.scalars(statement))

    def reviews(self) -> list[SummaryReview]:
        return list(
            self.session.scalars(
                select(SummaryReview).options(
                    selectinload(SummaryReview.summary),
                    selectinload(SummaryReview.reviewer),
                )
            )
        )

    def claims(self) -> list[SummaryClaim]:
        return list(
            self.session.scalars(
                select(SummaryClaim).options(selectinload(SummaryClaim.citations))
            )
        )

    def audit_action_count(self, action: str) -> int:
        return (
            self.session.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
            )
            or 0
        )

    def count(self, model: type) -> int:
        return self.session.scalar(select(func.count()).select_from(model)) or 0

    def summaries_generated_since(self, from_date: datetime) -> int:
        return (
            self.session.scalar(
                select(func.count()).select_from(Summary).where(Summary.generated_at >= from_date)
            )
            or 0
        )

    def active_user_count(self) -> int:
        return (
            self.session.scalar(
                select(func.count(func.distinct(AuditLog.user_id))).where(
                    AuditLog.user_id.is_not(None)
                )
            )
            or 0
        )

    def most_active_roles(self) -> list[tuple[str, int]]:
        rows = self.session.execute(
            select(User.role_code, func.count())
            .join(AuditLog, AuditLog.user_id == User.user_id)
            .group_by(User.role_code)
            .order_by(func.count().desc())
        )
        return [(role_code, count) for role_code, count in rows]

    def average_generation_latency_ms(self) -> float | None:
        value = self.session.scalar(
            select(func.avg(ModelRun.latency_ms)).where(ModelRun.latency_ms.is_not(None))
        )
        return float(value) if value is not None else None

    def table_counts(self) -> dict[str, int]:
        return {
            "patients": self.count(Patient),
            "encounters": self.count(Encounter),
            "documents": self.count(ClinicalDocument),
            "document_chunks": self.count(DocumentChunk),
            "summaries": self.count(Summary),
            "model_runs": self.count(ModelRun),
            "citations": self.count(ClaimCitation),
        }
