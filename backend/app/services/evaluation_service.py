from __future__ import annotations

import json
import os
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import ROOT_DIR, Settings
from ..db.base import Base
from ..db.seed import seed_mock_data
from ..models import (
    AuditLog,
    ClaimCitation,
    HumanEvaluation,
    ModelRun,
    Patient,
    Summary,
)
from ..persistence_schemas import (
    BenchmarkStatusResponse,
    DemoReadinessResponse,
    EvaluationLayerStatus,
    EvaluationProviderStatus,
    EvaluationReadinessItem,
    EvaluationStatusResponse,
    FunctionalValidationCheck,
    FunctionalValidationResponse,
    HumanEvaluationCreateRequest,
    HumanEvaluationListResponse,
    HumanEvaluationResponse,
    HumanEvaluationSummaryResponse,
    MetricCountItem,
    SummaryApproveRequest,
    SummaryEditRequest,
    SummaryGenerateRequest,
    SummaryRejectRequest,
)
from ..repositories import (
    AuditRepository,
    CitationRepository,
    EvaluationRepository,
    MetricsRepository,
    SummaryRepository,
)
from .audit_service import AuditService
from .citation_service import CitationService
from .deterministic_summary_service import DeterministicSummaryService
from .metrics_service import MetricsService
from .review_service import ReviewService
from .safety_service import SafetyService


BENCHMARK_DATASET_PATH = ROOT_DIR / "data" / "processed" / "ehr_benchmark" / "test.jsonl"
BENCHMARK_OUTPUT_PATH = ROOT_DIR / "results" / "ehr_benchmark" / "model_comparison.csv"
BENCHMARK_RUNNER_PATH = ROOT_DIR / "scripts" / "run_baseline_summarization.py"
REQUIRED_BENCHMARK_KEYS = {
    "note_id",
    "patient_id",
    "encounter_id",
    "source_note",
    "reference_summary",
    "dataset",
    "split",
}


