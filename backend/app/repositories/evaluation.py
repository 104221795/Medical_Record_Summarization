from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    AuditLog,
    ClaimCitation,
    ClinicalDocument,
    DocumentChunk,
    Encounter,
    HumanEvaluation,
    ModelRun,
    Patient,
    Summary,
    SummaryClaim,
    SummaryReview,
)


class EvaluationRepository:
    def __init__(self, session: Session):
        self.session = session

    def count(self, model: type) -> int:
        return self.session.scalar(select(func.count()).select_from(model)) or 0

    def table_counts(self) -> dict[str, int]:
        return {
            "patients": self.count(Patient),
            "encounters": self.count(Encounter),
            "documents": self.count(ClinicalDocument),
            "document_chunks": self.count(DocumentChunk),
            "summaries": self.count(Summary),
            "claims": self.count(SummaryClaim),
            "citations": self.count(ClaimCitation),
            "reviews": self.count(SummaryReview),
            "audit_logs": self.count(AuditLog),
            "model_runs": self.count(ModelRun),
            "human_evaluations": self.count(HumanEvaluation),
        }

    def latest_model_run(self, providers: Iterable[str]) -> dict[str, ModelRun]:
        provider_set = set(providers)
        rows = list(
            self.session.scalars(
                select(ModelRun)
                .where(ModelRun.provider.in_(provider_set))
                .order_by(ModelRun.created_at.desc())
            )
        )
        latest: dict[str, ModelRun] = {}
        for row in rows:
            key = row.provider or "unknown"
            latest.setdefault(key, row)
        return latest

    def get_summary(self, summary_id: uuid.UUID) -> Summary | None:
        return self.session.scalar(
            select(Summary)
            .where(Summary.summary_id == summary_id)
            .options(
                selectinload(Summary.model_run),
                selectinload(Summary.reviews).selectinload(SummaryReview.reviewer),
            )
        )

    def first_summary(self) -> Summary | None:
        return self.session.scalar(select(Summary).order_by(Summary.generated_at.desc()))

    def add_human_evaluation(self, evaluation: HumanEvaluation) -> HumanEvaluation:
        self.session.add(evaluation)
        return evaluation

    def human_evaluations(self) -> list[HumanEvaluation]:
        return list(
            self.session.scalars(
                select(HumanEvaluation)
                .options(
                    selectinload(HumanEvaluation.summary).selectinload(Summary.model_run),
                    selectinload(HumanEvaluation.summary)
                    .selectinload(Summary.reviews)
                    .selectinload(SummaryReview.reviewer),
                )
                .order_by(HumanEvaluation.created_at.desc())
            )
        )

    def human_evaluations_by_summary(self, summary_id: uuid.UUID) -> list[HumanEvaluation]:
        return list(
            self.session.scalars(
                select(HumanEvaluation)
                .where(HumanEvaluation.summary_id == summary_id)
                .options(
                    selectinload(HumanEvaluation.summary).selectinload(Summary.model_run),
                    selectinload(HumanEvaluation.summary)
                    .selectinload(Summary.reviews)
                    .selectinload(SummaryReview.reviewer),
                )
                .order_by(HumanEvaluation.created_at.desc())
            )
        )

    def summary_reviews(self) -> list[SummaryReview]:
        return list(
            self.session.scalars(
                select(SummaryReview)
                .options(
                    selectinload(SummaryReview.summary),
                    selectinload(SummaryReview.reviewer),
                )
                .order_by(SummaryReview.reviewed_at.desc(), SummaryReview.created_at.desc())
            )
        )

    def audit_action_exists(self, action: str) -> bool:
        return (
            self.session.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
            )
            or 0
        ) > 0
