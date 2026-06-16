from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, time
from decimal import Decimal

from ..models import ClaimSupportStatus, ReviewAction, Summary, SummaryReview, SummaryStatus
from ..persistence_schemas import (
    MetricCountItem,
    ReviewMetricsResponse,
    SafetyGateItem,
    SafetyGateResponse,
    SafetyMetricsResponse,
    SummaryQualityMetricsResponse,
    UsageMetricsResponse,
)
from ..repositories import MetricsRepository
from .citation_scope import validate_summary_citation_scope


METRICS_VIEW_ROLES = {"clinical_admin", "it_admin", "auditor", "ai_safety_reviewer"}
CLAIM_TYPES_REQUIRING_CITATION = {
    "encounter_context",
    "diagnosis",
    "medication",
    "lab_result",
    "vital_sign",
    "timeline_event",
    "imaging_finding",
    "follow_up",
    "allergy",
    "procedure",
}
UNSUPPORTED_STATUSES = {
    ClaimSupportStatus.UNSUPPORTED,
    ClaimSupportStatus.INSUFFICIENT_EVIDENCE,
    ClaimSupportStatus.UNCHECKED,
}


class MetricsPermissionError(PermissionError):
    pass


class MetricsService:
    def __init__(self, repository: MetricsRepository):
        self.repository = repository

    def summary_quality(
        self,
        *,
        role_code: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        department: str | None = None,
        summary_type: str | None = None,
        status: str | None = None,
    ) -> SummaryQualityMetricsResponse:
        self._require_role(role_code)
        summaries = self.repository.summaries(
            from_date=from_date,
            to_date=to_date,
            department=department,
            summary_type=summary_type,
            status=status,
        )
        return self._summary_quality_from_summaries(summaries)

    def usage(self, *, role_code: str) -> UsageMetricsResponse:
        self._require_role(role_code)
        counts = self.repository.table_counts()
        today_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        return UsageMetricsResponse(
            total_patients=counts["patients"],
            total_encounters=counts["encounters"],
            total_documents=counts["documents"],
            total_document_chunks=counts["document_chunks"],
            total_summaries_generated=counts["summaries"],
            summaries_generated_today=self.repository.summaries_generated_since(today_start),
            active_users=self.repository.active_user_count(),
            most_active_roles=_count_items(self.repository.most_active_roles()),
            average_generation_latency_ms=self.repository.average_generation_latency_ms(),
            model_run_count=counts["model_runs"],
        )

    def safety(self, *, role_code: str) -> SafetyMetricsResponse:
        self._require_role(role_code)
        summaries = self.repository.summaries()
        claims = self.repository.claims()
        citation_average = _average_decimal(
            [summary.citation_coverage for summary in summaries if summary.citation_coverage is not None]
        )
        unsupported_claim_total = sum(
            1 for claim in claims if claim.support_status in UNSUPPORTED_STATUSES
        )
        conflicting_claim_total = sum(
            1 for claim in claims if claim.support_status == ClaimSupportStatus.CONFLICTING
        )
        total_claims = len(claims)
        weak_citation_count = sum(
            1
            for claim in claims
            for citation in claim.citations
            if citation.citation_confidence is not None
            and Decimal(citation.citation_confidence) < Decimal("0.70")
        )
        missing_citation_count = sum(
            1
            for claim in claims
            if _requires_citation(claim.claim_type) and not claim.citations
        )
        critical_hallucination_proxy_count = _critical_hallucination_proxy_count(claims)
        citation_scope_violations = [
            violation
            for summary in summaries
            for violation in validate_summary_citation_scope(summary, self.repository.session)
        ]
        wrong_patient_retrieval_count = sum(
            1
            for violation in citation_scope_violations
            if violation.violation_type == "wrong_patient"
        )
        wrong_encounter_citation_count = sum(
            1
            for violation in citation_scope_violations
            if violation.violation_type == "wrong_encounter"
        )
        safety_gate_status = self._safety_gate(
            summaries=summaries,
            citation_average=citation_average,
            critical_hallucination_proxy_count=critical_hallucination_proxy_count,
            wrong_patient_retrieval_count=wrong_patient_retrieval_count,
            wrong_encounter_citation_count=wrong_encounter_citation_count,
        )
        return SafetyMetricsResponse(
            citation_coverage_average=citation_average,
            unsupported_claim_total=unsupported_claim_total,
            unsupported_claim_rate=(
                unsupported_claim_total / total_claims if total_claims else None
            ),
            conflicting_claim_total=conflicting_claim_total,
            weak_citation_count=weak_citation_count,
            missing_citation_count=missing_citation_count,
            critical_hallucination_proxy_count=critical_hallucination_proxy_count,
            wrong_patient_retrieval_count=wrong_patient_retrieval_count,
            safety_gate_status=safety_gate_status,
        )

    def review(self, *, role_code: str) -> ReviewMetricsResponse:
        self._require_role(role_code)
        reviews = self.repository.reviews()
        action_counts = Counter(review.action for review in reviews)
        edit_distances = [
            Decimal(review.edit_distance_score)
            for review in reviews
            if review.edit_distance_score is not None
        ]
        rejection_reasons = Counter(
            review.rejection_reason
            for review in reviews
            if review.action == ReviewAction.REJECT and review.rejection_reason
        )
        reviewer_activity = Counter(
            _reviewer_label(review) for review in reviews if review.reviewer is not None
        )
        review_latencies = [
            (review.reviewed_at - review.summary.generated_at).total_seconds() / 3600
            for review in reviews
            if review.summary is not None
            and review.summary.generated_at is not None
            and review.reviewed_at is not None
        ]
        return ReviewMetricsResponse(
            total_reviews=len(reviews),
            approvals=action_counts[ReviewAction.APPROVE],
            rejections=action_counts[ReviewAction.REJECT],
            edits=action_counts[ReviewAction.EDIT],
            average_edit_distance=_average_decimal(edit_distances),
            average_time_to_review_hours=_average_float(review_latencies),
            rejection_reasons_distribution=_count_items(rejection_reasons.items()),
            reviewer_activity=_count_items(reviewer_activity.items()),
        )

    def _summary_quality_from_summaries(
        self,
        summaries: list[Summary],
    ) -> SummaryQualityMetricsResponse:
        status_counts = Counter(summary.status for summary in summaries)
        summary_types = Counter(summary.summary_type for summary in summaries)
        rejection_reasons = Counter(
            review.rejection_reason
            for summary in summaries
            for review in summary.reviews
            if review.action == ReviewAction.REJECT and review.rejection_reason
        )
        edit_distances = [
            Decimal(review.edit_distance_score)
            for summary in summaries
            for review in summary.reviews
            if review.action == ReviewAction.EDIT and review.edit_distance_score is not None
        ]
        total = len(summaries)
        approved = status_counts[SummaryStatus.APPROVED]
        rejected = status_counts[SummaryStatus.REJECTED]
        return SummaryQualityMetricsResponse(
            total_summaries=total,
            draft_count=status_counts[SummaryStatus.DRAFT],
            under_review_count=status_counts[SummaryStatus.UNDER_REVIEW],
            edited_count=status_counts[SummaryStatus.EDITED],
            approved_count=approved,
            rejected_count=rejected,
            archived_count=status_counts[SummaryStatus.ARCHIVED],
            approval_rate=approved / total if total else 0.0,
            rejection_rate=rejected / total if total else 0.0,
            average_citation_coverage=_average_decimal(
                [
                    summary.citation_coverage
                    for summary in summaries
                    if summary.citation_coverage is not None
                ]
            ),
            average_unsupported_claim_count=_average_float(
                [summary.unsupported_claim_count for summary in summaries]
            ),
            average_conflict_count=_average_float([summary.conflict_count for summary in summaries]),
            average_edit_distance=_average_decimal(edit_distances),
            critical_unsupported_claim_count=sum(
                1
                for summary in summaries
                for claim in summary.claims
                if claim.clinical_risk_level == "critical"
                and claim.support_status != ClaimSupportStatus.SUPPORTED
            ),
            summaries_by_type=_count_items(summary_types.items()),
            top_rejection_reasons=_count_items(rejection_reasons.most_common(10)),
        )

    def _safety_gate(
        self,
        *,
        summaries: list[Summary],
        citation_average: float | None,
        critical_hallucination_proxy_count: int,
        wrong_patient_retrieval_count: int,
        wrong_encounter_citation_count: int,
    ) -> SafetyGateResponse:
        approved_without_doctor = sum(
            1
            for summary in summaries
            if summary.status == SummaryStatus.APPROVED and summary.approved_by is None
        )
        audit_coverage = self._audit_log_coverage(summaries)
        gates = [
            SafetyGateItem(
                name="critical_hallucination_proxy",
                status="pass" if critical_hallucination_proxy_count == 0 else "fail",
                value=critical_hallucination_proxy_count,
                threshold=0,
            ),
            SafetyGateItem(
                name="wrong_patient_retrieval",
                status="pass" if wrong_patient_retrieval_count == 0 else "fail",
                value=wrong_patient_retrieval_count,
                threshold=0,
                explanation="Citation sources must belong to the same patient as the draft summary.",
            ),
            SafetyGateItem(
                name="encounter_scope_enforcement",
                status="pass" if wrong_encounter_citation_count == 0 else "fail",
                value=wrong_encounter_citation_count,
                threshold=0,
                explanation="Encounter-specific citation sources must match the summary encounter.",
            ),
            _citation_gate(citation_average),
            audit_coverage,
            SafetyGateItem(
                name="approved_summaries_have_doctor_approval",
                status="pass" if approved_without_doctor == 0 else "fail",
                value=approved_without_doctor,
                threshold=0,
            ),
            SafetyGateItem(
                name="no_summary_auto_approval",
                status="pass" if approved_without_doctor == 0 else "fail",
                value=approved_without_doctor,
                threshold=0,
            ),
        ]
        if any(gate.status == "fail" for gate in gates):
            status = "fail"
        elif any(gate.status in {"warning", "not_available"} for gate in gates):
            status = "warning"
        else:
            status = "pass"
        return SafetyGateResponse(mvp_readiness_status=status, gates=gates)

    def _audit_log_coverage(self, summaries: list[Summary]) -> SafetyGateItem:
        generated_expected = sum(1 for summary in summaries if summary.model_run_id is not None)
        edited_expected = sum(
            1 for summary in summaries for review in summary.reviews if review.action == ReviewAction.EDIT
        )
        approved_expected = sum(
            1 for summary in summaries for review in summary.reviews if review.action == ReviewAction.APPROVE
        )
        rejected_expected = sum(
            1 for summary in summaries for review in summary.reviews if review.action == ReviewAction.REJECT
        )
        expected = generated_expected + edited_expected + approved_expected + rejected_expected
        actual = (
            self.repository.audit_action_count("generate_summary")
            + self.repository.audit_action_count("regenerate_summary")
            + self.repository.audit_action_count("edit_summary")
            + self.repository.audit_action_count("approve_summary")
            + self.repository.audit_action_count("reject_summary")
        )
        if expected == 0:
            return SafetyGateItem(
                name="audit_log_coverage",
                status="not_available",
                value="not_available",
                threshold=1.0,
                explanation="No measurable sensitive summary actions exist yet.",
            )
        coverage = min(actual / expected, 1.0)
        return SafetyGateItem(
            name="audit_log_coverage",
            status="pass" if coverage >= 1.0 else "fail",
            value=coverage,
            threshold=1.0,
        )

    @staticmethod
    def _require_role(role_code: str) -> None:
        if role_code not in METRICS_VIEW_ROLES:
            raise MetricsPermissionError("This role cannot view global metrics.")


