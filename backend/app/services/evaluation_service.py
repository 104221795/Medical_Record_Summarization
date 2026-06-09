from __future__ import annotations

import csv
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
    BenchmarkResultRow,
    BenchmarkResultsResponse,
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
from ..evaluation.clinical_metrics import (
    aggregate_clinical_metrics,
    compute_clinical_record_metrics,
    serialize_failure_categories,
)


BENCHMARK_DATASET_PATH = ROOT_DIR / "data" / "processed" / "ehr_benchmark" / "test.jsonl"
BENCHMARK_OUTPUT_PATH = ROOT_DIR / "results" / "ehr_benchmark" / "model_comparison.csv"
BENCHMARK_RUNNER_PATH = ROOT_DIR / "scripts" / "run_baseline_summarization.py"
MEDIUM_BENCHMARK_OUTPUT_DIR = Path("D:/clin_summ_outputs/medium_benchmark_bart_pegasus")
SUMMARIZATION_ONLY_OUTPUT_DIR = Path("D:/clin_summ_outputs/summarization_only_benchmark")
CLINICAL_CONTEXT_OUTPUT_DIR = Path("D:/clin_summ_outputs/clinical_context_benchmark")
RAG_GROUNDED_OUTPUT_DIR = Path("D:/clin_summ_outputs/rag_grounded_benchmark")
MEDIUM_BENCHMARK_COMPARISON_PATH = MEDIUM_BENCHMARK_OUTPUT_DIR / "model_comparison.csv"
MEDIUM_BENCHMARK_REPORT_PATH = MEDIUM_BENCHMARK_OUTPUT_DIR / "EVALUATION_REPORT.md"
MEDIUM_BENCHMARK_FAILURE_PATH = MEDIUM_BENCHMARK_OUTPUT_DIR / "failure_analysis.md"
BENCHMARK_DISCOVERY_DIRS = [
    Path("D:/clin_summ_outputs/rag_grounded_benchmark"),
    Path("D:/clin_summ_outputs/clinical_context_benchmark"),
    Path("D:/clin_summ_outputs/summarization_only_benchmark"),
    Path("D:/clin_summ_outputs/medium_benchmark"),
    Path("D:/clin_summ_outputs/medium_benchmark_bart_pegasus"),
    Path("D:/clin_summ_outputs/performance_benchmark"),
]
PREDICTION_FILES = {
    "deterministic": "deterministic_predictions.jsonl",
    "bart": "bart_predictions.jsonl",
    "pegasus": "pegasus_predictions.jsonl",
    "pegasus_pubmed": "pegasus_pubmed_predictions.jsonl",
    "pegasus_cnn_dailymail": "pegasus_cnn_dailymail_predictions.jsonl",
}
FAILURE_CATEGORIES = [
    "hallucinated content",
    "missing diagnosis",
    "missing medication",
    "missing timeline",
    "incomplete summary",
    "retrieval-related failure",
    "source data limitation",
]
CLINICAL_ROW_FIELDS = [
    "citation_coverage",
    "unsupported_claim_rate",
    "factuality_proxy_score",
    "missing_diagnosis_rate",
    "missing_medication_rate",
    "timeline_completeness",
    "hallucinated_clinical_entity_count",
    "critical_info_omission_rate",
    "latency_p50_ms",
    "latency_p95_ms",
]
PER_RECORD_CLINICAL_FIELDS = [
    "citation_coverage",
    "unsupported_claim_rate",
    "factuality_proxy_score",
    "missing_diagnosis_rate",
    "missing_medication_rate",
    "timeline_completeness",
    "hallucinated_clinical_entity_count",
    "critical_info_omission_rate",
]
PROXY_EVALUATION_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, "
    "or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as "
    "MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes."
)
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

    def benchmark_results(self, benchmark_type: str | None = None) -> BenchmarkResultsResponse:
        selected_dir, discovered = _select_benchmark_output_dir(BENCHMARK_DISCOVERY_DIRS, benchmark_type)
        comparison_path = selected_dir / "model_comparison.csv"
        report_path = selected_dir / "EVALUATION_REPORT.md"
        failure_path = selected_dir / "failure_analysis.md"
        manifest_path = _benchmark_manifest_path(selected_dir)
        per_record_path = selected_dir / "per_record_metrics.csv"
        rows = _read_model_comparison(comparison_path)
        rows = _merge_prediction_rows(selected_dir, rows)
        rows = _enrich_rows(selected_dir, rows, manifest_path, per_record_path)
        completed = [row for row in rows if row.rougeL is not None and row.completed_count > 0]
        best = max(completed, key=lambda row: row.rougeL or 0.0).model_provider if completed else None
        prediction_files = _prediction_file_availability(selected_dir)
        per_record_summary = _per_record_metric_summary(per_record_path)
        clinical_summary = _clinical_metric_summary(per_record_path, selected_dir)
        failure_examples = _per_record_failure_examples(selected_dir, limit=20)
        failure_summary = _failure_analysis_summary(failure_path, per_record_path)
        return BenchmarkResultsResponse(
            output_dir=str(selected_dir),
            selected_output_dir=str(selected_dir),
            benchmark_type=_benchmark_type(selected_dir),
            discovered_benchmark_folders=discovered,
            models=rows,
            per_record_metric_summary=per_record_summary,
            clinical_metric_summary=clinical_summary,
            per_record_failure_examples=failure_examples,
            prediction_file_availability=prediction_files,
            failure_analysis_summary=failure_summary,
            artifact_paths={
                "model_comparison": str(comparison_path) if comparison_path.exists() else None,
                "per_record_metrics": str(per_record_path) if per_record_path.exists() else None,
                "evaluation_run_manifest": str(manifest_path) if manifest_path.exists() else None,
                "rag_benchmark_manifest": str(selected_dir / "rag_benchmark_manifest.json")
                if (selected_dir / "rag_benchmark_manifest.json").exists()
                else None,
                "summarization_only_manifest": str(selected_dir / "summarization_only_manifest.json")
                if (selected_dir / "summarization_only_manifest.json").exists()
                else None,
                "clinical_context_manifest": str(selected_dir / "clinical_context_manifest.json")
                if (selected_dir / "clinical_context_manifest.json").exists()
                else None,
                "clinical_context_records": str(selected_dir / "clinical_context_records.jsonl")
                if (selected_dir / "clinical_context_records.jsonl").exists()
                else None,
                "retrieval_metrics": str(selected_dir / "retrieval_metrics.csv")
                if (selected_dir / "retrieval_metrics.csv").exists()
                else None,
                "retrieved_evidence": str(selected_dir / "retrieved_evidence.jsonl")
                if (selected_dir / "retrieved_evidence.jsonl").exists()
                else None,
                "run_log": str(selected_dir / "run.log") if (selected_dir / "run.log").exists() else None,
                "evaluation_report": str(report_path) if report_path.exists() else None,
                "failure_analysis": str(failure_path) if failure_path.exists() else None,
                "per_record_failure_analysis": str(selected_dir / "per_record_failure_analysis.jsonl")
                if (selected_dir / "per_record_failure_analysis.jsonl").exists()
                else None,
                "reproducibility_manifest": str(selected_dir / "reproducibility_manifest.json")
                if (selected_dir / "reproducibility_manifest.json").exists()
                else None,
                "pre_rag_readiness_report": str(selected_dir / "PRE_RAG_READINESS_REPORT.md")
                if (selected_dir / "PRE_RAG_READINESS_REPORT.md").exists()
                else None,
                "dataset_diversity_report": str(selected_dir / "dataset_diversity_report.md")
                if (selected_dir / "dataset_diversity_report.md").exists()
                else None,
                "citation_grounding_report": str(selected_dir / "citation_grounding_report.md")
                if (selected_dir / "citation_grounding_report.md").exists()
                else None,
                "dataset_strata_manifest": str(selected_dir / "dataset_strata_manifest.json")
                if (selected_dir / "dataset_strata_manifest.json").exists()
                else None,
                "human_review_rubric": str(selected_dir / "human_review_rubric.csv")
                if (selected_dir / "human_review_rubric.csv").exists()
                else None,
                "background_jobs_readiness": str(selected_dir / "background_jobs_readiness_report.md")
                if (selected_dir / "background_jobs_readiness_report.md").exists()
                else None,
                "production_tech_gap": str(selected_dir / "production_tech_gap_report.md")
                if (selected_dir / "production_tech_gap_report.md").exists()
                else None,
            },
            data_freshness_timestamp=_freshness_timestamp(selected_dir),
            best_model_by_rougeL=best,
            report_path=str(report_path),
            failure_analysis_path=str(failure_path),
            report_exists=report_path.exists(),
            failure_analysis_exists=failure_path.exists(),
            proxy_warning=PROXY_EVALUATION_WARNING,
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
        latest = self.repository.latest_model_run(
            ["local", "deterministic", "bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail", "gemini"]
        )
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
                model_name=os.environ.get("PEGASUS_MODEL_NAME") or "google/pegasus-pubmed",
                latest=latest.get("pegasus"),
                message="Real Hugging Face execution requires RUN_REAL_BASELINES=1.",
            ),
            _provider_status(
                "pegasus_pubmed",
                configured=True,
                enabled=pegasus_enabled,
                model_name=os.environ.get("PEGASUS_PUBMED_MODEL_NAME") or "google/pegasus-pubmed",
                latest=latest.get("pegasus_pubmed"),
                message="Real Hugging Face execution requires RUN_REAL_BASELINES=1.",
            ),
            _provider_status(
                "pegasus_cnn_dailymail",
                configured=True,
                enabled=pegasus_enabled,
                model_name=os.environ.get("PEGASUS_CNN_DAILYMAIL_MODEL_NAME") or "google/pegasus-cnn_dailymail",
                latest=latest.get("pegasus_cnn_dailymail"),
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


def _read_model_comparison(path: Path) -> list[BenchmarkResultRow]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_benchmark_row(row) for row in reader]


