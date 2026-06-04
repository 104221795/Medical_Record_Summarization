from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics
from evaluation.data_governance.layers import (
    HONESTY_WARNING,
    configure_d_drive_environment,
    run_governance_preflight,
    write_failure_analysis,
    write_human_review_template,
)
from scripts.run_provider_evaluation import GeminiEvaluationSummarizer
from src.data.dataset_loader import load_jsonl_dataset
from src.models import BartSummarizer, BaseSummarizer, DeterministicSummarizer, PegasusSummarizer


DEFAULT_OUTPUT_DIR = Path(os.environ.get("CLIN_SUMM_OUTPUT_DIR", "D:/clin_summ_outputs"))
PROXY_WARNING = "Proxy evaluation only. Do not claim real EHR benchmark or clinical performance from these outputs."
LEGACY_PROXY_WARNING = (
    "Proxy evaluation only: use de-identified/demo/open benchmark data. "
    "Do not claim real EHR benchmark or clinical performance from these outputs."
)


class FullEvaluationPipelineError(ValueError):
    pass


@dataclass(frozen=True)
class PipelineConfig:
    input_path: Path
    dataset: str = "multiclinsum"
    models: tuple[str, ...] = ("deterministic", "bart", "pegasus")
    limit: int | None = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    allow_model_downloads: bool = False
    include_bertscore: bool = False
    device: int = -1
    dry_run: bool = False
    fail_fast: bool = False
    allow_gemini: bool = False
    bart_model_name: str = "facebook/bart-large-cnn"
    pegasus_model_name: str = "google/pegasus-xsum"
    gemini_model_name: str = "gemini-2.5-flash-lite"


@dataclass(frozen=True)
class ProviderPlan:
    name: str
    model_name: str
    summarizer: BaseSummarizer | None = None
    skipped_reason: str | None = None

    @property
    def enabled(self) -> bool:
        return self.summarizer is not None and self.skipped_reason is None


def run_full_evaluation_pipeline(config: PipelineConfig) -> dict[str, Any]:
    cache_paths = configure_d_drive_environment()
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    log_path.write_text("", encoding="utf-8")

    _log(log_path, "Starting full evaluation pipeline.")
    _log(log_path, f"Input path: {config.input_path}")
    _log(log_path, f"Dataset: {config.dataset}")
    _log(log_path, f"Models: {', '.join(config.models)}")
    _log(log_path, f"Dry run: {config.dry_run}")

    records = _load_records(config)
    readiness = _dataset_readiness(config, records)
    _log(log_path, f"Dataset readiness: {readiness['status']} ({readiness['record_count']} records).")
    _log(log_path, f"HF_HOME: {cache_paths['HF_HOME']}")
    _log(log_path, f"HF_HUB_CACHE: {cache_paths['HF_HUB_CACHE']}")
    _log(log_path, f"HF_DATASETS_CACHE: {cache_paths['HF_DATASETS_CACHE']}")
    _log(log_path, f"TRANSFORMERS_CACHE: {cache_paths['TRANSFORMERS_CACHE']}")

    governance = run_governance_preflight(
        records,
        dataset=config.dataset,
        input_path=config.input_path,
        output_dir=output_dir,
        requested_models=config.models,
        cache_paths=cache_paths,
    )
    _write_json(output_dir / "model_manifest.json", governance.model_manifest)
    _log(
        log_path,
        "Data routing: "
        f"benchmark={len(governance.benchmark_records)}, "
        f"warning={len(governance.warning_records)}, "
        f"rejected={len(governance.rejected_records)}.",
    )
    if not governance.benchmark_records:
        raise FullEvaluationPipelineError(
            "No records qualified for benchmark evaluation after data routing. "
            "Inspect data_governance/quality_report.md and rejected_manifest.jsonl."
        )

    provider_plans = [_build_provider_plan(model, config) for model in config.models]
    all_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    for provider in provider_plans:
        _log(log_path, f"Running provider: {provider.name}")
        rows = _run_provider(governance.benchmark_records, provider, config=config, log_path=log_path)
        all_rows.extend(rows)
        metrics = _comparison_row(provider, rows, config=config)
        comparison_rows.append(metrics)
        _write_jsonl(output_dir / f"{provider.name}_predictions.jsonl", rows)
        _log(log_path, f"Provider {provider.name} finished with status: {metrics['status']}")

    _write_jsonl(output_dir / "all_predictions.jsonl", all_rows)
    _write_comparison_csv(output_dir / "model_comparison.csv", comparison_rows)
    _write_per_record_metrics_csv(output_dir / "per_record_metrics.csv", all_rows)
    quality_by_note = {
        record.get("note_id", ""): record.get("quality_route", "")
        for record in governance.benchmark_records + governance.warning_records + governance.rejected_records
    }
    write_human_review_template(all_rows, output_dir)
    write_failure_analysis(all_rows, output_dir=output_dir, quality_by_note=quality_by_note)
    manifest = _manifest(config, readiness, comparison_rows, governance=governance, cache_paths=cache_paths)
    _write_json(output_dir / "evaluation_run_manifest.json", manifest)
    _write_json(output_dir / "run_manifest.json", manifest)
    _write_markdown_report(output_dir / "EVALUATION_REPORT.md", config, readiness, comparison_rows, governance=governance)
    _log(log_path, f"Outputs written to {output_dir}")
    _log(log_path, PROXY_WARNING)

    return {
        "output_dir": str(output_dir),
        "manifest": manifest,
        "comparison_rows": comparison_rows,
        "prediction_rows": all_rows,
    }