class EvaluationService:
    def __init__(
        self,
        repository: EvaluationRepository,
        session: Session,
        settings: Settings,
        audit_service: AuditService,
    ):
        self.repository = repository
        self.session = session
        self.settings = settings
        self.audit_service = audit_service

    def demo_readiness(self) -> DemoReadinessResponse:
        counts = self.repository.table_counts()
        return DemoReadinessResponse(
            golden_path=[
                _readiness_item("Patient List", counts["patients"] > 0, "Patient records available."),
                _readiness_item("Patient Detail", counts["encounters"] > 0, "Encounter context available."),
                _readiness_item("Generate Summary", counts["summaries"] > 0, "Draft summaries available."),
                _readiness_item("View Citation", counts["citations"] > 0, "Citation records available."),
                _readiness_item("Safety Panel", counts["claims"] > 0, "Claim safety data available."),
                _readiness_item("HITL Review", True, "Review workflow endpoints are registered."),
                _readiness_item("Audit Log", counts["audit_logs"] > 0, "Audit records available."),
                _readiness_item("Monitoring Dashboard", True, "Metrics endpoints are registered."),
            ],
            provider_readiness=self.provider_readiness(),
            evaluation_layers=self._evaluation_layers(),
            message=(
                "Use /api/v1/evaluation/functional/run to execute the mock-data "
                "functional validation path. Real EHR benchmark metrics remain pending."
            ),
        )

    def status(self) -> EvaluationStatusResponse:
        counts = self.repository.table_counts()
        return EvaluationStatusResponse(
            provider_readiness=self.provider_readiness(),
            golden_path_readiness="ready" if counts["patients"] and counts["documents"] else "runnable",
            citation_readiness="ready" if counts["citations"] else "runnable",
            safety_readiness="ready" if counts["claims"] else "runnable",
            hitl_readiness="ready",
            audit_readiness="ready" if counts["audit_logs"] else "runnable",
            metrics_readiness="ready",
            evaluation_layers=self._evaluation_layers(),
        )

    def functional_status(self) -> FunctionalValidationResponse:
        return FunctionalValidationResponse(
            status="runnable",
            checks=[
                FunctionalValidationCheck(
                    name="functional_validation_runner",
                    status="not_tested",
                    message="Ready to run against mock/de-identified local demo data.",
                )
            ],
            message="Functional validation is runnable now and does not require real EHR benchmark data.",
        )

    def run_functional_validation(
        self,
        *,
        tenant_id: str,
        actor_external_id: str,
    ) -> FunctionalValidationResponse:
        checks: list[FunctionalValidationCheck] = []
        state: dict[str, Any] = {}

        def check(name: str, action, success_message: str) -> None:
            try:
                action()
            except Exception as exc:  # pragma: no cover - message is asserted at API level
                checks.append(
                    FunctionalValidationCheck(
                        name=name,
                        status="failed",
                        message=str(exc),
                    )
                )
            else:
                checks.append(
                    FunctionalValidationCheck(
                        name=name,
                        status="passed",
                        message=success_message,
                    )
                )

        check("demo_data_seed", lambda: self._seed_demo_data(state), "Demo data exists or was seeded.")
        check("patient_list", lambda: self._require(state.get("patient_id")), "Patient list contains a demo patient.")
        check("patient_detail", lambda: self._patient_detail(state), "Patient detail can be loaded.")
        check("document_endpoint", lambda: self._documents_exist(state), "Clinical documents are available.")
        check(
            "summary_generation",
            lambda: self._generate_summary(state, tenant_id, actor_external_id),
            "Draft summary generated successfully.",
        )
        check("summary_claims", lambda: self._summary_has_claims(state), "Summary claims were created.")
        check(
            "citation_or_unsupported",
            lambda: self._citations_or_unsupported_exist(state),
            "Citations exist or unsupported claims are visibly flagged.",
        )
        check(
            "citation_source",
            lambda: self._citation_source_works(state, tenant_id, actor_external_id),
            "Citation source can be loaded for the same patient.",
        )
        check(
            "hitl_review",
            lambda: self._hitl_review_works(state, tenant_id, actor_external_id),
            "HITL edit/approve/reject workflow executed on draft summaries.",
        )
        check("audit_logs", self._sensitive_audit_exists, "Sensitive actions created audit logs.")
        check("metrics", self._metrics_work, "Metrics endpoints/services can calculate current state.")

        failed = sum(1 for item in checks if item.status == "failed")
        status = "passed" if failed == 0 else "partial" if failed < len(checks) else "failed"
        self.audit_service.record(
            action="run_functional_validation",
            patient_id=state.get("patient_id"),
            resource_type="evaluation",
            metadata={
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
                "status": status,
                "failed_checks": failed,
                "real_ehr_benchmark_used": False,
            },
        )
        return FunctionalValidationResponse(
            status=status,
            checks=checks,
            message=(
                "Functional validation uses mock/de-identified data only. "
                "It must not be reported as real EHR benchmark performance."
            ),
        )

    def benchmark_status(self) -> BenchmarkStatusResponse:
        dataset_exists = BENCHMARK_DATASET_PATH.exists()
        runner_exists = BENCHMARK_RUNNER_PATH.exists()
        output_exists = BENCHMARK_OUTPUT_PATH.exists()
        if not dataset_exists:
            return BenchmarkStatusResponse(
                status="pending_dataset",
                message=(
                    "Real EHR benchmark requires credentialed MIMIC-IV-Ext-BHC or "
                    "MIMIC-IV-Note processed JSONL. No benchmark result is available yet."
                ),
                dataset_path=_relative(BENCHMARK_DATASET_PATH),
                dataset_exists=False,
                schema_valid=None,
                benchmark_runner_exists=runner_exists,
                model_comparison_output_path=_relative(BENCHMARK_OUTPUT_PATH),
                model_comparison_output_exists=output_exists,
            )
        schema_valid, message = _validate_benchmark_jsonl(BENCHMARK_DATASET_PATH)
        status = "ready" if schema_valid and runner_exists else "invalid_dataset"
        if output_exists and schema_valid:
            status = "results_available"
            message = "Processed real EHR benchmark dataset and model comparison output are present."
        return BenchmarkStatusResponse(
            status=status,
            message=message,
            dataset_path=_relative(BENCHMARK_DATASET_PATH),
            dataset_exists=True,
            schema_valid=schema_valid,
            benchmark_runner_exists=runner_exists,
            model_comparison_output_path=_relative(BENCHMARK_OUTPUT_PATH),
            model_comparison_output_exists=output_exists,
        )

    def create_human_evaluation(
        self,
        payload: HumanEvaluationCreateRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
    ) -> HumanEvaluationResponse:
        summary = self.repository.get_summary(payload.summary_id)
        if summary is None:
            raise ValueError("Summary was not found.")
        model_provider = payload.model_provider or _provider_label(summary.model_run.provider if summary.model_run else None)
        evaluation = HumanEvaluation(
            summary_id=summary.summary_id,
            evaluator_id=payload.evaluator_id or actor_external_id,
            evaluator_name=payload.evaluator_name or actor_external_id,
            model_provider=model_provider,
            factual_correctness_score=payload.factual_correctness_score,
            completeness_score=payload.completeness_score,
            conciseness_score=payload.conciseness_score,
            readability_score=payload.readability_score,
            citation_usefulness_score=payload.citation_usefulness_score,
            hallucination_risk=payload.hallucination_risk,
            comments=payload.comments,
        )
        self.repository.add_human_evaluation(evaluation)
        self.session.flush()
        self.audit_service.record(
            action="submit_human_evaluation",
            patient_id=summary.patient_id,
            resource_type="summary",
            resource_id=summary.summary_id,
            metadata={
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
                "evaluation_id": str(evaluation.evaluation_id),
                "model_provider": model_provider,
                "demo_or_mock_usability_evaluation": True,
            },
        )
        return _human_evaluation_response(evaluation)

    def human_summary(self) -> HumanEvaluationSummaryResponse:
        evaluations = self.repository.human_evaluations()
        return _human_summary(evaluations)

    def human_by_summary(self, summary_id: uuid.UUID) -> HumanEvaluationListResponse:
        evaluations = self.repository.human_evaluations_by_summary(summary_id)
        return HumanEvaluationListResponse(
            summary_id=summary_id,
            evaluations=[_human_evaluation_response(item) for item in evaluations],
        )

    def provider_readiness(self) -> list[EvaluationProviderStatus]:
        latest = self.repository.latest_model_run(["local", "deterministic", "bart", "pegasus", "gemini"])
        deterministic = latest.get("local") or latest.get("deterministic")
        bart_enabled = _real_baselines_enabled()
        pegasus_enabled = _real_baselines_enabled()
        gemini_enabled = (
            self.settings.llm_provider == "gemini"
            and self.settings.llm_external_enabled
            and self.settings.llm_allow_phi_external
            and bool(self.settings.gemini_api_key)
        )
        return [
            _provider_status(
                "deterministic",
                configured=True,
                enabled=True,
                model_name=deterministic.model_name if deterministic else "deterministic_summary_service",
                latest=deterministic,
                message="Safe local provider used by default.",
            ),
            _provider_status(
                "bart",
                configured=True,
                enabled=bart_enabled,
                model_name=os.environ.get("BART_MODEL_NAME") or "facebook/bart-large-cnn",
                latest=latest.get("bart"),
                message="Real Hugging Face execution requires RUN_REAL_BASELINES=1.",
            ),
            _provider_status(
                "pegasus",
                configured=True,
                enabled=pegasus_enabled,
                model_name=os.environ.get("PEGASUS_MODEL_NAME") or "google/pegasus-xsum",
                latest=latest.get("pegasus"),
                message="Real Hugging Face execution requires RUN_REAL_BASELINES=1.",
            ),
            _provider_status(
                "gemini",
                configured=bool(self.settings.gemini_api_key),
                enabled=gemini_enabled,
                model_name=self.settings.gemini_model,
                latest=latest.get("gemini"),
                message=(
                    "Gemini requires RAG_LLM_PROVIDER=gemini, external enabled, "
                    "PHI allowance, and API key."
                ),
            ),
        ]

    def _evaluation_layers(self) -> list[EvaluationLayerStatus]:
        benchmark = self.benchmark_status()
        return [
            EvaluationLayerStatus(
                layer="functional_validation",
                status="runnable",
                message="Runs now on mock/de-identified demo data.",
            ),
            EvaluationLayerStatus(
                layer="real_ehr_benchmark",
                status=benchmark.status,
                message=benchmark.message,
                expected_path=benchmark.dataset_path,
            ),
            EvaluationLayerStatus(
                layer="human_evaluation",
                status="runnable",
                message="Can collect evaluator scores on generated demo/mock summaries.",
            ),
        ]

    def _seed_demo_data(self, state: dict[str, Any]) -> None:
        if self.settings.environment != "production":
            Base.metadata.create_all(bind=self.session.get_bind())
        result = seed_mock_data(self.session)
        state["patient_id"] = result.patient_id
        state["encounter_id"] = result.encounter_id
        state["seed_summary_id"] = result.summary_id

    def _patient_detail(self, state: dict[str, Any]) -> None:
        self._require(self.session.get(Patient, state["patient_id"]))

    def _documents_exist(self, state: dict[str, Any]) -> None:
        self._require(self.repository.table_counts()["documents"] > 0)

    def _generate_summary(
        self,
        state: dict[str, Any],
        tenant_id: str,
        actor_external_id: str,
    ) -> None:
        service = DeterministicSummaryService(
            SummaryRepository(self.session),
            SafetyService(),
            self.audit_service,
            self.settings,
        )
        generated = service.generate(
            str(state["patient_id"]),
            SummaryGenerateRequest(
                encounter_id=state["encounter_id"],
                summary_type="patient_snapshot",
                language="vi",
                model_provider="deterministic",
            ),
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
        )
        state["generated_summary_id"] = generated.summary_id
        summary = SummaryRepository(self.session).get_summary(generated.summary_id)
        self._require(summary and summary.status.value == "draft")

    def _summary_has_claims(self, state: dict[str, Any]) -> None:
        summary = SummaryRepository(self.session).get_summary(state["generated_summary_id"])
        self._require(summary and summary.claims)

    def _citations_or_unsupported_exist(self, state: dict[str, Any]) -> None:
        summary = SummaryRepository(self.session).get_summary(state["generated_summary_id"])
        self._require(summary is not None)
        has_citation = any(claim.citations for claim in summary.claims)
        has_flagged = any(
            claim.support_status.value in {"unsupported", "insufficient_evidence", "conflicting"}
            for claim in summary.claims
        )
        self._require(has_citation or has_flagged)

    def _citation_source_works(
        self,
        state: dict[str, Any],
        tenant_id: str,
        actor_external_id: str,
    ) -> None:
        summary = SummaryRepository(self.session).get_summary(state["generated_summary_id"])
        self._require(summary is not None)
        citation = next(
            (citation for claim in summary.claims for citation in claim.citations),
            None,
        )
        self._require(citation is not None)
        source = CitationService(
            SummaryRepository(self.session),
            CitationRepository(self.session),
            self.audit_service,
        ).source(
            str(citation.citation_id),
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
        )
        self._require(source.patient_id == summary.patient_id)

    def _hitl_review_works(
        self,
        state: dict[str, Any],
        tenant_id: str,
        actor_external_id: str,
    ) -> None:
        review_service = ReviewService(SummaryRepository(self.session), self.audit_service)
        summary_id = str(state["generated_summary_id"])
        review_service.start_review(
            summary_id,
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            role_code="doctor",
        )
        review_service.edit(
            summary_id,
            SummaryEditRequest(
                edited_summary_text="Functional validation edit of a draft summary.",
                edit_comment="Functional validation smoke edit.",
            ),
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            role_code="doctor",
        )
        review_service.reject(
            summary_id,
            SummaryRejectRequest(
                rejection_reason="other",
                rejection_comment="Functional validation rejection path.",
            ),
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            role_code="doctor",
        )
        self._generate_summary(state, tenant_id, actor_external_id)
        review_service.approve(
            str(state["generated_summary_id"]),
            SummaryApproveRequest(approval_comment="Functional validation approval path."),
            tenant_id=tenant_id,
            actor_external_id=actor_external_id,
            role_code="doctor",
        )

    def _sensitive_audit_exists(self) -> None:
        for action in ("generate_summary", "view_citation", "edit_summary", "approve_summary", "reject_summary"):
            self._require(self.repository.audit_action_exists(action))

    def _metrics_work(self) -> None:
        service = MetricsService(MetricsRepository(self.session))
        service.usage(role_code="clinical_admin")
        service.summary_quality(role_code="clinical_admin")
        service.safety(role_code="clinical_admin")
        service.review(role_code="clinical_admin")

    @staticmethod
    def _require(condition: Any) -> None:
        if not condition:
            raise ValueError("Required validation condition was not met.")