def _select_benchmark_output_dir(
    candidate_dirs: list[Path],
    benchmark_type: str | None = None,
) -> tuple[Path, list[dict[str, Any]]]:
    discovered = [_folder_info(path) for path in candidate_dirs]
    existing = [item for item in discovered if item["exists"]]
    if benchmark_type:
        existing = [item for item in existing if item["benchmark_type"] == benchmark_type]
    if not existing:
        fallback_by_type = {
            "rag_grounded": RAG_GROUNDED_OUTPUT_DIR,
            "clinical_context": CLINICAL_CONTEXT_OUTPUT_DIR,
            "summarization_only": MEDIUM_BENCHMARK_OUTPUT_DIR,
        }
        selected = fallback_by_type.get(benchmark_type or "", MEDIUM_BENCHMARK_OUTPUT_DIR)
        for item in discovered:
            item["selected"] = item["path"] == str(selected)
        return selected, discovered
    ranked = sorted(existing, key=lambda item: (item["has_model_comparison"], item["last_modified"] or ""), reverse=True)
    selected = Path(ranked[0]["path"])
    for item in discovered:
        item["selected"] = item["path"] == str(selected)
    return selected, discovered


def _benchmark_manifest_path(path: Path) -> Path:
    for filename in (
        "rag_benchmark_manifest.json",
        "clinical_context_manifest.json",
        "summarization_only_manifest.json",
        "evaluation_run_manifest.json",
    ):
        candidate = path / filename
        if candidate.exists():
            return candidate
    return path / "evaluation_run_manifest.json"