def _load_records(config: PipelineConfig) -> list[dict[str, str]]:
    if not config.input_path.exists():
        raise FullEvaluationPipelineError(f"Evaluation input file does not exist: {config.input_path}")
    records = load_jsonl_dataset(
        config.input_path,
        dataset=config.dataset,
        split="test",
        require_reference=True,
        max_records=config.limit,
    )
    if not records:
        raise FullEvaluationPipelineError(f"Evaluation input contains no usable records: {config.input_path}")
    return records


def _dataset_readiness(config: PipelineConfig, records: list[dict[str, str]]) -> dict[str, Any]:
    source_count = sum(1 for record in records if record.get("source_note"))
    reference_count = sum(1 for record in records if record.get("reference_summary"))
    warning_count = sum(1 for record in records if record.get("deidentification_warnings"))
    return {
        "status": "ready" if source_count == len(records) and reference_count == len(records) else "not_ready",
        "input_path": str(config.input_path),
        "dataset": config.dataset,
        "record_count": len(records),
        "source_note_count": source_count,
        "reference_summary_count": reference_count,
        "deidentification_warning_count": warning_count,
        "proxy_warning": PROXY_WARNING,
    }


def _build_provider_plan(model: str, config: PipelineConfig) -> ProviderPlan:
    name = _normalize_model_name(model)
    if config.dry_run:
        return _dry_run_provider_plan(name, config)
    if name == "deterministic":
        summarizer = DeterministicSummarizer(max_sentences=3)
        return ProviderPlan(name=name, model_name=summarizer.model_name, summarizer=summarizer)
    if name == "bart":
        if not _real_baselines_enabled(config):
            return ProviderPlan(name=name, model_name=config.bart_model_name, skipped_reason=_model_downloads_message("BART"))
        return ProviderPlan(
            name=name,
            model_name=config.bart_model_name,
            summarizer=BartSummarizer(model_name=config.bart_model_name, device=config.device),
        )
    if name == "pegasus":
        if not _real_baselines_enabled(config):
            return ProviderPlan(
                name=name,
                model_name=config.pegasus_model_name,
                skipped_reason=_model_downloads_message("Pegasus"),
            )
        return ProviderPlan(
            name=name,
            model_name=config.pegasus_model_name,
            summarizer=PegasusSummarizer(model_name=config.pegasus_model_name, device=config.device),
        )
    if name == "gemini":
        return _gemini_provider_plan(config)
    raise FullEvaluationPipelineError(
        f"Unsupported model '{model}'. Supported models: deterministic,bart,pegasus,gemini."
    )


def _dry_run_provider_plan(name: str, config: PipelineConfig) -> ProviderPlan:
    if name == "deterministic":
        return ProviderPlan(name=name, model_name="deterministic_sentence_baseline")
    if name == "bart":
        reason = None if _real_baselines_enabled(config) else _model_downloads_message("BART")
        return ProviderPlan(name=name, model_name=config.bart_model_name, skipped_reason=reason)
    if name == "pegasus":
        reason = None if _real_baselines_enabled(config) else _model_downloads_message("Pegasus")
        return ProviderPlan(name=name, model_name=config.pegasus_model_name, skipped_reason=reason)
    if name == "gemini":
        plan = _gemini_provider_plan(config)
        return ProviderPlan(name=name, model_name=plan.model_name, skipped_reason=plan.skipped_reason)
    raise FullEvaluationPipelineError(
        f"Unsupported model '{name}'. Supported models: deterministic,bart,pegasus,gemini."
    )


