import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    ClaimCitation,
    ClinicalDocument,
    Condition,
    DiagnosticReport,
    DocumentChunk,
    Encounter,
    Medication,
    ModelRun,
    Observation,
    Patient,
    Role,
    Summary,
    SummaryClaim,
    SummaryReview,
    SummarySection,
    User,
)


class SummaryRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_patient(self, patient_id: uuid.UUID) -> Patient | None:
        return self.session.get(Patient, patient_id)

    def get_encounter(self, encounter_id: uuid.UUID) -> Encounter | None:
        return self.session.get(Encounter, encounter_id)

    def get_summary(self, summary_id: uuid.UUID) -> Summary | None:
        return self.session.scalar(
            select(Summary)
            .where(Summary.summary_id == summary_id)
            .options(
                selectinload(Summary.sections).selectinload(SummarySection.claims).selectinload(
                    SummaryClaim.citations
                ),
                selectinload(Summary.claims).selectinload(SummaryClaim.citations),
                selectinload(Summary.reviews).selectinload(SummaryReview.reviewer),
                selectinload(Summary.model_run),
            )
        )

    def get_user_by_external_id(self, external_user_id: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.external_user_id == external_user_id)
        )

    def get_or_create_role(self, role_code: str) -> Role:
        role = self.session.get(Role, role_code)
        if role is not None:
            return role
        role = Role(
            role_code=role_code,
            role_name=role_code.replace("_", " ").title(),
            description="Mock RBAC role created for local review workflow testing.",
        )
        self.session.add(role)
        self.session.flush()
        return role

    def add_review(self, review: SummaryReview) -> SummaryReview:
        self.session.add(review)
        return review

    def list_reviews(self, summary_id: uuid.UUID) -> list[SummaryReview]:
        return list(
            self.session.scalars(
                select(SummaryReview)
                .where(SummaryReview.summary_id == summary_id)
                .options(selectinload(SummaryReview.reviewer))
                .order_by(SummaryReview.reviewed_at, SummaryReview.created_at)
            )
        )

    def get_claim(self, claim_id: uuid.UUID) -> SummaryClaim | None:
        return self.session.scalar(
            select(SummaryClaim)
            .where(SummaryClaim.claim_id == claim_id)
            .options(selectinload(SummaryClaim.citations), selectinload(SummaryClaim.summary))
        )

    def get_citation(self, citation_id: uuid.UUID) -> ClaimCitation | None:
        return self.session.scalar(
            select(ClaimCitation)
            .where(ClaimCitation.citation_id == citation_id)
            .options(selectinload(ClaimCitation.claim).selectinload(SummaryClaim.summary))
        )

    def next_version(
        self,
        patient_id: uuid.UUID,
        encounter_id: uuid.UUID | None,
        summary_type: str,
    ) -> int:
        statement = select(func.max(Summary.version_number)).where(
            Summary.patient_id == patient_id,
            Summary.summary_type == summary_type,
        )
        if encounter_id is None:
            statement = statement.where(Summary.encounter_id.is_(None))
        else:
            statement = statement.where(Summary.encounter_id == encounter_id)
        return (self.session.scalar(statement) or 0) + 1

    def clinical_context(
        self, patient_id: uuid.UUID, encounter_id: uuid.UUID | None
    ) -> dict[str, list]:
        return {
            "conditions": self._by_patient_encounter(Condition, patient_id, encounter_id),
            "observations": self._by_patient_encounter(Observation, patient_id, encounter_id),
            "medications": self._by_patient_encounter(Medication, patient_id, encounter_id),
            "diagnostic_reports": self._by_patient_encounter(
                DiagnosticReport, patient_id, encounter_id
            ),
            "documents": self._documents(patient_id, encounter_id),
            "chunks": self._chunks(patient_id, encounter_id),
        }

    def add_model_run(self, model_run: ModelRun) -> ModelRun:
        self.session.add(model_run)
        return model_run

    def add_summary_graph(
        self,
        summary: Summary,
        sections: list[SummarySection],
        claims: list[SummaryClaim],
        citations: list[ClaimCitation],
    ) -> Summary:
        self.session.add(summary)
        self.session.flush()
        for section in sections:
            section.summary_id = summary.summary_id
        self.session.add_all(sections)
        self.session.flush()
        self.session.add_all(claims)
        self.session.flush()
        self.session.add_all(citations)
        return summary

    def _by_patient_encounter(self, model: type, patient_id: uuid.UUID, encounter_id: uuid.UUID | None) -> list:
        statement = select(model).where(model.patient_id == patient_id)
        if encounter_id is not None:
            statement = statement.where(model.encounter_id == encounter_id)
        return list(self.session.scalars(statement))

    def _documents(self, patient_id: uuid.UUID, encounter_id: uuid.UUID | None) -> list[ClinicalDocument]:
        statement = select(ClinicalDocument).where(ClinicalDocument.patient_id == patient_id)
        if encounter_id is not None:
            statement = statement.where(ClinicalDocument.encounter_id == encounter_id)
        return list(
            self.session.scalars(
                statement.order_by(
                    ClinicalDocument.document_datetime.desc(),
                    ClinicalDocument.created_at.desc(),
                )
            )
        )

    def _chunks(self, patient_id: uuid.UUID, encounter_id: uuid.UUID | None) -> list[DocumentChunk]:
        statement = select(DocumentChunk).where(DocumentChunk.patient_id == patient_id)
        if encounter_id is not None:
            statement = statement.where(DocumentChunk.encounter_id == encounter_id)
        return list(
            self.session.scalars(
                statement.order_by(DocumentChunk.created_at.desc(), DocumentChunk.chunk_index)
            )
        )
