from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from difflib import SequenceMatcher

from ..models import (
    ClaimSupportStatus,
    ReviewAction,
    Role,
    Summary,
    SummaryReview,
    SummaryStatus,
    User,
)
from ..persistence_schemas import (
    SummaryApproveRequest,
    SummaryEditRequest,
    SummaryRejectRequest,
    SummaryReviewActionResponse,
    SummaryReviewListResponse,
    SummaryReviewResponse,
    SummaryReviewStartResponse,
)
from ..repositories import SummaryRepository
from .audit_service import AuditService
from .persistence_common import PersistedResourceNotFoundError


DOCTOR_ROLE = "doctor"
HISTORY_ROLES = {"doctor", "clinical_admin", "auditor"}
MUTABLE_REVIEW_STATUSES = {
    SummaryStatus.DRAFT,
    SummaryStatus.UNDER_REVIEW,
    SummaryStatus.EDITED,
    SummaryStatus.APPROVED,
    SummaryStatus.REJECTED,
}
START_REVIEW_STATUSES = {SummaryStatus.DRAFT, SummaryStatus.EDITED}
LOCKED_STATUSES = {
    SummaryStatus.ARCHIVED,
}


class ReviewPermissionError(PermissionError):
    pass


class ReviewTransitionError(ValueError):
    pass