def _real_baselines_enabled(config: PipelineConfig) -> bool:
    return config.allow_model_downloads or os.environ.get("RUN_REAL_BASELINES") == "1"


def _model_downloads_message(model_name: str) -> str:
    return (
        f"{model_name} execution is disabled by default. Pass --allow-model-downloads "
        "or set RUN_REAL_BASELINES=1 to load Hugging Face models."
    )


def _gemini_provider_plan(config: PipelineConfig) -> ProviderPlan:
    api_key = os.environ.get("RAG_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    explicitly_allowed = config.allow_gemini or os.environ.get("RUN_GEMINI_EVALUATION") == "1"
    governance_enabled = (
        os.environ.get("RAG_LLM_PROVIDER") == "gemini"
        and os.environ.get("RAG_LLM_EXTERNAL_ENABLED", "").lower() == "true"
        and os.environ.get("RAG_LLM_ALLOW_PHI_EXTERNAL", "").lower() == "true"
    )
    if not explicitly_allowed or not governance_enabled or not api_key:
        return ProviderPlan(
            name="gemini",
            model_name=config.gemini_model_name,
            skipped_reason=(
                "Gemini evaluation is disabled. It requires --allow-gemini or "
                "RUN_GEMINI_EVALUATION=1, RAG_LLM_PROVIDER=gemini, "
                "RAG_LLM_EXTERNAL_ENABLED=true, RAG_LLM_ALLOW_PHI_EXTERNAL=true, "
                "and RAG_GEMINI_API_KEY."
            ),
        )
    return ProviderPlan(
        name="gemini",
        model_name=config.gemini_model_name,
        summarizer=GeminiEvaluationSummarizer(api_key=api_key, model_name=config.gemini_model_name),
    )


def _run_provider(
    records: list[dict[str, str]],
    provider: ProviderPlan,
    *,
    config: PipelineConfig,
    log_path: Path,
) -> list[dict[str, Any]]:
    if config.dry_run:
        return [_dry_run_row(record, provider, config=config) for record in records]
    if provider.skipped_reason:
        return [_skipped_row(record, provider, reason=provider.skipped_reason, config=config) for record in records]
    if provider.summarizer is None:
        return [_skipped_row(record, provider, reason="Provider is not enabled.", config=config) for record in records]

    rows: list[dict[str, Any]] = []
    for record in records:
        try:
            output = provider.summarizer.generate(record)
            rows.append(_completed_row(record, provider, output, config=config))
        except Exception as exc:
            message = f"{provider.name} failed for note_id={record.get('note_id', '')}: {exc}"
            _log(log_path, message)
            if config.fail_fast:
                raise
            rows.append(_failed_row(record, provider, error_message=str(exc), config=config))
    return rows


def _base_row(record: dict[str, str], provider: ProviderPlan, *, config: PipelineConfig) -> dict[str, Any]:
    return {
        "evaluation_type": "full_layered_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "legacy_proxy_warning": LEGACY_PROXY_WARNING,
        "dataset": record.get("dataset", config.dataset),
        "dataset_requested": config.dataset,
        "evaluation_layer": _evaluation_layer(config.dataset),
        "split": record.get("split", ""),
        "input_path": str(config.input_path),
        "note_id": record.get("note_id", ""),
        "patient_id": record.get("patient_id", ""),
        "encounter_id": record.get("encounter_id", ""),
        "model_provider": provider.name,
        "model_name": provider.model_name,
        "source_note": record.get("source_note", ""),
        "reference_summary": record.get("reference_summary", ""),
        "deidentification_warnings": record.get("deidentification_warnings", ""),
    }


def _completed_row(
    record: dict[str, str],
    provider: ProviderPlan,
    output: Any,
    *,
    config: PipelineConfig,
) -> dict[str, Any]:
    pair_metrics = compute_pairwise_metrics(
        [output.generated_summary],
        [output.reference_summary],
        include_bertscore=False,
    )
    return {
        **_base_row(record, provider, config=config),
        "status": "completed",
        "error_message": None,
        "generated_summary": output.generated_summary,
        "latency_ms": output.latency_ms,
        "rouge1": pair_metrics.get("rouge1"),
        "rouge2": pair_metrics.get("rouge2"),
        "rougeL": pair_metrics.get("rougeL"),
        "dry_run": False,
    }


def _failed_row(
    record: dict[str, str],
    provider: ProviderPlan,
    *,
    error_message: str,
    config: PipelineConfig,
) -> dict[str, Any]:
    return {
        **_base_row(record, provider, config=config),
        "status": "failed",
        "error_message": error_message,
        "generated_summary": "",
        "latency_ms": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
        "dry_run": False,
    }


def _skipped_row(
    record: dict[str, str],
    provider: ProviderPlan,
    *,
    reason: str,
    config: PipelineConfig,
) -> dict[str, Any]:
    return {
        **_base_row(record, provider, config=config),
        "status": "skipped",
        "error_message": reason,
        "generated_summary": "",
        "latency_ms": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
        "dry_run": False,
    }


def _dry_run_row(record: dict[str, str], provider: ProviderPlan, *, config: PipelineConfig) -> dict[str, Any]:
    if provider.skipped_reason:
        status = "skipped"
        message = provider.skipped_reason
    else:
        status = "ready"
        message = "Dry run only. Dataset and provider configuration were checked; no generation was executed."
    return {
        **_base_row(record, provider, config=config),
        "status": status,
        "error_message": message,
        "generated_summary": "",
        "latency_ms": 0,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
        "dry_run": True,
    }


def _comparison_row(provider: ProviderPlan, rows: list[dict[str, Any]], *, config: PipelineConfig) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    failed = [row for row in rows if row["status"] == "failed"]
    skipped = [row for row in rows if row["status"] == "skipped"]
    ready = [row for row in rows if row["status"] == "ready"]
    predictions = [row["generated_summary"] for row in completed]
    references = [row["reference_summary"] for row in completed]
    metrics = (
        compute_pairwise_metrics(predictions, references, include_bertscore=config.include_bertscore)
        if completed
        else {}
    )
    status = _aggregate_status(completed=completed, failed=failed, skipped=skipped, ready=ready)
    return {
        "model_provider": provider.name,
        "model_name": provider.model_name,
        "status": status,
        "dataset": config.dataset,
        "evaluation_layer": _evaluation_layer(config.dataset),
        "record_count": len(rows),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "ready_count": len(ready),
        "rouge1": metrics.get("rouge1"),
        "rouge2": metrics.get("rouge2"),
        "rougeL": metrics.get("rougeL"),
        "rouge1_ci_low": _ci95([row["rouge1"] for row in completed])[0],
        "rouge1_ci_high": _ci95([row["rouge1"] for row in completed])[1],
        "rouge2_ci_low": _ci95([row["rouge2"] for row in completed])[0],
        "rouge2_ci_high": _ci95([row["rouge2"] for row in completed])[1],
        "rougeL_ci_low": _ci95([row["rougeL"] for row in completed])[0],
        "rougeL_ci_high": _ci95([row["rougeL"] for row in completed])[1],
        "bertscore_precision": metrics.get("bertscore_precision"),
        "bertscore_recall": metrics.get("bertscore_recall"),
        "bertscore_f1": metrics.get("bertscore_f1"),
        "bertscore_status": metrics.get("bertscore_status", "not_requested" if not config.include_bertscore else "not_available"),
        "bertscore_message": metrics.get("bertscore_message", ""),
        "average_latency_ms": _mean([row["latency_ms"] for row in completed]),
        "average_input_length": _mean([len(row["source_note"].split()) for row in rows]),
        "average_output_length": _mean([len(row["generated_summary"].split()) for row in completed]),
        "proxy_warning": PROXY_WARNING,
        "notes": _provider_notes(provider, failed=failed, skipped=skipped, ready=ready),
    }


def _aggregate_status(
    *,
    completed: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    ready: list[dict[str, Any]],
) -> str:
    if completed and not failed and not skipped:
        return "completed"
    if ready and not completed and not failed and not skipped:
        return "ready"
    if skipped and not completed and not failed:
        return "skipped"
    if failed and not completed:
        return "failed"
    if completed and (failed or skipped):
        return "partial"
    return "not_available"


def _provider_notes(
    provider: ProviderPlan,
    *,
    failed: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    ready: list[dict[str, Any]],
) -> str:
    if provider.skipped_reason:
        return provider.skipped_reason
    if failed:
        return "; ".join(sorted({str(row["error_message"]) for row in failed if row["error_message"]}))
    if ready:
        return "Dry run only. No generation was executed."
    return PROXY_WARNING


def _manifest(
    config: PipelineConfig,
    readiness: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    *,
    governance: Any,
    cache_paths: dict[str, str],
) -> dict[str, Any]:
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pipeline": "full_layered_evaluation",
        "proxy_warning": PROXY_WARNING,
        "honesty_warning": HONESTY_WARNING,
        "legacy_proxy_warning": LEGACY_PROXY_WARNING,
        "config": {
            "input_path": str(config.input_path),
            "dataset": config.dataset,
            "models": list(config.models),
            "limit": config.limit,
            "output_dir": str(config.output_dir),
            "allow_model_downloads": config.allow_model_downloads,
            "include_bertscore": config.include_bertscore,
            "device": config.device,
            "dry_run": config.dry_run,
            "fail_fast": config.fail_fast,
            "allow_gemini": config.allow_gemini,
        },
        "dataset_readiness": readiness,
        "dataset_manifest": governance.dataset_manifest,
        "dataset_profile_ref": "dataset_profile.json",
        "quality_metrics_ref": "quality_metrics.json",
        "retrieval_metrics_ref": "retrieval_metrics.json",
        "chunking_manifest_ref": "data_governance/chunking_manifest.json",
        "cache_location": cache_paths,
        "model_comparison": comparison_rows,
        "outputs": {
            "manifest": "evaluation_run_manifest.json",
            "run_manifest": "run_manifest.json",
            "comparison_csv": "model_comparison.csv",
            "per_record_metrics_csv": "per_record_metrics.csv",
            "all_predictions": "all_predictions.jsonl",
            "report": "EVALUATION_REPORT.md",
            "log": "run.log",
            "dataset_profile": "dataset_profile.json",
            "quality_metrics": "quality_metrics.json",
            "retrieval_metrics": "retrieval_metrics.json",
            "model_manifest": "model_manifest.json",
            "failure_analysis": "failure_analysis.md",
            "human_review_template": "human_review_template.csv",
            "per_model_predictions": [f"{model}_predictions.jsonl" for model in config.models],
        },
    }
    manifest.update(governance.run_manifest_base)
    manifest["metrics"] = comparison_rows
    return manifest