def _benchmark_type(path: Path) -> str:
    if (path / "rag_benchmark_manifest.json").exists() or (path / "retrieval_metrics.csv").exists():
        return "rag_grounded"
    if (path / "clinical_context_manifest.json").exists() or (path / "clinical_context_records.jsonl").exists():
        return "clinical_context"
    return "summarization_only"


def _folder_info(path: Path) -> dict[str, Any]:
    files = list(path.glob("*")) if path.exists() else []
    last_modified = max((file.stat().st_mtime for file in files if file.is_file()), default=0.0)
    pubmed_path = path / PREDICTION_FILES["pegasus_pubmed"]
    pubmed_count = _jsonl_count(pubmed_path)
    manifest_path = _benchmark_manifest_path(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "selected": False,
        "has_model_comparison": (path / "model_comparison.csv").exists(),
        "has_per_record_metrics": (path / "per_record_metrics.csv").exists(),
        "has_manifest": manifest_path.exists(),
        "has_rag_manifest": (path / "rag_benchmark_manifest.json").exists(),
        "has_clinical_context_manifest": (path / "clinical_context_manifest.json").exists(),
        "has_summarization_only_manifest": (path / "summarization_only_manifest.json").exists(),
        "benchmark_type": _benchmark_type(path),
        "has_pegasus_pubmed_predictions": pubmed_path.exists(),
        "pegasus_pubmed_record_count": pubmed_count,
        "has_pegasus_pubmed_200": pubmed_count >= 200,
        "last_modified": _iso_mtime(last_modified) if last_modified else None,
    }


