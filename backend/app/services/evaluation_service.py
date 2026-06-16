from __future__ import annotations

import csv
import json
import os
import subprocess
import time
import uuid
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

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
    SummaryReview,
    SummaryStatus,
)
from ..persistence_schemas import (
    BenchmarkFlowComparisonRecord,
    BenchmarkFlowComparisonResponse,
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
    HumanEvaluationAnalyticsResponse,
    HumanEvaluationExportResponse,
    HumanEvaluationExportRow,
    HumanEvaluationListResponse,
    HumanEvaluationResponse,
    HumanEvaluationRubricDimension,
    HumanEvaluationRubricResponse,
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
RAG_BEST_MODELS_OUTPUT_DIR = Path("D:/clin_summ_outputs/rag_best_models_benchmark")
PREFERRED_RAG_BEST_MODELS_OUTPUT_DIR = Path("D:/clin_summ_outputs/rag_best_models_benchmark_no_gemini_ui")
MEDIUM_BENCHMARK_COMPARISON_PATH = MEDIUM_BENCHMARK_OUTPUT_DIR / "model_comparison.csv"
MEDIUM_BENCHMARK_REPORT_PATH = MEDIUM_BENCHMARK_OUTPUT_DIR / "EVALUATION_REPORT.md"
MEDIUM_BENCHMARK_FAILURE_PATH = MEDIUM_BENCHMARK_OUTPUT_DIR / "failure_analysis.md"
BENCHMARK_DISCOVERY_DIRS = [
    Path("D:/clin_summ_outputs/rag_best_models_benchmark_no_gemini_ui"),
    Path("D:/clin_summ_outputs/rag_best_models_benchmark"),
    Path("D:/clin_summ_outputs/rag_best_models_ollama_50"),
    Path("D:/clin_summ_outputs/rag_best_models_ollama_smoke"),
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
    "qwen2.5": "qwen2.5_predictions.jsonl",
    "llama3.2": "llama3.2_predictions.jsonl",
    "gemini2.5_flash_lite": "gemini2.5_flash_lite_predictions.jsonl",
}
FLOW_COMPARISON_LABELS = {
    "summarization_only": "Flow 1 Raw Summarization",
    "clinical_context": "Flow 1.5 Clinical Context",
    "rag_grounded": "Flow 2 RAG Grounded",
}
BENCHMARK_TYPE_LABELS = FLOW_COMPARISON_LABELS | {"rag_best_models": "Flow 2.1 RAG Best Models"}
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
RUBRIC_VERSION = "clinical_human_eval_rubric_v1"
HUMAN_EVALUATION_RUBRIC = [
    HumanEvaluationRubricDimension(
        key="factual_correctness_score",
        label="Factual correctness",
        description="Clinical statements match the cited/source evidence without introducing unsupported facts.",
        score_1="Major unsupported or incorrect clinical facts.",
        score_3="Mostly correct but contains minor uncertainty or weak evidence linkage.",
        score_5="All important clinical facts are supported and clinically precise.",
    ),
    HumanEvaluationRubricDimension(
        key="completeness_score",
        label="Clinical completeness",
        description="Captures the important diagnosis, medication, timeline, diagnostics, assessment, and plan information.",
        score_1="Misses critical clinical information.",
        score_3="Covers the main point but misses one or more useful details.",
        score_5="Captures all clinically important information needed for review.",
    ),
    HumanEvaluationRubricDimension(
        key="conciseness_score",
        label="Conciseness",
        description="Avoids redundant or irrelevant text while preserving clinically important details.",
        score_1="Too verbose, repetitive, or cluttered.",
        score_3="Usable but could be shorter or better organized.",
        score_5="Concise and clinically focused.",
    ),
    HumanEvaluationRubricDimension(
        key="readability_score",
        label="Readability",
        description="Clear structure, readable wording, and useful sectioning for a clinician.",
        score_1="Hard to read or poorly structured.",
        score_3="Readable with some formatting or wording issues.",
        score_5="Easy to scan, sectioned well, and clinically usable.",
    ),
    HumanEvaluationRubricDimension(
        key="citation_usefulness_score",
        label="Citation usefulness",
        description="Citations make it easy to verify clinical claims and locate supporting source evidence.",
        score_1="Citations missing, wrong, or not helpful.",
        score_3="Some useful citations but incomplete coverage or weak linkage.",
        score_5="Citations are specific, complete, and easy to audit.",
    ),
]
HUMAN_EVALUATION_EXPORT_FIELDS = [
    "evaluation_id",
    "summary_id",
    "patient_id",
    "encounter_id",
    "summary_status",
    "final_locked",
    "model_provider",
    "model_name",
    "evaluator_id",
    "evaluator_name",
    "reviewer_signature",
    "latest_review_action",
    "latest_rejection_reason",
    "factual_correctness_score",
    "completeness_score",
    "conciseness_score",
    "readability_score",
    "citation_usefulness_score",
    "hallucination_risk",
    "comments",
    "citation_coverage",
    "unsupported_claim_count",
    "conflict_count",
    "edit_distance_score",
    "edit_diff_summary",
    "generated_summary_text",
    "final_reviewed_summary_text",
    "created_at",
]
REJECTION_REASON_OPTIONS = [
    "unsupported_claim",
    "wrong_citation",
    "missing_critical_info",
    "incorrect_clinical_fact",
    "conflicting_evidence",
    "poor_readability",
    "too_generic",
    "unsafe_output",
    "other",
]


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
            rag_readiness_gate=self._rag_readiness_gate(),
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
        # Prefer an explicit latest pointer for Flow 2.1 if present and valid.
        selected_dir, discovered = _select_benchmark_output_dir(BENCHMARK_DISCOVERY_DIRS, benchmark_type)
        if benchmark_type == "rag_best_models":
            pointer = Path("D:/clin_summ_outputs/latest_rag_best_models.json")
            if pointer.exists():
                try:
                    payload = json.loads(pointer.read_text(encoding="utf-8"))
                    sel = Path(str(payload.get("selected_output_dir") or ""))
                    if sel.exists() and (sel / "model_comparison.csv").exists():
                        selected_dir = sel
                        # ensure discovered includes the selected dir and mark it selected
                        found = False
                        for item in discovered:
                            if item.get("path") == str(selected_dir):
                                item["selected"] = True
                                found = True
                            else:
                                item["selected"] = False
                        if not found:
                            di = _folder_info(selected_dir)
                            di["selected"] = True
                            discovered.append(di)
                except Exception:
                    # ignore pointer parse errors and fall back to discovery
                    pass
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
        failure_examples = _per_record_failure_examples(selected_dir, limit=120)
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

    def benchmark_flow_comparison(
        self,
        *,
        limit: int = 12,
        provider: str | None = None,
    ) -> BenchmarkFlowComparisonResponse:
        flow_dirs: dict[str, Path] = {}
        flow_metadata: list[dict[str, str | None]] = []
        for flow_key, title in FLOW_COMPARISON_LABELS.items():
            selected_dir, _ = _select_benchmark_output_dir(BENCHMARK_DISCOVERY_DIRS, flow_key)
            flow_dirs[flow_key] = selected_dir
            flow_metadata.append(
                {
                    "key": flow_key,
                    "title": title,
                    "output_dir": str(selected_dir),
                    "benchmark_type": _benchmark_type(selected_dir) if selected_dir.exists() else flow_key,
                }
            )

        indexed = {
            flow_key: _flow_prediction_index(output_dir, provider_filter=provider)
            for flow_key, output_dir in flow_dirs.items()
        }
        common_keys = set.intersection(*(set(index.keys()) for index in indexed.values()))
        records = [
            _flow_comparison_record(note_id, model_provider, indexed)
            for note_id, model_provider in common_keys
        ]
        records = sorted(records, key=_flow_comparison_priority, reverse=True)[:limit]
        return BenchmarkFlowComparisonResponse(
            flows=flow_metadata,
            records=records,
            limit=limit,
            provider_filter=provider,
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

    def human_rubric(self) -> HumanEvaluationRubricResponse:
        return HumanEvaluationRubricResponse(
            rubric_version=RUBRIC_VERSION,
            scoring_scale="1=unsafe/poor, 3=usable with reservations, 5=clinically strong for review",
            dimensions=HUMAN_EVALUATION_RUBRIC,
            hallucination_risk_options=["low", "medium", "high"],
            approve_reject_reason_options=REJECTION_REASON_OPTIONS,
            required_fields=[
                "summary_id",
                "factual_correctness_score",
                "completeness_score",
                "conciseness_score",
                "readability_score",
                "citation_usefulness_score",
                "hallucination_risk",
            ],
            export_fields=HUMAN_EVALUATION_EXPORT_FIELDS,
        )

    def human_analytics(self) -> HumanEvaluationAnalyticsResponse:
        evaluations = self.repository.human_evaluations()
        reviews = self.repository.summary_reviews()
        return _human_analytics(evaluations, reviews)

    def human_export(self, *, include_text: bool = False, limit: int = 500) -> HumanEvaluationExportResponse:
        evaluations = self.repository.human_evaluations()[:limit]
        rows = [_human_export_row(evaluation, include_text=include_text) for evaluation in evaluations]
        return HumanEvaluationExportResponse(
            export_version="human_evaluation_dataset_v1",
            row_count=len(rows),
            include_text=include_text,
            rows=rows,
        )

    def provider_readiness(self) -> list[EvaluationProviderStatus]:
        latest = self.repository.latest_model_run(
            [
                "local",
                "deterministic",
                "bart",
                "pegasus",
                "pegasus_pubmed",
                "pegasus_cnn_dailymail",
                "qwen2.5",
                "llama3.2",
                "gemini2.5_flash_lite",
                "gemini",
            ]
        )
        deterministic = latest.get("local") or latest.get("deterministic")
        bart_enabled = _real_baselines_enabled()
        pegasus_enabled = _real_baselines_enabled()
        qwen_health = _ollama_model_health("qwen2.5:3b")
        llama_health = _ollama_model_health("llama3.2:3b")
        qwen_enabled = bool(qwen_health.get("model_present")) or latest.get("qwen2.5") is not None
        llama_enabled = bool(llama_health.get("model_present")) or latest.get("llama3.2") is not None
        gemini_flash_health = _gemini_key_health(os.environ.get("GEMINI_API_KEY") or self.settings.gemini_api_key)
        gemini_flash_configured = bool(os.environ.get("GEMINI_API_KEY") or self.settings.gemini_api_key)
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
                "qwen2.5",
                configured=qwen_enabled,
                enabled=qwen_enabled and bool(qwen_health.get("ollama_running")),
                model_name=os.environ.get("LLM_GATEWAY_QWEN2_5_MODEL") or "ollama/qwen2.5:3b",
                latest=latest.get("qwen2.5"),
                message=_ollama_health_message("qwen2.5", qwen_health),
                health_checks=qwen_health,
                warmup_latency_ms=_int_or_none(qwen_health.get("warmup_latency_ms")),
            ),
            _provider_status(
                "llama3.2",
                configured=llama_enabled,
                enabled=llama_enabled and bool(llama_health.get("ollama_running")),
                model_name=os.environ.get("LLM_GATEWAY_LLAMA3_2_MODEL") or "ollama/llama3.2:3b",
                latest=latest.get("llama3.2"),
                message=_ollama_health_message("llama3.2", llama_health),
                health_checks=llama_health,
                warmup_latency_ms=_int_or_none(llama_health.get("warmup_latency_ms")),
            ),
            _provider_status(
                "gemini2.5_flash_lite",
                configured=gemini_flash_configured,
                enabled=gemini_flash_configured,
                model_name=os.environ.get("LLM_GATEWAY_GEMINI2_5_FLASH_LITE_MODEL") or "gemini/gemini-2.5-flash-lite",
                latest=latest.get("gemini2.5_flash_lite"),
                message=gemini_flash_health.get("message") or "Cloud gateway model for Flow 2.1.",
                health_checks=gemini_flash_health,
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

    def _rag_readiness_gate(self) -> dict[str, Any]:
        selected_dir, _discovered = _select_benchmark_output_dir(BENCHMARK_DISCOVERY_DIRS, "rag_best_models")
        retrieval_path = selected_dir / "retrieval_metrics.csv"
        comparison_path = selected_dir / "model_comparison.csv"
        if not selected_dir.exists() or not retrieval_path.exists():
            return {
                "status": "not_available",
                "decision": "do_not_replace_doctor_flow",
                "selected_output_dir": str(selected_dir),
                "message": "Run Flow 2.1 RAG benchmark before considering doctor-flow integration.",
                "checks": [],
            }

        retrieval_summary = _rag_retrieval_gate_summary(retrieval_path)
        model_rows = _read_model_comparison(comparison_path)
        completed_models = [
            row.model_provider
            for row in model_rows
            if row.completed_count > 0 and str(row.status).lower() in {"completed", "partial"}
        ]
        target_models = {"qwen2.5", "llama3.2"}
        has_local_llm = bool(target_models.intersection(completed_models))
        weak_count = int(retrieval_summary.get("weak_retrieval_count") or 0)
        record_count = int(retrieval_summary.get("record_count") or 0)
        weak_rate = (weak_count / record_count) if record_count else 1.0
        hard_fail = record_count == 0 or not has_local_llm or weak_rate > 0.25
        caution = not hard_fail and (
            weak_count > 0
            or int(retrieval_summary.get("missing_medication_evidence_count") or 0) > 0
            or float(retrieval_summary.get("average_recall_at_5") or 0.0) < 0.85
        )
        status = "blocked" if hard_fail else "caution" if caution else "ready"
        decision = {
            "ready": "safe_to_pilot_in_admin_only",
            "caution": "review_retrieval_before_doctor_flow",
            "blocked": "do_not_replace_doctor_flow",
        }[status]
        checks = [
            {
                "name": "diagnosis_evidence",
                "status": "passed" if int(retrieval_summary.get("missing_diagnosis_evidence_count") or 0) == 0 else "warning",
                "value": retrieval_summary.get("missing_diagnosis_evidence_count"),
                "message": "Records missing diagnosis facts before summarization.",
            },
            {
                "name": "medication_evidence",
                "status": "passed" if int(retrieval_summary.get("missing_medication_evidence_count") or 0) == 0 else "warning",
                "value": retrieval_summary.get("missing_medication_evidence_count"),
                "message": "Medication may be absent in source, but missing medication evidence is surfaced for review.",
            },
            {
                "name": "timeline_evidence",
                "status": "passed" if int(retrieval_summary.get("missing_timeline_evidence_count") or 0) == 0 else "warning",
                "value": retrieval_summary.get("missing_timeline_evidence_count"),
                "message": "Records missing timeline facts before summarization.",
            },
            {
                "name": "retrieval_quality",
                "status": "passed" if weak_count == 0 else "warning" if weak_rate <= 0.25 else "failed",
                "value": round(weak_rate, 4),
                "message": "Weak retrieval records are flagged as review_retrieval_first.",
            },
            {
                "name": "local_llm_completed",
                "status": "passed" if has_local_llm else "failed",
                "value": sorted(target_models.intersection(completed_models)),
                "message": "At least one local Flow 2.1 model should complete before doctor-flow integration.",
            },
        ]
        return {
            "status": status,
            "decision": decision,
            "selected_output_dir": str(selected_dir),
            "record_count": record_count,
            "completed_models": completed_models,
            "retrieval_summary": retrieval_summary,
            "checks": checks,
            "message": "Keep RAG inside Admin evaluation until this gate is ready and reviewed.",
        }

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
    health_checks: dict[str, Any] | None = None,
    warmup_latency_ms: int | None = None,
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
        health_checks=health_checks or {},
        warmup_latency_ms=warmup_latency_ms,
    )


def _ollama_model_health(model_name: str) -> dict[str, Any]:
    base_url = os.environ.get("OLLAMA_API_BASE", "http://127.0.0.1:11434").rstrip("/")
    result: dict[str, Any] = {
        "ollama_running": False,
        "model_present": False,
        "model_name": model_name,
        "ollama_models_dir": os.environ.get("OLLAMA_MODELS") or None,
        "api_base": base_url,
        "warmup_status": "not_run",
        "warmup_latency_ms": None,
    }
    tags = _ollama_tags(base_url)
    if tags.get("error"):
        result["error"] = tags["error"]
        return result
    result["ollama_running"] = True
    names = set(tags.get("models") or [])
    result["available_models"] = sorted(names)
    result["model_present"] = model_name in names
    if not result["model_present"]:
        return result
    smoke = _ollama_smoke(base_url, model_name)
    result.update(smoke)
    return result


def _ollama_tags(base_url: str) -> dict[str, Any]:
    try:
        payload = _http_json(f"{base_url}/api/tags", timeout=2.0)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    models = [
        str(item.get("name") or "")
        for item in payload.get("models", [])
        if isinstance(item, dict) and item.get("name")
    ]
    return {"models": models}


def _ollama_smoke(base_url: str, model_name: str) -> dict[str, Any]:
    body = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Reply with OK only."},
        ],
        "stream": False,
        "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "10m"),
        "options": {"temperature": 0, "num_predict": 8, "num_ctx": 1024},
    }
    started = time.perf_counter()
    try:
        payload = _http_json(f"{base_url}/api/chat", method="POST", body=body, timeout=12.0)
    except Exception as exc:
        return {
            "warmup_status": "failed",
            "warmup_latency_ms": int((time.perf_counter() - started) * 1000),
            "warmup_error": f"{type(exc).__name__}: {exc}",
        }
    content = ""
    message = payload.get("message")
    if isinstance(message, dict):
        content = str(message.get("content") or "")
    ok = bool(content.strip())
    return {
        "warmup_status": "passed" if ok else "failed",
        "warmup_latency_ms": int((time.perf_counter() - started) * 1000),
        "warmup_response_preview": content.strip()[:80],
    }