def _write_markdown_report(
    path: Path,
    config: PipelineConfig,
    readiness: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    *,
    governance: Any,
) -> None:
    lines = [
        "# Full Layered Evaluation Report",
        "",
        f"> {PROXY_WARNING}",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Dataset Clarification",
        "",
        "- Mock/de-identified data is used for functional validation.",
        "- MultiClinSum/MTS-Dialog/MEDIQA-Sum are proxy/open benchmark datasets.",
        "- Real EHR benchmark evaluation with MIMIC-IV-Note or MIMIC-IV-BHC is pending credentialed access and governance approval.",
        "- Medical record summarization datasets are limited because real clinical notes are sensitive and access-controlled.",
        "",
        "## Run Configuration",
        "",
        f"- Dataset: `{config.dataset}`",
        f"- Evaluation layer: `{_evaluation_layer(config.dataset)}`",
        f"- Input: `{config.input_path}`",
        f"- Output directory: `{config.output_dir}`",
        f"- Models: `{', '.join(config.models)}`",
        f"- Limit: `{config.limit if config.limit is not None else 'all'}`",
        f"- Dry run: `{config.dry_run}`",
        f"- Include BERTScore: `{config.include_bertscore}`",
        f"- Allow model downloads: `{config.allow_model_downloads}`",
        f"- HF cache: `{os.environ.get('HF_HOME', '')}`",
        "",
        "## Dataset Readiness",
        "",
        f"- Status: `{readiness['status']}`",
        f"- Records loaded: `{readiness['record_count']}`",
        f"- Source note count: `{readiness['source_note_count']}`",
        f"- Reference summary count: `{readiness['reference_summary_count']}`",
        f"- De-identification warning count: `{readiness['deidentification_warning_count']}`",
        f"- Dataset manifest: `data_governance/dataset_manifest.json`",
        f"- Dataset version: `{governance.dataset_manifest.get('dataset_version')}`",
        "",
        "## Data Governance And Routing",
        "",
        f"- Benchmark records: `{len(governance.benchmark_records)}`",
        f"- Warning records: `{len(governance.warning_records)}`",
        f"- Rejected records: `{len(governance.rejected_records)}`",
        f"- Average quality score: `{governance.quality_metrics.get('average_quality_score')}`",
        f"- Missing rate: `{governance.quality_metrics.get('missing_rate')}`",
        f"- Duplicate rate: `{governance.quality_metrics.get('duplicate_rate')}`",
        f"- Noise rate: `{governance.quality_metrics.get('noise_rate')}`",
        "",
        "Rejected records are not evaluated. Warning records are kept out of the main benchmark set unless explicitly promoted after review.",
        "",
        "## Chunking And Retrieval Preflight",
        "",
        f"- Chunk count: `{governance.chunking_manifest.get('chunk_count')}`",
        f"- Average chunk length: `{governance.chunking_manifest.get('average_chunk_length')}`",
        f"- Context fragmentation: `{governance.chunking_manifest.get('context_fragmentation')}`",
        f"- Retrieval validation type: `{governance.retrieval_metrics.get('validation_type')}`",
        "",
        "## Model Comparison",
        "",
        "| Model | Status | Completed | Ready | Skipped | Failed | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore F1 | Avg latency ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in comparison_rows:
        lines.append(
            "| {model} | {status} | {completed} | {ready} | {skipped} | {failed} | {rouge1} | {rouge2} | {rougeL} | {bertscore} | {latency} |".format(
                model=row["model_provider"],
                status=row["status"],
                completed=row["completed_count"],
                ready=row["ready_count"],
                skipped=row["skipped_count"],
                failed=row["failed_count"],
                rouge1=_display(row["rouge1"]),
                rouge2=_display(row["rouge2"]),
                rougeL=_display(row["rougeL"]),
                bertscore=_display(row["bertscore_f1"]),
                latency=_display(row["average_latency_ms"]),
            )
        )
    lines.extend(
        [
            "",
            "## Provider Notes",
            "",
        ]
    )
    for row in comparison_rows:
        lines.append(f"- `{row['model_provider']}`: {row['notes']}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "These outputs validate a reproducible evaluation pipeline on mock/de-identified or open proxy data. They do not validate clinical deployment readiness, real EHR benchmark performance, or autonomous medical decision-making.",
            "",
            "BART and Pegasus real generation is disabled by default. Gemini is optional and requires explicit opt-in plus governance environment flags.",
            "",
            "## Output Files",
            "",
            "- `evaluation_run_manifest.json`",
            "- `run_manifest.json`",
            "- `dataset_profile.json`",
            "- `quality_metrics.json`",
            "- `retrieval_metrics.json`",
            "- `model_comparison.csv`",
            "- `per_record_metrics.csv`",
            "- `all_predictions.jsonl`",
            "- `<model>_predictions.jsonl`",
            "- `human_review_template.csv`",
            "- `failure_analysis.md`",
            "- `EVALUATION_REPORT.md`",
            "- `run.log`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "model_provider",
        "model_name",
        "status",
        "dataset",
        "evaluation_layer",
        "record_count",
        "completed_count",
        "failed_count",
        "skipped_count",
        "ready_count",
        "rouge1",
        "rouge1_ci_low",
        "rouge1_ci_high",
        "rouge2",
        "rouge2_ci_low",
        "rouge2_ci_high",
        "rougeL",
        "rougeL_ci_low",
        "rougeL_ci_high",
        "bertscore_precision",
        "bertscore_recall",
        "bertscore_f1",
        "bertscore_status",
        "bertscore_message",
        "average_latency_ms",
        "average_input_length",
        "average_output_length",
        "proxy_warning",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_per_record_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "note_id",
        "dataset",
        "split",
        "model_provider",
        "model_name",
        "status",
        "rouge1",
        "rouge2",
        "rougeL",
        "latency_ms",
        "input_token_count",
        "output_token_count",
        "reference_token_count",
        "error_message",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "note_id": row.get("note_id", ""),
                    "dataset": row.get("dataset", ""),
                    "split": row.get("split", ""),
                    "model_provider": row.get("model_provider", ""),
                    "model_name": row.get("model_name", ""),
                    "status": row.get("status", ""),
                    "rouge1": row.get("rouge1"),
                    "rouge2": row.get("rouge2"),
                    "rougeL": row.get("rougeL"),
                    "latency_ms": row.get("latency_ms"),
                    "input_token_count": len(str(row.get("source_note", "")).split()),
                    "output_token_count": len(str(row.get("generated_summary", "")).split()),
                    "reference_token_count": len(str(row.get("reference_summary", "")).split()),
                    "error_message": row.get("error_message"),
                }
            )