def _merge_prediction_rows(output_dir: Path, rows: list[BenchmarkResultRow]) -> list[BenchmarkResultRow]:
    by_provider = {row.model_provider: row for row in rows}
    for provider, filename in PREDICTION_FILES.items():
        if provider in by_provider:
            continue
        prediction_path = output_dir / filename
        if not prediction_path.exists():
            continue
        row = _prediction_row(provider, prediction_path)
        if row:
            by_provider[provider] = row
    ordered = ["deterministic", "bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail"]
    return [by_provider[key] for key in ordered if key in by_provider] + [
        row for key, row in by_provider.items() if key not in ordered and key != "gemini"
    ] + ([by_provider["gemini"]] if "gemini" in by_provider else [])


def _prediction_row(provider: str, path: Path) -> BenchmarkResultRow | None:
    rows = [_ensure_clinical_metrics(row) for row in _read_prediction_jsonl(path)]
    if not rows:
        return None
    completed = [row for row in rows if row.get("status") == "completed"]
    first = rows[0]
    record_count = len(rows)
    completed_count = len(completed)
    failed_count = sum(1 for row in rows if row.get("status") not in {"completed", "skipped"})
    skipped_count = sum(1 for row in rows if row.get("status") == "skipped")
    model_name = str(first.get("model_name") or _default_model_name(provider))
    stage_name = str(first.get("stage") or "")
    clinical_metrics = aggregate_clinical_metrics(rows)
    return BenchmarkResultRow(
        model_provider=provider,
        model_name=model_name,
        status="completed" if completed_count == record_count else "partial",
        record_count=record_count,
        completed_count=completed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        rouge1=_mean([row.get("rouge1") for row in completed]),
        rouge2=_mean([row.get("rouge2") for row in completed]),
        rougeL=_mean([row.get("rougeL") for row in completed]),
        bertscore_status="not_requested",
        bertscore_model_type=None,
        average_latency_ms=_mean([row.get("latency_ms") for row in completed]),
        latency_p50_ms=clinical_metrics.get("latency_p50_ms"),
        latency_p95_ms=clinical_metrics.get("latency_p95_ms"),
        citation_coverage=clinical_metrics.get("citation_coverage"),
        unsupported_claim_rate=clinical_metrics.get("unsupported_claim_rate"),
        factuality_proxy_score=clinical_metrics.get("factuality_proxy_score"),
        missing_diagnosis_rate=clinical_metrics.get("missing_diagnosis_rate"),
        missing_medication_rate=clinical_metrics.get("missing_medication_rate"),
        timeline_completeness=clinical_metrics.get("timeline_completeness"),
        hallucinated_clinical_entity_count=clinical_metrics.get("hallucinated_clinical_entity_count"),
        critical_info_omission_rate=clinical_metrics.get("critical_info_omission_rate"),
        stage_name=stage_name or None,
        checkpoint=model_name,
        provider_type="api" if provider == "gemini" else "local",
        domain_fit=_domain_fit(provider),
        failure_counts=_failure_counts_from_prediction_rows(rows),
        notes="Proxy benchmark, not clinical validation.",
    )