def _citation_gate(citation_average: float | None) -> SafetyGateItem:
    if citation_average is None:
        return SafetyGateItem(
            name="citation_coverage",
            status="not_available",
            value="not_available",
            threshold=0.90,
            explanation="No summaries with citation coverage are available yet.",
        )
    return SafetyGateItem(
        name="citation_coverage",
        status="pass" if citation_average >= 0.90 else "fail",
        value=citation_average,
        threshold=0.90,
    )


def _critical_hallucination_proxy_count(claims: list) -> int:
    return sum(
        1
        for claim in claims
        if claim.clinical_risk_level == "critical"
        and (
            claim.support_status != ClaimSupportStatus.SUPPORTED
            or (_requires_citation(claim.claim_type) and not claim.citations)
        )
    )


def _requires_citation(claim_type: str | None) -> bool:
    return claim_type in CLAIM_TYPES_REQUIRING_CITATION


def _reviewer_label(review: SummaryReview) -> str:
    if not review.reviewer:
        return "unknown"
    return review.reviewer.external_user_id or review.reviewer.full_name or str(review.reviewer_id)


def _count_items(items) -> list[MetricCountItem]:
    return [MetricCountItem(key=str(key), count=int(count)) for key, count in items]


def _average_decimal(values: list[Decimal | None]) -> float | None:
    cleaned = [Decimal(value) for value in values if value is not None]
    if not cleaned:
        return None
    return float(sum(cleaned) / len(cleaned))


def _average_float(values: list[float | int | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)