def _log(log_path: Path, message: str) -> None:
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    line = f"{timestamp} {message}"
    print(message)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _normalize_model_name(model: str) -> str:
    normalized = model.strip().lower()
    if normalized not in {"deterministic", "bart", "pegasus", "gemini"}:
        raise FullEvaluationPipelineError(
            f"Unsupported model '{model}'. Supported models: deterministic,bart,pegasus,gemini."
        )
    return normalized


def _parse_models(raw: str) -> tuple[str, ...]:
    models = tuple(_normalize_model_name(item) for item in raw.split(",") if item.strip())
    if not models:
        raise FullEvaluationPipelineError("At least one model must be requested.")
    return models


def _evaluation_layer(dataset: str) -> str:
    normalized = dataset.strip().lower().replace("-", "_")
    aliases = {
        "multi_clin_sum": "multiclinsum",
        "multi_clinsum": "multiclinsum",
        "mtsdialog": "mts_dialog",
        "mts_dialogue": "mts_dialog",
        "mediqasum": "mediqa_sum",
        "acibench": "aci_bench",
    }
    normalized = aliases.get(normalized, normalized)
    return {
        "mock": "Layer A - Functional Validation",
        "multiclinsum": "Layer C.1 - Primary Open Clinical Summarization Benchmark",
        "mts_dialog": "Layer C.2 - Auxiliary Dialogue-to-Note Proxy Evaluation",
        "mediqa_sum": "Layer C.2 - Auxiliary MEDIQA-Sum Proxy Evaluation",
        "aci_bench": "Layer C.3 - Optional Full-Visit Dialogue-to-Note Proxy Evaluation",
        "mimic_iv_note": "Layer D - Future Real EHR Note-Level Benchmark",
        "mimic_iv_ext_bhc": "Layer D - Future Real EHR Note-Level Benchmark",
    }.get(normalized, "Layer C - Proxy/Open Benchmark")