def _provider_status(
    provider: str,
    *,
    configured: bool,
    enabled: bool,
    model_name: str | None,
    latest: ModelRun | None,
    message: str,
) -> EvaluationProviderStatus:
    if not configured:
        status = "not_configured"
    elif not enabled:
        status = "disabled"
    elif latest is not None and latest.status != "completed":
        status = "last_run_failed"
    else:
        status = "ready"
    return EvaluationProviderStatus(
        provider=provider,
        configured=configured,
        enabled=enabled,
        status=status,
        model_name=latest.model_name if latest else model_name,
        last_run_status=latest.status if latest else None,
        latency_ms=latest.latency_ms if latest else None,
        message=message,
    )


def _readiness_item(name: str, ready: bool, ready_message: str) -> EvaluationReadinessItem:
    return EvaluationReadinessItem(
        name=name,
        status="ready" if ready else "not_tested",
        message=ready_message if ready else "No local validation data available yet.",
    )


def _real_baselines_enabled() -> bool:
    return os.environ.get("RUN_REAL_BASELINES") == "1" or os.environ.get("RAG_RUN_REAL_BASELINES") == "1"


def _validate_benchmark_jsonl(path: Path) -> tuple[bool, str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            lines = [line for _, line in zip(range(20), handle) if line.strip()]
    except OSError as exc:
        return False, f"Benchmark dataset could not be read: {exc}"
    if not lines:
        return False, "Benchmark dataset is empty."
    for index, line in enumerate(lines, start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            return False, f"Benchmark dataset line {index} is invalid JSON: {exc}"
        missing = REQUIRED_BENCHMARK_KEYS.difference(row)
        if missing:
            return False, f"Benchmark dataset line {index} is missing keys: {sorted(missing)}"
        if not str(row.get("source_note") or "").strip() or not str(row.get("reference_summary") or "").strip():
            return False, f"Benchmark dataset line {index} has empty source_note or reference_summary."
    return True, "Processed real EHR benchmark dataset is present and follows the expected schema."


def _human_summary(evaluations: list[HumanEvaluation]) -> HumanEvaluationSummaryResponse:
    risks = Counter(item.hallucination_risk for item in evaluations)
    providers = Counter(item.model_provider or "unknown" for item in evaluations)
    return HumanEvaluationSummaryResponse(
        total_evaluations=len(evaluations),
        average_factual_correctness_score=_average([item.factual_correctness_score for item in evaluations]),
        average_completeness_score=_average([item.completeness_score for item in evaluations]),
        average_conciseness_score=_average([item.conciseness_score for item in evaluations]),
        average_readability_score=_average([item.readability_score for item in evaluations]),
        average_citation_usefulness_score=_average([item.citation_usefulness_score for item in evaluations]),
        hallucination_risk_distribution=[
            MetricCountItem(key=str(key), count=int(count)) for key, count in risks.items()
        ],
        evaluations_by_provider=[
            MetricCountItem(key=str(key), count=int(count)) for key, count in providers.items()
        ],
        recent_evaluations=[_human_evaluation_response(item) for item in evaluations[:10]],
    )


def _human_evaluation_response(evaluation: HumanEvaluation) -> HumanEvaluationResponse:
    return HumanEvaluationResponse.model_validate(evaluation)


def _average(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)


def _provider_label(provider: str | None) -> str | None:
    if provider == "local":
        return "deterministic"
    return provider