def _enrich_rows(
    output_dir: Path,
    rows: list[BenchmarkResultRow],
    manifest_path: Path,
    per_record_path: Path,
) -> list[BenchmarkResultRow]:
    stages = _manifest_stages(manifest_path)
    per_record_failures = _per_record_failures_by_provider(per_record_path)
    per_record_clinical = _per_record_clinical_by_provider(per_record_path)
    prediction_clinical = _prediction_clinical_by_provider(output_dir)
    for row in rows:
        row.checkpoint = row.checkpoint or row.model_name
        row.provider_type = row.provider_type or ("api" if row.model_provider == "gemini" else "local")
        row.domain_fit = row.domain_fit or _domain_fit(row.model_provider)
        stage = stages.get(row.model_provider)
        if stage:
            row.stage_name = row.stage_name or stage.get("name")
            row.total_runtime_seconds = _float_value_any(stage.get("runtime_seconds"))
            if not row.notes and stage.get("notes"):
                row.notes = str(stage.get("notes"))
        if not row.failure_counts:
            row.failure_counts = per_record_failures.get(row.model_provider)
        clinical = per_record_clinical.get(row.model_provider) or prediction_clinical.get(row.model_provider, {})
        for field in CLINICAL_ROW_FIELDS:
            if getattr(row, field, None) is None and field in clinical:
                setattr(row, field, clinical[field])
    return rows


def _manifest_stages(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for stage in data.get("stages", []):
        provider = stage.get("model_provider")
        if not provider:
            continue
        current = result.get(provider)
        if current is None or int(stage.get("records") or 0) >= int(current.get("records") or 0):
            result[str(provider)] = stage
    return result


def _read_prediction_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def _prediction_file_availability(output_dir: Path) -> dict[str, Any]:
    availability: dict[str, Any] = {}
    for provider, filename in PREDICTION_FILES.items():
        path = output_dir / filename
        availability[filename] = {
            "provider": provider,
            "exists": path.exists(),
            "record_count": _jsonl_count(path),
            "path": str(path),
            "last_modified": _iso_mtime(path.stat().st_mtime) if path.exists() else None,
        }
    return availability


def _per_record_metric_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "not_available"}
    failure_counts = Counter()
    providers = Counter()
    provider_metrics: dict[str, list[dict[str, Any]]] = {}
    rows = 0
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows += 1
                provider = row.get("model_provider") or "unknown"
                providers[provider] += 1
                provider_metrics.setdefault(provider, []).append(row)
                for category in _split_failure_categories(row.get("failure_categories")):
                    failure_counts[category] += 1
    except OSError:
        return {"status": "not_available"}
    return {
        "status": "available",
        "row_count": rows,
        "providers": dict(providers),
        "failure_counts": dict(failure_counts),
        "clinical_metrics_by_provider": {
            provider: _aggregate_csv_clinical(rows)
            for provider, rows in provider_metrics.items()
        },
        "bertscore": "not_available_in_current_run",
    }


def _clinical_metric_summary(per_record_path: Path, output_dir: Path) -> dict[str, Any]:
    if per_record_path.exists():
        provider_rows: dict[str, list[dict[str, Any]]] = {}
        try:
            with per_record_path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    provider_rows.setdefault(row.get("model_provider") or "unknown", []).append(row)
        except OSError:
            provider_rows = {}
        if provider_rows:
            by_provider = {
                provider: _aggregate_csv_clinical(rows)
                for provider, rows in provider_rows.items()
            }
            if _has_any_clinical_metric(by_provider):
                return {
                    "status": "available",
                    "source": "per_record_metrics.csv",
                    "by_provider": by_provider,
                }

    prediction_rows = []
    for filename in PREDICTION_FILES.values():
        prediction_rows.extend(_ensure_clinical_metrics(row) for row in _read_prediction_jsonl(output_dir / filename))
    if not prediction_rows:
        return {"status": "not_available"}
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for row in prediction_rows:
        by_provider.setdefault(row.get("model_provider") or "unknown", []).append(row)
    return {
        "status": "available",
        "source": "prediction_jsonl",
        "by_provider": {
            provider: aggregate_clinical_metrics(rows)
            for provider, rows in by_provider.items()
        },
    }