class ReviewService:
    """Human-in-the-loop review workflow for draft AI summaries."""

    def __init__(self, repository: SummaryRepository, audit_service: AuditService):
        self.repository = repository
        self.audit_service = audit_service

    def start_review(
        self,
        summary_id: str,
        *,
        tenant_id: str,
        actor_external_id: str,
        role_code: str,
    ) -> SummaryReviewStartResponse:
        self._require_doctor(role_code, "start review")
        summary = self._get_summary(summary_id)
        previous = summary.status
        if previous in LOCKED_STATUSES:
            raise ReviewTransitionError(
                f"Cannot start review for a summary in {previous.value} status."
            )
        if previous not in START_REVIEW_STATUSES and previous not in {
            SummaryStatus.UNDER_REVIEW,
            SummaryStatus.APPROVED,
            SummaryStatus.REJECTED,
        }:
            raise ReviewTransitionError(
                f"Cannot start review from {previous.value} status."
            )

        actor = self._resolve_actor(actor_external_id, role_code)
        now = datetime.now(UTC)
        if previous in START_REVIEW_STATUSES:
            summary.status = SummaryStatus.UNDER_REVIEW
        summary.reviewed_by = actor.user_id
        summary.reviewed_at = now
        review = self._add_review(
            summary,
            actor,
            action=ReviewAction.START_REVIEW,
            previous_status=previous,
            resulting_status=summary.status,
            comment="Review started.",
            reviewed_at=now,
        )
        self._record_audit(
            "start_review",
            summary,
            actor,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            metadata={"previous_status": previous.value, "status": summary.status.value},
        )
        self.repository.session.flush()
        return SummaryReviewStartResponse(
            summary_id=summary.summary_id,
            patient_id=summary.patient_id,
            status=summary.status.value,
            previous_status=previous.value,
            reviewed_by=actor.user_id,
            reviewed_at=now,
            review_id=review.review_id,
        )

    def edit(
        self,
        summary_id: str,
        payload: SummaryEditRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
        role_code: str,
    ) -> SummaryReviewActionResponse:
        self._require_doctor(role_code, "edit summary")
        summary = self._get_summary(summary_id)
        previous = summary.status
        if previous not in MUTABLE_REVIEW_STATUSES:
            raise ReviewTransitionError(f"Cannot edit a summary in {previous.value} status.")

        actor = self._resolve_actor(actor_external_id, role_code)
        now = datetime.now(UTC)
        edit_distance = _edit_distance_ratio(summary.summary_text, payload.edited_summary_text)
        summary.status = SummaryStatus.EDITED
        summary.reviewed_by = actor.user_id
        summary.reviewed_at = now
        summary.approved_by = None
        summary.approved_at = None
        summary.rejected_at = None
        summary.rejection_reason = None
        review = self._add_review(
            summary,
            actor,
            action=ReviewAction.EDIT,
            previous_status=previous,
            resulting_status=SummaryStatus.EDITED,
            comment=payload.edit_comment,
            edited_summary_text=payload.edited_summary_text,
            edit_distance_score=edit_distance,
            reviewed_at=now,
        )
        self._record_audit(
            "edit_summary",
            summary,
            actor,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            metadata={
                "previous_status": previous.value,
                "status": SummaryStatus.EDITED.value,
                "edit_comment": payload.edit_comment,
                "edit_distance_score": str(edit_distance),
                "citation_revalidation_required": True,
            },
        )
        self.repository.session.flush()
        return self._action_response(
            summary,
            review,
            previous_status=previous,
            edit_distance_score=edit_distance,
            citation_revalidation_required=True,
        )

    def approve(
        self,
        summary_id: str,
        payload: SummaryApproveRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
        role_code: str,
    ) -> SummaryReviewActionResponse:
        self._require_doctor(role_code, "approve summary")
        summary = self._get_summary(summary_id)
        previous = summary.status
        if previous not in MUTABLE_REVIEW_STATUSES:
            raise ReviewTransitionError(f"Cannot approve a summary in {previous.value} status.")
        blocking_claims = _critical_unsupported_claims(summary)
        if blocking_claims:
            raise ReviewTransitionError(
                "Approval blocked: critical unsupported or conflicting claims require resolution."
            )

        actor = self._resolve_actor(actor_external_id, role_code)
        now = datetime.now(UTC)
        summary.status = SummaryStatus.APPROVED
        summary.reviewed_by = actor.user_id
        summary.reviewed_at = now
        summary.approved_by = actor.user_id
        summary.approved_at = now
        summary.rejected_at = None
        summary.rejection_reason = None
        review = self._add_review(
            summary,
            actor,
            action=ReviewAction.APPROVE,
            previous_status=previous,
            resulting_status=SummaryStatus.APPROVED,
            comment=payload.approval_comment,
            reviewed_at=now,
        )
        self._record_audit(
            "approve_summary",
            summary,
            actor,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            metadata={
                "previous_status": previous.value,
                "status": SummaryStatus.APPROVED.value,
                "approval_comment": payload.approval_comment,
            },
        )
        self.repository.session.flush()
        return self._action_response(summary, review, previous_status=previous)

    def reject(
        self,
        summary_id: str,
        payload: SummaryRejectRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
        role_code: str,
    ) -> SummaryReviewActionResponse:
        self._require_doctor(role_code, "reject summary")
        summary = self._get_summary(summary_id)
        previous = summary.status
        if previous not in MUTABLE_REVIEW_STATUSES:
            raise ReviewTransitionError(f"Cannot reject a summary in {previous.value} status.")

        actor = self._resolve_actor(actor_external_id, role_code)
        now = datetime.now(UTC)
        summary.status = SummaryStatus.REJECTED
        summary.reviewed_by = actor.user_id
        summary.reviewed_at = now
        summary.rejected_at = now
        summary.rejection_reason = payload.rejection_reason
        review = self._add_review(
            summary,
            actor,
            action=ReviewAction.REJECT,
            previous_status=previous,
            resulting_status=SummaryStatus.REJECTED,
            comment=payload.rejection_comment,
            rejection_reason=payload.rejection_reason,
            reviewed_at=now,
        )
        self._record_audit(
            "reject_summary",
            summary,
            actor,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            metadata={
                "previous_status": previous.value,
                "status": SummaryStatus.REJECTED.value,
                "rejection_reason": payload.rejection_reason,
                "rejection_comment": payload.rejection_comment,
            },
        )
        self.repository.session.flush()
        return self._action_response(summary, review, previous_status=previous)

    def history(
        self,
        summary_id: str,
        *,
        tenant_id: str,
        actor_external_id: str,
        role_code: str,
    ) -> SummaryReviewListResponse:
        if role_code not in HISTORY_ROLES:
            raise ReviewPermissionError("This role cannot view summary review history.")
        summary = self._get_summary(summary_id)
        actor = self._resolve_actor(actor_external_id, role_code)
        self._record_audit(
            "view_review_history",
            summary,
            actor,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            metadata={"status": summary.status.value},
        )
        reviews = self.repository.list_reviews(summary.summary_id)
        return SummaryReviewListResponse(
            summary_id=summary.summary_id,
            reviews=[_review_response(review) for review in reviews],
        )

    def _get_summary(self, summary_id: str) -> Summary:
        try:
            resolved_id = uuid.UUID(summary_id)
        except ValueError as exc:
            raise PersistedResourceNotFoundError("Summary was not found.") from exc
        summary = self.repository.get_summary(resolved_id)
        if summary is None:
            raise PersistedResourceNotFoundError("Summary was not found.")
        return summary

    def _require_doctor(self, role_code: str, action: str) -> None:
        if role_code != DOCTOR_ROLE:
            raise ReviewPermissionError(f"Only doctor role can {action}.")

    def _resolve_actor(self, actor_external_id: str, role_code: str) -> User:
        actor = self.repository.get_user_by_external_id(actor_external_id)
        if actor is not None:
            return actor
        role = self.repository.get_or_create_role(role_code)
        actor = User(
            external_user_id=actor_external_id,
            full_name=actor_external_id.replace("-", " ").replace("_", " ").title(),
            email=f"{actor_external_id.lower()}@mock.local",
            role=role,
            status="active",
        )
        self.repository.session.add(actor)
        self.repository.session.flush()
        return actor

    def _add_review(
        self,
        summary: Summary,
        actor: User,
        *,
        action: ReviewAction,
        previous_status: SummaryStatus,
        resulting_status: SummaryStatus,
        comment: str | None = None,
        rejection_reason: str | None = None,
        edited_summary_text: str | None = None,
        edit_distance_score: Decimal | None = None,
        reviewed_at: datetime,
    ) -> SummaryReview:
        review = SummaryReview(
            summary_id=summary.summary_id,
            reviewer_id=actor.user_id,
            action=action,
            previous_status=previous_status,
            resulting_status=resulting_status,
            comment=comment,
            rejection_reason=rejection_reason,
            edited_summary_text=edited_summary_text,
            edit_distance_score=edit_distance_score,
            reviewed_at=reviewed_at,
        )
        self.repository.add_review(review)
        self.repository.session.flush()
        return review

    def _record_audit(
        self,
        action: str,
        summary: Summary,
        actor: User,
        *,
        tenant_id: str,
        actor_external_id: str,
        metadata: dict[str, object | None],
    ) -> None:
        self.audit_service.record(
            action=action,
            user_id=actor.user_id,
            patient_id=summary.patient_id,
            resource_type="summary",
            resource_id=summary.summary_id,
            metadata={
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
                "auth_mode": "mock_header_rbac",
                **metadata,
            },
        )

    @staticmethod
    def _action_response(
        summary: Summary,
        review: SummaryReview,
        *,
        previous_status: SummaryStatus,
        edit_distance_score: Decimal | None = None,
        citation_revalidation_required: bool = False,
    ) -> SummaryReviewActionResponse:
        return SummaryReviewActionResponse(
            summary_id=summary.summary_id,
            patient_id=summary.patient_id,
            status=summary.status.value,
            previous_status=previous_status.value,
            reviewed_by=review.reviewer_id,
            reviewed_at=review.reviewed_at,
            review_id=review.review_id,
            approved_by=summary.approved_by,
            approved_at=summary.approved_at,
            rejected_at=summary.rejected_at,
            rejection_reason=summary.rejection_reason,
            edit_distance_score=edit_distance_score,
            citation_revalidation_required=citation_revalidation_required,
        )


def _review_response(review: SummaryReview) -> SummaryReviewResponse:
    return SummaryReviewResponse(
        review_id=review.review_id,
        summary_id=review.summary_id,
        reviewer_id=review.reviewer_id,
        reviewer_role=review.reviewer.role_code if review.reviewer else None,
        review_action=review.action.value,
        previous_status=review.previous_status.value if review.previous_status else None,
        resulting_status=review.resulting_status.value if review.resulting_status else None,
        comment=review.comment,
        rejection_reason=review.rejection_reason,
        edited_summary_text=review.edited_summary_text,
        edit_distance_score=review.edit_distance_score,
        reviewed_at=review.reviewed_at,
    )


def _edit_distance_ratio(original: str, edited: str) -> Decimal:
    ratio = SequenceMatcher(None, original or "", edited or "").ratio()
    return Decimal(str(round(1 - ratio, 4)))


def _critical_unsupported_claims(summary: Summary) -> list:
    return [
        claim
        for claim in summary.claims
        if claim.clinical_risk_level == "critical"
        and claim.support_status != ClaimSupportStatus.SUPPORTED
    ]