def _http_json(url: str, *, method: str = "GET", body: dict[str, Any] | None = None, timeout: float) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urlrequest.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urlerror.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


def _gemini_key_health(api_key: Any) -> dict[str, Any]:
    # Accept str, None, or pydantic SecretStr; extract a plain string value safely
    if api_key is None:
        key = ""
    elif hasattr(api_key, "get_secret_value"):
        try:
            key = (api_key.get_secret_value() or "").strip()
        except Exception:
            key = str(api_key) if api_key is not None else ""
            key = (key or "").strip()
    else:
        key = str(api_key).strip()

    present = bool(key)
    format_valid = present and len(key) >= 20 and key.startswith("AIza")
    return {
        "api_key_present": present,
        "api_key_format_valid": format_valid,
        "cloud_validation": "not_run",
        "message": (
            "Gemini key is present and format looks valid; live cloud validation is not run from Admin refresh."
            if format_valid
            else "Gemini key is missing or does not look like a Google API key."
        ),
    }


def _ollama_health_message(provider: str, health: dict[str, Any]) -> str:
    if not health.get("ollama_running"):
        return f"{provider} requires Ollama running at {health.get('api_base')}."
    if not health.get("model_present"):
        return f"{provider} requires local model {health.get('model_name')} in ollama list."
    if health.get("warmup_status") != "passed":
        return f"{provider} model exists but warmup failed: {health.get('warmup_error') or 'empty response'}."
    return f"{provider} is available through local Ollama; warmup latency {health.get('warmup_latency_ms')} ms."


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rag_retrieval_gate_summary(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {"status": "not_available", "record_count": 0}
    record_count = len(rows)
    missing_diagnosis = 0
    missing_medication = 0
    missing_timeline = 0
    weak_retrieval = 0
    recall_values: list[float] = []
    mrr_values: list[float] = []
    latency_values: list[float] = []
    for row in rows:
        facts = _json_dict_any(row.get("critical_fact_counts"))
        diagnosis_count = int(facts.get("DIAGNOSIS") or 0)
        medication_count = int(facts.get("MEDICATIONS") or 0)
        timeline_count = int(facts.get("TIMELINE") or 0)
        recall = _float_value_any(row.get("recall_at_5")) or 0.0
        mrr = _float_value_any(row.get("mrr")) or 0.0
        context_chunks = _int_value_any(row.get("context_chunk_count"))
        if diagnosis_count == 0:
            missing_diagnosis += 1
        if medication_count == 0:
            missing_medication += 1
        if timeline_count == 0:
            missing_timeline += 1
        if diagnosis_count == 0 or timeline_count == 0 or recall < 0.5 or context_chunks == 0:
            weak_retrieval += 1
        recall_values.append(recall)
        mrr_values.append(mrr)
        latency = _float_value_any(row.get("retrieval_latency_ms"))
        if latency is not None:
            latency_values.append(latency)
    return {
        "status": "available",
        "record_count": record_count,
        "weak_retrieval_count": weak_retrieval,
        "missing_diagnosis_evidence_count": missing_diagnosis,
        "missing_medication_evidence_count": missing_medication,
        "missing_timeline_evidence_count": missing_timeline,
        "average_recall_at_5": _mean(recall_values),
        "average_mrr": _mean(mrr_values),
        "latency_p95_ms": _percentile(latency_values, 95),
    }


def _json_dict_any(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _int_value_any(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


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


def _human_analytics(
    evaluations: list[HumanEvaluation],
    reviews: list[SummaryReview],
) -> HumanEvaluationAnalyticsResponse:
    actions = Counter(str(review.action.value if review.action else "unknown") for review in reviews)
    rejection_reasons = Counter(
        str(review.rejection_reason)
        for review in reviews
        if review.rejection_reason
    )
    reviewer_activity = Counter(_reviewer_label(review) for review in reviews)
    edit_distances = [
        float(review.edit_distance_score)
        for review in reviews
        if review.edit_distance_score is not None
    ]
    locked_summary_ids = {
        str(review.summary_id)
        for review in reviews
        if review.summary is not None and review.summary.status == SummaryStatus.APPROVED
    }
    providers = Counter(item.model_provider or "unknown" for item in evaluations)
    risks = Counter(item.hallucination_risk for item in evaluations)
    return HumanEvaluationAnalyticsResponse(
        total_reviews=len(reviews),
        approvals=actions.get("approve", 0),
        rejections=actions.get("reject", 0),
        edits=actions.get("edit", 0),
        final_locked_approved_summaries=len(locked_summary_ids),
        rejection_reasons_distribution=_metric_items(rejection_reasons),
        reviewer_activity=_metric_items(reviewer_activity),
        average_edit_distance=round(sum(edit_distances) / len(edit_distances), 4) if edit_distances else None,
        human_evaluation_count=len(evaluations),
        human_evaluations_by_provider=_metric_items(providers),
        hallucination_risk_distribution=_metric_items(risks),
    )


def _human_export_row(evaluation: HumanEvaluation, *, include_text: bool) -> HumanEvaluationExportRow:
    summary = evaluation.summary
    if summary is None:  # Defensive; relationship should be present for persisted rows.
        raise ValueError("Human evaluation is missing its linked summary.")
    latest_review = _latest_review(summary.reviews)
    latest_edit = _latest_edit(summary.reviews)
    model_run = summary.model_run
    final_text = latest_edit.edited_summary_text if latest_edit and latest_edit.edited_summary_text else summary.summary_text
    return HumanEvaluationExportRow(
        evaluation_id=evaluation.evaluation_id,
        summary_id=evaluation.summary_id,
        patient_id=summary.patient_id,
        encounter_id=summary.encounter_id,
        summary_status=summary.status.value if summary.status else "unknown",
        final_locked=summary.status == SummaryStatus.APPROVED,
        model_provider=evaluation.model_provider or _provider_label(model_run.provider if model_run else None),
        model_name=model_run.model_name if model_run else None,
        evaluator_id=evaluation.evaluator_id,
        evaluator_name=evaluation.evaluator_name,
        reviewer_signature=_reviewer_signature(latest_review) if latest_review else None,
        latest_review_action=latest_review.action.value if latest_review and latest_review.action else None,
        latest_rejection_reason=latest_review.rejection_reason if latest_review else None,
        factual_correctness_score=evaluation.factual_correctness_score,
        completeness_score=evaluation.completeness_score,
        conciseness_score=evaluation.conciseness_score,
        readability_score=evaluation.readability_score,
        citation_usefulness_score=evaluation.citation_usefulness_score,
        hallucination_risk=evaluation.hallucination_risk,
        comments=evaluation.comments,
        citation_coverage=summary.citation_coverage,
        unsupported_claim_count=summary.unsupported_claim_count,
        conflict_count=summary.conflict_count,
        edit_distance_score=latest_edit.edit_distance_score if latest_edit else None,
        edit_diff_summary=_export_edit_diff_summary(summary.summary_text, latest_edit.edited_summary_text if latest_edit else None),
        generated_summary_text=summary.summary_text if include_text else None,
        final_reviewed_summary_text=final_text if include_text else None,
        created_at=evaluation.created_at,
    )


def _latest_review(reviews: list[SummaryReview]) -> SummaryReview | None:
    if not reviews:
        return None
    return max(reviews, key=lambda item: (item.reviewed_at, item.created_at))


def _latest_edit(reviews: list[SummaryReview]) -> SummaryReview | None:
    edit_reviews = [review for review in reviews if review.edited_summary_text]
    return _latest_review(edit_reviews)


def _reviewer_signature(review: SummaryReview) -> str:
    return f"reviewer:{review.reviewer_id}|signed_at:{review.reviewed_at.isoformat(timespec='seconds')}"


def _export_edit_diff_summary(original: str, edited: str | None) -> dict[str, Any]:
    if not edited:
        return {}
    original_lines = [line for line in (original or "").splitlines() if line.strip()]
    edited_lines = [line for line in edited.splitlines() if line.strip()]
    matcher = SequenceMatcher(None, original_lines, edited_lines)
    counts = Counter(op for op, *_ in matcher.get_opcodes() if op != "equal")
    return {
        "changed_segments": sum(counts.values()),
        "insert_segments": counts.get("insert", 0),
        "delete_segments": counts.get("delete", 0),
        "replace_segments": counts.get("replace", 0),
        "original_lines": len(original_lines),
        "edited_lines": len(edited_lines),
    }


def _reviewer_label(review: SummaryReview) -> str:
    if review.reviewer is None:
        return str(review.reviewer_id)
    return review.reviewer.external_user_id or review.reviewer.full_name or str(review.reviewer_id)


def _metric_items(counter: Counter) -> list[MetricCountItem]:
    return [
        MetricCountItem(key=str(key), count=int(count))
        for key, count in counter.most_common()
    ]


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
    # For rag_best_models, also scan the root output directory for any
    # folders matching the `rag_best_models*` prefix so new runs are
    # discovered automatically without manual copying.
    candidate_paths: list[Path] = list(candidate_dirs)
    if benchmark_type == "rag_best_models":
        root_scan = Path("D:/clin_summ_outputs")
        try:
            for p in sorted(root_scan.glob("rag_best_models*")):
                if p not in candidate_paths:
                    candidate_paths.append(p)
        except Exception:
            # ignore scanning errors and fall back to provided candidates
            pass
    discovered = [_folder_info(path) for path in candidate_paths]
    existing = [item for item in discovered if item["exists"]]
    if benchmark_type:
        existing = [item for item in existing if item["benchmark_type"] == benchmark_type]
    # Special handling for Flow 2.1 (rag_best_models): prefer the
    # pre-defined preferred directory when present and otherwise only
    # consider folders that include a model_comparison.csv. This ensures
    # the dashboard loads `data.models` from a valid `model_comparison.csv`.
    if benchmark_type == "rag_best_models":
        # If the preferred folder exists and contains a comparison CSV, select it.
        preferred = next(
            (item for item in existing if item["path"] == str(PREFERRED_RAG_BEST_MODELS_OUTPUT_DIR) and item.get("has_model_comparison")),
            None,
        )
        if preferred:
            selected = Path(preferred["path"])
            for item in discovered:
                item["selected"] = item["path"] == str(selected)
            return selected, discovered
        # Otherwise prefer any existing folder that contains model_comparison.csv,
        # choosing the most recently modified such folder.
        candidates = [item for item in existing if item.get("has_model_comparison")]
        if candidates:
            ranked = sorted(candidates, key=lambda item: item["last_modified"] or "", reverse=True)
            selected = Path(ranked[0]["path"])
            for item in discovered:
                item["selected"] = item["path"] == str(selected)
            return selected, discovered
    if not existing:
        fallback_by_type = {
            "rag_best_models": RAG_BEST_MODELS_OUTPUT_DIR,
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
    if path.name.startswith("rag_best_models") or _manifest_pipeline(path) == "rag_best_models_benchmark":
        return "rag_best_models"
    if (path / "rag_benchmark_manifest.json").exists() or (path / "retrieval_metrics.csv").exists():
        return "rag_grounded"
    if (path / "clinical_context_manifest.json").exists() or (path / "clinical_context_records.jsonl").exists():
        return "clinical_context"
    return "summarization_only"


def _manifest_pipeline(path: Path) -> str | None:
    manifest_path = path / "rag_benchmark_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return str(payload.get("pipeline") or "") or None


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
    ordered = ["deterministic", "bart", "pegasus", "qwen2.5", "llama3.2", "gemini2.5_flash_lite", "pegasus_pubmed", "pegasus_cnn_dailymail"]
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


def _flow_prediction_index(
    output_dir: Path,
    *,
    provider_filter: str | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for provider, filename in PREDICTION_FILES.items():
        if provider_filter and provider != provider_filter:
            continue
        for raw_row in _read_prediction_jsonl(output_dir / filename):
            enriched = _ensure_clinical_metrics(dict(raw_row))
            note_id = str(enriched.get("note_id") or enriched.get("record_id") or "").strip()
            if not note_id:
                continue
            row_provider = str(enriched.get("model_provider") or provider).strip() or provider
            indexed[(note_id, row_provider)] = _flow_prediction_payload(
                enriched,
                provider=row_provider,
                fallback_model_name=_default_model_name(provider),
            )
    return indexed


def _flow_prediction_payload(
    row: dict[str, Any],
    *,
    provider: str,
    fallback_model_name: str,
) -> dict[str, Any]:
    metrics = {
        field: _float_value_any(row.get(field))
        for field in PER_RECORD_CLINICAL_FIELDS
    }
    return {
        "note_id": str(row.get("note_id") or ""),
        "patient_id": str(row.get("patient_id") or "") or None,
        "encounter_id": str(row.get("encounter_id") or "") or None,
        "dataset": str(row.get("dataset") or "") or None,
        "model_provider": provider,
        "model_name": row.get("model_name") or row.get("checkpoint") or fallback_model_name,
        "status": row.get("status") or "completed",
        "input_note": row.get("source_note") or row.get("input_note") or "",
        "reference_summary": row.get("reference_summary") or "",
        "generated_summary": row.get("generated_summary") or "",
        "retrieved_evidence": row.get("retrieved_evidence") or row.get("evidence") or "",
        "citations": row.get("citations") or [],
        "failure_labels": _split_failure_categories(row.get("failure_categories") or row.get("failure_labels")),
        "rouge1": _float_value_any(row.get("rouge1")),
        "rouge2": _float_value_any(row.get("rouge2")),
        "rougeL": _float_value_any(row.get("rougeL")),
        "latency_ms": _float_value_any(row.get("latency_ms")),
        "clinical_metrics": metrics,
        "error_message": row.get("error_message"),
    }


def _flow_comparison_record(
    note_id: str,
    model_provider: str,
    indexed: dict[str, dict[tuple[str, str], dict[str, Any]]],
) -> BenchmarkFlowComparisonRecord:
    flows = {
        flow_key: indexed[flow_key][(note_id, model_provider)]
        for flow_key in FLOW_COMPARISON_LABELS
    }
    raw = flows["summarization_only"]
    rag = flows["rag_grounded"]
    highlights, verdict, deltas = _flow_comparison_highlights(raw, rag)
    representative = next((cell for cell in flows.values() if cell.get("input_note")), raw)
    return BenchmarkFlowComparisonRecord(
        note_id=note_id,
        patient_id=representative.get("patient_id"),
        encounter_id=representative.get("encounter_id"),
        dataset=representative.get("dataset"),
        model_provider=model_provider,
        input_note=representative.get("input_note"),
        reference_summary=representative.get("reference_summary"),
        flows=flows,
        highlights=highlights,
        verdict=verdict,
        rag_delta=deltas,
    )


def _flow_comparison_highlights(
    raw: dict[str, Any],
    rag: dict[str, Any],
) -> tuple[list[str], str, dict[str, float | None]]:
    raw_metrics = raw.get("clinical_metrics") or {}
    rag_metrics = rag.get("clinical_metrics") or {}
    deltas = {
        "missing_diagnosis_rate": _metric_delta(raw_metrics, rag_metrics, "missing_diagnosis_rate", lower_is_better=True),
        "missing_medication_rate": _metric_delta(raw_metrics, rag_metrics, "missing_medication_rate", lower_is_better=True),
        "timeline_completeness": _metric_delta(raw_metrics, rag_metrics, "timeline_completeness", lower_is_better=False),
        "unsupported_claim_rate": _metric_delta(raw_metrics, rag_metrics, "unsupported_claim_rate", lower_is_better=True),
        "citation_coverage": _metric_delta(raw_metrics, rag_metrics, "citation_coverage", lower_is_better=False),
    }
    raw_labels = set(raw.get("failure_labels") or [])
    rag_labels = set(rag.get("failure_labels") or [])
    highlights: list[str] = []
    helped = False
    worse = False

    for field, label in (
        ("missing_diagnosis_rate", "RAG reduced missing diagnosis"),
        ("missing_medication_rate", "RAG reduced missing medication"),
    ):
        if _meaningful_positive(deltas[field]) or field.replace("_rate", "").replace("_", " ") in raw_labels - rag_labels:
            helped = True
            highlights.append(label)

    if _meaningful_positive(deltas["timeline_completeness"]) or "missing timeline" in raw_labels - rag_labels:
        helped = True
        highlights.append("RAG improved timeline completeness")

    if _meaningful_positive(deltas["citation_coverage"]):
        helped = True
        highlights.append("RAG improved citation coverage")

    if _meaningful_negative(deltas["unsupported_claim_rate"]):
        worse = True
        highlights.append("RAG increased unsupported claim rate")

    if (
        _meaningful_negative(deltas["missing_diagnosis_rate"])
        or _meaningful_negative(deltas["missing_medication_rate"])
        or _meaningful_negative(deltas["timeline_completeness"])
    ):
        worse = True
        highlights.append("RAG worsened a clinical completeness metric")

    if "retrieval-related failure" in rag_labels:
        worse = True
        highlights.append("RAG retrieved weak or mismatched evidence")

    if not highlights:
        highlights.append("No major RAG delta detected")

    if helped and not worse:
        verdict = "rag_helped"
    elif worse:
        verdict = "rag_needs_review"
    else:
        verdict = "mixed_or_neutral"
    return highlights, verdict, deltas


def _metric_delta(
    raw_metrics: dict[str, Any],
    rag_metrics: dict[str, Any],
    key: str,
    *,
    lower_is_better: bool,
) -> float | None:
    raw_value = _float_value_any(raw_metrics.get(key))
    rag_value = _float_value_any(rag_metrics.get(key))
    if raw_value is None or rag_value is None:
        return None
    return round(raw_value - rag_value, 4) if lower_is_better else round(rag_value - raw_value, 4)


def _meaningful_positive(value: float | None) -> bool:
    return value is not None and value >= 0.05


def _meaningful_negative(value: float | None) -> bool:
    return value is not None and value <= -0.05


def _flow_comparison_priority(record: BenchmarkFlowComparisonRecord) -> float:
    verdict_weight = {
        "rag_helped": 3.0,
        "rag_needs_review": 2.5,
        "mixed_or_neutral": 1.0,
    }.get(record.verdict, 0.0)
    delta_weight = sum(abs(value) for value in record.rag_delta.values() if value is not None)
    label_weight = sum(len(cell.get("failure_labels") or []) for cell in record.flows.values()) * 0.1
    return verdict_weight + delta_weight + label_weight


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
        if rows and any(isinstance(row.get("model_outputs"), list) for row in rows):
            return _normalized_grouped_failure_examples(rows, limit=limit)
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


def _normalized_grouped_failure_examples(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for row in rows:
        note_id = str(row.get("note_id") or "").strip()
        if not note_id:
            continue
        model_outputs = [_normalized_model_output(output) for output in row.get("model_outputs") or []]
        record_labels = set(_split_failure_categories(row.get("failure_labels") or row.get("failure_categories")))
        for output in model_outputs:
            record_labels.update(output.get("failure_labels") or [])
        severity = len(record_labels)
        for output in model_outputs:
            rouge_l = _float_value_any(output.get("rougeL"))
            metrics = output.get("clinical_metrics") or {}
            severity += 1.0 - rouge_l if rouge_l is not None else 0.5
            severity += _float_value_any(metrics.get("unsupported_claim_rate")) or 0.0
            severity += _float_value_any(metrics.get("critical_info_omission_rate")) or 0.0
        clean_record_labels = _clean_failure_labels(record_labels)
        examples.append(
            {
                "note_id": note_id,
                "patient_id": row.get("patient_id") or "",
                "encounter_id": row.get("encounter_id") or "",
                "dataset": row.get("dataset") or "",
                "input_note": row.get("input_note") or row.get("source_note") or "",
                "reference_summary": row.get("reference_summary") or "",
                "retrieved_evidence": row.get("retrieved_evidence") or "",
                "citations": row.get("citations") or [],
                "failure_labels": clean_record_labels,
                "model_outputs": sorted(model_outputs, key=lambda output: _provider_sort_key(output.get("model_provider"))),
                "severity": round(severity, 4),
            }
        )
    return sorted(examples, key=lambda item: item["severity"], reverse=True)[:limit]


def _normalized_model_output(output: dict[str, Any]) -> dict[str, Any]:
    metrics = output.get("clinical_metrics") or {
        field: output.get(field)
        for field in PER_RECORD_CLINICAL_FIELDS
    }
    labels = _split_failure_categories(output.get("failure_labels") or output.get("failure_categories"))
    if not labels:
        labels = _failure_labels_from_output_metrics(metrics)
    return {
        "model_provider": output.get("model_provider") or "",
        "model_name": output.get("model_name") or "",
        "status": output.get("status") or "",
        "generated_summary": output.get("generated_summary") or "",
        "rouge1": output.get("rouge1"),
        "rouge2": output.get("rouge2"),
        "rougeL": output.get("rougeL"),
        "latency_ms": output.get("latency_ms"),
        "clinical_metrics": metrics,
        "failure_labels": labels,
        "error_message": output.get("error_message"),
    }


def _failure_labels_from_output_metrics(metrics: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    if (_float_value_any(metrics.get("unsupported_claim_rate")) or 0.0) > 0.0:
        labels.append("hallucinated content")
    if (_float_value_any(metrics.get("missing_diagnosis_rate")) or 0.0) > 0.0:
        labels.append("missing diagnosis")
    if (_float_value_any(metrics.get("missing_medication_rate")) or 0.0) > 0.0:
        labels.append("missing medication")
    timeline = _float_value_any(metrics.get("timeline_completeness"))
    if timeline is not None and timeline < 1.0:
        labels.append("missing timeline")
    if (_float_value_any(metrics.get("critical_info_omission_rate")) or 0.0) > 0.0:
        labels.append("incomplete summary")
    if not labels:
        labels.append("no major proxy failure detected")
    return _clean_failure_labels(labels)


def _clean_failure_labels(labels: Any) -> list[str]:
    clean = sorted(set(_split_failure_categories(labels)))
    if len(clean) > 1:
        clean = [label for label in clean if label != "no major proxy failure detected"]
    return clean


def _provider_sort_key(provider: str | None) -> int:
    order = {
        "deterministic": 0,
        "bart": 1,
        "pegasus": 2,
        "qwen2.5": 3,
        "llama3.2": 4,
        "gemini2.5_flash_lite": 5,
        "pegasus_pubmed": 6,
        "pegasus_cnn_dailymail": 7,
    }
    return order.get(provider or "", 99)


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
    if isinstance(value, (list, set, tuple)):
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
        "pegasus": "google/pegasus-cnn_dailymail",
        "qwen2.5": "ollama/qwen2.5:3b",
        "llama3.2": "ollama/llama3.2:3b",
        "gemini2.5_flash_lite": "gemini/gemini-2.5-flash-lite",
        "pegasus_pubmed": "google/pegasus-pubmed",
        "pegasus_cnn_dailymail": "google/pegasus-cnn_dailymail",
        "gemini": "gemini configured provider",
    }.get(provider, provider)


def _domain_fit(provider: str) -> str:
    return {
        "deterministic": "Fast extractive baseline",
        "bart": "General summarization baseline",
        "pegasus": "General Pegasus baseline",
        "qwen2.5": "Local Ollama instruction model",
        "llama3.2": "Local Ollama instruction model",
        "gemini2.5_flash_lite": "Cloud Gemini gateway model",
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