def _mean(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)


def _ci95(values: list[Any]) -> tuple[float | None, float | None]:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None, None
    if len(numeric) == 1:
        value = round(numeric[0], 4)
        return value, value
    avg = sum(numeric) / len(numeric)
    variance = sum((value - avg) ** 2 for value in numeric) / (len(numeric) - 1)
    standard_error = (variance ** 0.5) / (len(numeric) ** 0.5)
    margin = 1.96 * standard_error
    return round(max(0.0, avg - margin), 4), round(min(1.0, avg + margin), 4)


def _display(value: Any) -> str:
    if value is None or value == "":
        return "not_available"
    return str(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full layered MVP evaluation pipeline.")
    parser.add_argument("--input", required=True, help="Processed evaluation JSONL input path.")
    parser.add_argument("--dataset", default="multiclinsum")
    parser.add_argument("--models", default="deterministic,bart,pegasus")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--allow-model-downloads", action="store_true")
    parser.add_argument("--include-bertscore", action="store_true")
    parser.add_argument("--device", type=int, default=-1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--allow-gemini", action="store_true")
    parser.add_argument("--bart-model", default=os.environ.get("BART_MODEL_NAME", "facebook/bart-large-cnn"))
    parser.add_argument("--pegasus-model", default=os.environ.get("PEGASUS_MODEL_NAME", "google/pegasus-xsum"))
    parser.add_argument("--gemini-model", default=os.environ.get("RAG_GEMINI_MODEL", "gemini-2.5-flash-lite"))
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> PipelineConfig:
    return PipelineConfig(
        input_path=Path(args.input),
        dataset=args.dataset,
        models=_parse_models(args.models),
        limit=args.limit,
        output_dir=Path(args.output_dir),
        allow_model_downloads=args.allow_model_downloads,
        include_bertscore=args.include_bertscore,
        device=args.device,
        dry_run=args.dry_run,
        fail_fast=args.fail_fast,
        allow_gemini=args.allow_gemini,
        bart_model_name=args.bart_model,
        pegasus_model_name=args.pegasus_model,
        gemini_model_name=args.gemini_model,
    )


def main() -> None:
    args = _parse_args()
    result = run_full_evaluation_pipeline(config_from_args(args))
    print(PROXY_WARNING)
    print(f"Full evaluation pipeline outputs written to {result['output_dir']}")


if __name__ == "__main__":
    main()