def _failure_analysis_summary(failure_path: Path, per_record_path: Path) -> dict[str, Any]:
    counts = _failure_counts_from_markdown(failure_path)
    source = "failure_analysis.md" if counts else "per_record_metrics.csv"
    if not counts:
        counts = _aggregate_failure_counts(per_record_path)
    return {
        "status": "available" if counts else "not_available",
        "source": source if counts else None,
        "counts": counts or {category: "Not available in current run" for category in FAILURE_CATEGORIES},
    }


def _failure_counts_from_markdown(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    counts: dict[str, int] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return counts
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- ") or ": `" not in stripped:
            continue
        key, value = stripped[2:].split(": `", 1)
        try:
            counts[key.strip()] = int(value.strip("` "))
        except ValueError:
            continue
    return counts


def _aggregate_failure_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    counts = Counter()
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                for category in _split_failure_categories(row.get("failure_categories")):
                    counts[category] += 1
    except OSError:
        return {}
    return dict(counts)


def _per_record_failures_by_provider(path: Path) -> dict[str, dict[str, int]]:
    if not path.exists():
        return {}
    counts: dict[str, Counter] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                provider = row.get("model_provider") or "unknown"
                counts.setdefault(provider, Counter())
                for category in _split_failure_categories(row.get("failure_categories")):
                    counts[provider][category] += 1
    except OSError:
        return {}
    return {provider: dict(counter) for provider, counter in counts.items()}


def _per_record_clinical_by_provider(path: Path) -> dict[str, dict[str, float | None]]:
    if not path.exists():
        return {}
    rows_by_provider: dict[str, list[dict[str, Any]]] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows_by_provider.setdefault(row.get("model_provider") or "unknown", []).append(row)
    except OSError:
        return {}
    return {
        provider: _aggregate_csv_clinical(rows)
        for provider, rows in rows_by_provider.items()
    }


def _prediction_clinical_by_provider(output_dir: Path) -> dict[str, dict[str, Any]]:
    by_provider: dict[str, list[dict[str, Any]]] = {}
    for provider, filename in PREDICTION_FILES.items():
        rows = [_ensure_clinical_metrics(row) for row in _read_prediction_jsonl(output_dir / filename)]
        if rows:
            by_provider[provider] = rows
    return {
        provider: aggregate_clinical_metrics(rows)
        for provider, rows in by_provider.items()
    }


def _has_any_clinical_metric(by_provider: dict[str, dict[str, Any]]) -> bool:
    for metrics in by_provider.values():
        for field in PER_RECORD_CLINICAL_FIELDS:
            if metrics.get(field) is not None:
                return True
    return False


def _aggregate_csv_clinical(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "citation_coverage": _mean([row.get("citation_coverage") for row in rows]),
        "unsupported_claim_rate": _mean([row.get("unsupported_claim_rate") for row in rows]),
        "factuality_proxy_score": _mean([row.get("factuality_proxy_score") for row in rows]),
        "missing_diagnosis_rate": _mean([row.get("missing_diagnosis_rate") for row in rows]),
        "missing_medication_rate": _mean([row.get("missing_medication_rate") for row in rows]),
        "timeline_completeness": _mean([row.get("timeline_completeness") for row in rows]),
        "hallucinated_clinical_entity_count": _mean([row.get("hallucinated_clinical_entity_count") for row in rows]),
        "critical_info_omission_rate": _mean([row.get("critical_info_omission_rate") for row in rows]),
        "latency_p50_ms": _percentile([_float_value_any(row.get("latency_ms")) for row in rows], 50),
        "latency_p95_ms": _percentile([_float_value_any(row.get("latency_ms")) for row in rows], 95),
    }


def _failure_counts_from_prediction_rows(rows: list[dict[str, Any]]) -> dict[str, int] | None:
    counts = Counter()
    for row in rows:
        for category in _split_failure_categories(row.get("failure_categories")):
            counts[category] += 1
    return dict(counts) if counts else None


def _per_record_failure_examples(output_dir: Path, *, limit: int) -> list[dict[str, Any]]:
    explicit_path = output_dir / "per_record_failure_analysis.jsonl"
    if explicit_path.exists():
        rows = _read_failure_jsonl(explicit_path)
    else:
        rows = []
        for filename in PREDICTION_FILES.values():
            rows.extend(_failure_payload_from_prediction(row) for row in _read_prediction_jsonl(output_dir / filename))
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        note_id = str(row.get("note_id") or "")
        if not note_id:
            continue
        current = grouped.setdefault(
            note_id,
            {
                "note_id": note_id,
                "patient_id": row.get("patient_id") or "",
                "encounter_id": row.get("encounter_id") or "",
                "dataset": row.get("dataset") or "",
                "input_note": row.get("input_note") or row.get("source_note") or "",
                "reference_summary": row.get("reference_summary") or "",
                "retrieved_evidence": row.get("retrieved_evidence") or "",
                "citations": row.get("citations") or [],
                "failure_labels": set(),
                "model_outputs": [],
                "severity": 0.0,
            },
        )
        labels = _split_failure_categories(row.get("failure_labels") or row.get("failure_categories"))
        current["failure_labels"].update(labels)
        rouge_l = _float_value_any(row.get("rougeL"))
        current["severity"] += len(labels) + (1.0 - rouge_l if rouge_l is not None else 1.0)
        current["model_outputs"].append(
            {
                "model_provider": row.get("model_provider") or "",
                "model_name": row.get("model_name") or "",
                "status": row.get("status") or "",
                "generated_summary": row.get("generated_summary") or "",
                "rouge1": row.get("rouge1"),
                "rouge2": row.get("rouge2"),
                "rougeL": row.get("rougeL"),
                "latency_ms": row.get("latency_ms"),
                "clinical_metrics": row.get("clinical_metrics") or {
                    field: row.get(field)
                    for field in PER_RECORD_CLINICAL_FIELDS
                },
                "failure_labels": labels,
                "error_message": row.get("error_message"),
            }
        )
    examples = []
    for item in grouped.values():
        item["failure_labels"] = sorted(item["failure_labels"])
        item["model_outputs"] = sorted(item["model_outputs"], key=lambda row: row.get("model_provider") or "")
        examples.append(item)
    return sorted(examples, key=lambda item: item["severity"], reverse=True)[:limit]


def _failure_payload_from_prediction(row: dict[str, Any]) -> dict[str, Any]:
    enriched = _ensure_clinical_metrics(row)
    return {
        "note_id": enriched.get("note_id", ""),
        "patient_id": enriched.get("patient_id", ""),
        "encounter_id": enriched.get("encounter_id", ""),
        "dataset": enriched.get("dataset", ""),
        "model_provider": enriched.get("model_provider", ""),
        "model_name": enriched.get("model_name", ""),
        "status": enriched.get("status", ""),
        "input_note": enriched.get("source_note", ""),
        "generated_summary": enriched.get("generated_summary", ""),
        "reference_summary": enriched.get("reference_summary", ""),
        "retrieved_evidence": enriched.get("retrieved_evidence") or enriched.get("evidence") or "",
        "citations": enriched.get("citations") or [],
        "rouge1": enriched.get("rouge1"),
        "rouge2": enriched.get("rouge2"),
        "rougeL": enriched.get("rougeL"),
        "latency_ms": enriched.get("latency_ms"),
        "clinical_metrics": {
            field: enriched.get(field)
            for field in PER_RECORD_CLINICAL_FIELDS
        },
        "failure_labels": enriched.get("failure_categories") or [],
        "error_message": enriched.get("error_message"),
    }


def _read_failure_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def _ensure_clinical_metrics(row: dict[str, Any]) -> dict[str, Any]:
    if all(row.get(field) not in {None, ""} for field in ("factuality_proxy_score", "critical_info_omission_rate")):
        if "failure_categories" not in row and "failure_labels" in row:
            row["failure_categories"] = row["failure_labels"]
        return row
    enriched = dict(row)
    enriched.update(compute_clinical_record_metrics(enriched))
    enriched["failure_categories"] = serialize_failure_categories(enriched.get("failure_categories"))
    return enriched


def _split_failure_categories(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _freshness_timestamp(output_dir: Path) -> str | None:
    files = [file for file in output_dir.glob("*") if file.is_file()]
    last_modified = max((file.stat().st_mtime for file in files), default=0.0)
    return _iso_mtime(last_modified) if last_modified else None


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _mean(values: list[Any]) -> float | None:
    numbers = [_float_value_any(value) for value in values]
    clean = [value for value in numbers if value is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


def _percentile(values: list[Any], percentile: int) -> float | None:
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return round(float(clean[0]), 4)
    rank = (len(clean) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(clean) - 1)
    weight = rank - lower
    return round((clean[lower] * (1 - weight)) + (clean[upper] * weight), 4)


def _float_value_any(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_mtime(value: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(value, tz=UTC).isoformat()


def _default_model_name(provider: str) -> str:
    return {
        "deterministic": "deterministic_sentence_baseline",
        "bart": "facebook/bart-large-cnn",
        "pegasus": "google/pegasus-xsum",
        "pegasus_pubmed": "google/pegasus-pubmed",
        "pegasus_cnn_dailymail": "google/pegasus-cnn_dailymail",
        "gemini": "gemini configured provider",
    }.get(provider, provider)


def _domain_fit(provider: str) -> str:
    return {
        "deterministic": "Fast extractive baseline",
        "bart": "General summarization baseline",
        "pegasus": "General Pegasus baseline",
        "pegasus_pubmed": "Medical/scientific",
        "pegasus_cnn_dailymail": "General news summarization baseline",
        "gemini": "External API LLM; not official unless fully benchmarked",
    }.get(provider, "Not available in current run")


def _benchmark_row(row: dict[str, str]) -> BenchmarkResultRow:
    return BenchmarkResultRow(
        model_provider=row.get("model_provider", ""),
        model_name=row.get("model_name", ""),
        status=row.get("status", ""),
        record_count=_int_value(row.get("record_count")),
        completed_count=_int_value(row.get("completed_count")),
        failed_count=_int_value(row.get("failed_count")),
        skipped_count=_int_value(row.get("skipped_count")),
        rouge1=_float_value(row.get("rouge1")),
        rouge2=_float_value(row.get("rouge2")),
        rougeL=_float_value(row.get("rougeL")),
        bertscore_precision=_float_value(row.get("bertscore_precision")),
        bertscore_recall=_float_value(row.get("bertscore_recall")),
        bertscore_f1=_float_value(row.get("bertscore_f1")),
        bertscore_status=row.get("bertscore_status") or None,
        bertscore_model_type=row.get("bertscore_model_type") or None,
        average_latency_ms=_float_value(row.get("average_latency_ms")),
        latency_p50_ms=_float_value(row.get("latency_p50_ms")),
        latency_p95_ms=_float_value(row.get("latency_p95_ms")),
        citation_coverage=_float_value(row.get("citation_coverage")),
        unsupported_claim_rate=_float_value(row.get("unsupported_claim_rate")),
        factuality_proxy_score=_float_value(row.get("factuality_proxy_score")),
        missing_diagnosis_rate=_float_value(row.get("missing_diagnosis_rate")),
        missing_medication_rate=_float_value(row.get("missing_medication_rate")),
        timeline_completeness=_float_value(row.get("timeline_completeness")),
        hallucinated_clinical_entity_count=_float_value(row.get("hallucinated_clinical_entity_count")),
        critical_info_omission_rate=_float_value(row.get("critical_info_omission_rate")),
        stage_name=row.get("stage_name") or row.get("stage") or None,
        checkpoint=row.get("checkpoint") or row.get("model_name") or None,
        provider_type=row.get("provider_type") or None,
        domain_fit=row.get("domain_fit") or None,
        total_runtime_seconds=_float_value(row.get("total_runtime_seconds")),
        failure_counts=_json_dict(row.get("failure_counts")),
        notes=row.get("notes") or None,
        error_message=row.get("error_message") or None,
    )


def _int_value(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def _float_value(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _json_dict(value: str | None) -> dict[str, int] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    result: dict[str, int] = {}
    for key, count in parsed.items():
        try:
            result[str(key)] = int(count)
        except (TypeError, ValueError):
            continue
    return result
