from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

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
from .citation_scope import summarize_scope_violations, validate_summary_citation_scope
from .persistence_common import PersistedResourceNotFoundError


DOCTOR_ROLE = "doctor"
HISTORY_ROLES = {"doctor", "clinical_admin", "auditor"}
MUTABLE_REVIEW_STATUSES = {
    SummaryStatus.DRAFT,
    SummaryStatus.UNDER_REVIEW,
    SummaryStatus.EDITED,
}
START_REVIEW_STATUSES = {SummaryStatus.DRAFT, SummaryStatus.EDITED}
LOCKED_STATUSES = {
    SummaryStatus.ARCHIVED,
}
APPROVAL_BLOCKING_CLAIM_TYPES = {
    "diagnosis",
    "medication",
    "allergy",
    "lab_result",
    "vital_sign",
    "procedure",
    "imaging_finding",
    "timeline_event",
    "follow_up",
    "encounter_context",
}
APPROVAL_BLOCKING_RISK_LEVELS = {"medium", "high", "critical"}
APPROVAL_BLOCKING_STATUSES = {
    ClaimSupportStatus.UNSUPPORTED,
    ClaimSupportStatus.INSUFFICIENT_EVIDENCE,
    ClaimSupportStatus.UNCHECKED,
    ClaimSupportStatus.CONFLICTING,
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
        if previous not in START_REVIEW_STATUSES and previous != SummaryStatus.UNDER_REVIEW:
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
                "training_signal": _review_training_signal(
                    summary,
                    action="edit",
                    edit_distance_score=edit_distance,
                ),
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
        scope_violations = validate_summary_citation_scope(
            summary,
            self.repository.session,
        )
        if scope_violations:
            raise ReviewTransitionError(
                "Approval blocked: citation source scope validation failed. "
                + summarize_scope_violations(scope_violations)
            )
        blocking_claims = _approval_blocking_claims(summary)
        if blocking_claims:
            raise ReviewTransitionError(
                "Approval blocked: unsupported, unchecked, or conflicting clinical claims require resolution."
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
                "training_signal": _review_training_signal(summary, action="approve"),
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
                "training_signal": _review_training_signal(
                    summary,
                    action="reject",
                    rejection_reason=payload.rejection_reason,
                ),
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
                **_summary_audit_metadata(summary),
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
            final_locked=summary.status == SummaryStatus.APPROVED,
            reviewer_signature=_reviewer_signature(review.reviewer_id, review.reviewed_at),
            audit_trail_ready=True,
            edit_diff=_edit_diff(summary.summary_text, review.edited_summary_text),
            edit_diff_summary=_edit_diff_summary(summary.summary_text, review.edited_summary_text),
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
        reviewer_signature=_reviewer_signature(review.reviewer_id, review.reviewed_at),
        audit_trail_ready=True,
        edit_diff=_edit_diff(review.summary.summary_text if review.summary else "", review.edited_summary_text),
        edit_diff_summary=_edit_diff_summary(review.summary.summary_text if review.summary else "", review.edited_summary_text),
    )


def _edit_distance_ratio(original: str, edited: str) -> Decimal:
    ratio = SequenceMatcher(None, original or "", edited or "").ratio()
    return Decimal(str(round(1 - ratio, 4)))


def _edit_diff(original: str, edited: str | None, *, max_segments: int = 80) -> list[dict[str, str | None]]:
    if edited is None:
        return []
    original_units = _diff_units(original)
    edited_units = _diff_units(edited)
    matcher = SequenceMatcher(None, original_units, edited_units)
    segments: list[dict[str, str | None]] = []
    for op, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if op == "equal":
            continue
        segments.append(
            {
                "op": op,
                "old_text": " ".join(original_units[old_start:old_end]) or None,
                "new_text": " ".join(edited_units[new_start:new_end]) or None,
            }
        )
        if len(segments) >= max_segments:
            segments.append({"op": "truncated", "old_text": None, "new_text": "Diff truncated for response size."})
            break
    return segments


def _edit_diff_summary(original: str, edited: str | None) -> dict[str, Any]:
    if edited is None:
        return {}
    original_units = _diff_units(original)
    edited_units = _diff_units(edited)
    matcher = SequenceMatcher(None, original_units, edited_units)
    counts = {"insert": 0, "delete": 0, "replace": 0}
    for op, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if op == "insert":
            counts["insert"] += new_end - new_start
        elif op == "delete":
            counts["delete"] += old_end - old_start
        elif op == "replace":
            counts["replace"] += max(old_end - old_start, new_end - new_start)
    return {
        "changed_segments": sum(1 for value in counts.values() if value > 0),
        "inserted_units": counts["insert"],
        "deleted_units": counts["delete"],
        "replaced_units": counts["replace"],
        "original_units": len(original_units),
        "edited_units": len(edited_units),
    }


def _diff_units(text: str | None) -> list[str]:
    return [unit for unit in (text or "").replace("\r\n", "\n").splitlines() if unit.strip()]


def _reviewer_signature(reviewer_id: uuid.UUID, reviewed_at: datetime) -> str:
    return f"reviewer:{reviewer_id}|signed_at:{reviewed_at.isoformat(timespec='seconds')}"


def _critical_unsupported_claims(summary: Summary) -> list:
    return [
        claim
        for claim in summary.claims
        if claim.clinical_risk_level == "critical"
        and claim.support_status != ClaimSupportStatus.SUPPORTED
    ]


def _approval_blocking_claims(summary: Summary) -> list:
    return [
        claim
        for claim in summary.claims
        if claim.support_status in APPROVAL_BLOCKING_STATUSES
        and (
            claim.clinical_risk_level in APPROVAL_BLOCKING_RISK_LEVELS
            or claim.support_status == ClaimSupportStatus.CONFLICTING
            or claim.claim_type in APPROVAL_BLOCKING_CLAIM_TYPES
            and claim.clinical_risk_level != "low"
        )
    ]


def _summary_audit_metadata(summary: Summary) -> dict[str, object | None]:
    provider = _model_provider_label(summary.model_run)
    metadata = {
        "summary_id": str(summary.summary_id),
        "encounter_id": str(summary.encounter_id) if summary.encounter_id else None,
        "summary_type": summary.summary_type,
        "summary_status": summary.status.value if summary.status else None,
        "provider": provider,
        "model_provider": provider,
        "model_name": summary.model_run.model_name if summary.model_run else None,
        "latency_ms": summary.model_run.latency_ms if summary.model_run else None,
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _review_training_signal(
    summary: Summary,
    *,
    action: str,
    rejection_reason: str | None = None,
    edit_distance_score: Decimal | None = None,
) -> dict[str, object | None]:
    categories = _review_failure_categories(summary, rejection_reason)
    return {
        "action": action,
        "provider": _model_provider_label(summary.model_run),
        "model_name": summary.model_run.model_name if summary.model_run else None,
        "summary_id": str(summary.summary_id),
        "citation_coverage": str(summary.citation_coverage) if summary.citation_coverage is not None else None,
        "unsupported_claim_count": summary.unsupported_claim_count,
        "conflict_count": summary.conflict_count,
        "critical_unsupported_count": len(_critical_unsupported_claims(summary)),
        "missing_required_domains": _missing_required_domains(summary),
        "failure_categories": categories,
        "rejection_reason": rejection_reason,
        "edit_distance_score": str(edit_distance_score) if edit_distance_score is not None else None,
        "improvement_targets": _improvement_targets(categories),
    }


def _review_failure_categories(summary: Summary, rejection_reason: str | None) -> list[str]:
    categories: set[str] = set()
    if rejection_reason:
        categories.add(rejection_reason)
    for claim in summary.claims:
        status = claim.support_status
        claim_type = claim.claim_type or "general"
        if status == ClaimSupportStatus.CONFLICTING:
            categories.add("conflicting_evidence")
        elif status == ClaimSupportStatus.UNSUPPORTED:
            categories.add("unsupported_claim")
        elif status == ClaimSupportStatus.INSUFFICIENT_EVIDENCE:
            if claim_type == "diagnosis":
                categories.add("missing_diagnosis")
            elif claim_type == "medication":
                categories.add("missing_medication")
            elif claim_type == "timeline_event":
                categories.add("missing_timeline")
            else:
                categories.add("insufficient_evidence")
    for domain in _missing_required_domains(summary):
        categories.add(f"missing_{domain}")
    return sorted(categories)


def _missing_required_domains(summary: Summary) -> list[str]:
    supported_types = {
        claim.claim_type
        for claim in summary.claims
        if claim.support_status == ClaimSupportStatus.SUPPORTED and claim.citations
    }
    missing: list[str] = []
    if "diagnosis" not in supported_types:
        missing.append("diagnosis")
    if "medication" not in supported_types:
        missing.append("medication")
    if not supported_types.intersection({"timeline_event", "encounter_context", "procedure"}):
        missing.append("timeline")
    return missing


def _improvement_targets(categories: list[str]) -> list[str]:
    targets: set[str] = set()
    for category in categories:
        if category in {"wrong_citation", "missing_diagnosis", "missing_medication", "missing_timeline", "insufficient_evidence"}:
            targets.add("retrieval_or_reranking")
        if category in {"unsupported_claim", "unsafe_output", "incorrect_clinical_fact", "too_generic", "poor_readability"}:
            targets.add("prompt_or_model_selection")
        if category in {"conflicting_evidence", "missing_critical_info"}:
            targets.add("doctor_review_rubric")
    return sorted(targets) or ["monitor"]


def _model_provider_label(model_run: object | None) -> str | None:
    provider = getattr(model_run, "provider", None)
    if provider == "local":
        return "deterministic"
    return provider
