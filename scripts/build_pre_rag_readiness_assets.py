from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.evaluation.citation_grounding import analyze_prediction_row, write_grounding_outputs
from backend.app.evaluation.clinical_metrics import (
    PER_RECORD_CLINICAL_FIELDS,
    aggregate_clinical_metrics,
    compute_clinical_record_metrics,
    serialize_failure_categories,
)
from backend.app.evaluation.dataset_diversity import (
    build_dataset_diversity_report,
    build_stratified_subsets,
    inventory_available_datasets,
    load_jsonl_records,
    profile_records,
    write_stratified_subsets,
)
from backend.app.evaluation.reproducibility import build_reproducibility_manifest, write_reproducibility_manifest
from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = Path("data/processed/governance/benchmark_set.jsonl")
DEFAULT_BENCHMARK_OUTPUT = Path("D:/clin_summ_outputs/medium_benchmark_bart_pegasus")
DEFAULT_OUTPUT = Path("D:/clin_summ_outputs/pre_rag_readiness")
PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, "
    "or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as "
    "MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes."
)


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset)
    benchmark_output_dir = Path(args.benchmark_output_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_cache_env()

    prediction_rows = enrich_prediction_rows(load_prediction_rows(benchmark_output_dir))
    comparison_rows = read_csv_rows(benchmark_output_dir / "model_comparison.csv")
    write_posthoc_record_artifacts(benchmark_output_dir, prediction_rows)
    write_posthoc_record_artifacts(output_dir, prediction_rows)
    bertscore_status = update_bertscore_if_requested(
        comparison_path=benchmark_output_dir / "model_comparison.csv",
        comparison_rows=comparison_rows,
        prediction_rows=prediction_rows,
        compute_bertscore=args.compute_bertscore,
        model_type=args.bertscore_model_type,
        device=args.bertscore_device,
        batch_size=args.bertscore_batch_size,
    )
    if args.compute_bertscore:
        comparison_rows = read_csv_rows(benchmark_output_dir / "model_comparison.csv")
    update_clinical_comparison_metrics(
        comparison_path=benchmark_output_dir / "model_comparison.csv",
        comparison_rows=comparison_rows,
        prediction_rows=prediction_rows,
    )
    comparison_rows = read_csv_rows(benchmark_output_dir / "model_comparison.csv")
    if comparison_rows:
        write_csv_rows(output_dir / "model_comparison.csv", comparison_rows, ordered_comparison_fields(comparison_rows, {}))

    records = load_jsonl_records(dataset_path)
    profiles = profile_records(records)
    inventory = inventory_available_datasets(ROOT)
    subsets = build_stratified_subsets(records, profiles, subset_size=args.subset_size)
    subset_manifest = write_stratified_subsets(output_dir / "stratified_subsets", subsets)
    write_json(output_dir / "dataset_strata_manifest.json", subset_manifest)
    (output_dir / "dataset_diversity_report.md").write_text(
        build_dataset_diversity_report(
            dataset_path=dataset_path,
            records=records,
            profiles=profiles,
            inventory=inventory,
            subset_manifest=subset_manifest,
        ),
        encoding="utf-8",
    )

    grounding_results = [analyze_prediction_row(row) for row in prediction_rows]
    grounding_paths = write_grounding_outputs(output_dir, grounding_results)

    human_review_paths = write_human_review_outputs(output_dir, prediction_rows)
    background_report_path = write_background_jobs_readiness_report(output_dir)
    tech_report_path = write_production_tech_gap_report(output_dir)

    manifest = build_reproducibility_manifest(
        run_name="pre_rag_readiness_assets",
        dataset_path=dataset_path,
        output_dir=output_dir,
        model_checkpoints=model_checkpoints(comparison_rows),
        prompt_template_version=os.environ.get("RAG_PROMPT_TEMPLATE_VERSION", "not_versioned"),
        retrieval_config={
            "embedding_provider": os.environ.get("RAG_EMBEDDING_PROVIDER", "sentence_transformers"),
            "embedding_model": os.environ.get("RAG_SENTENCE_TRANSFORMERS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            "vector_store": "qdrant",
            "retrieval_top_k": os.environ.get("RAG_RETRIEVAL_TOP_K", "6"),
            "note": "Current medium benchmark is summarization-only; retrieval config is captured for the next RAG-grounded benchmark.",
        },
        generation_params={
            "max_input_tokens": 1024,
            "max_new_tokens": 160,
            "num_beams": 4,
            "no_repeat_ngram_size": 3,
            "device": os.environ.get("RAG_GENERATION_DEVICE", "cpu"),
        },
        extra={
            "proxy_warning": PROXY_WARNING,
            "bertscore": bertscore_status,
            "dataset_strata_manifest": str(output_dir / "dataset_strata_manifest.json"),
            "citation_grounding": grounding_paths,
            "human_review": human_review_paths,
            "background_jobs_report": str(background_report_path),
            "production_tech_gap_report": str(tech_report_path),
        },
    )
    write_reproducibility_manifest(output_dir / "reproducibility_manifest.json", manifest)
    if benchmark_output_dir.exists():
        write_reproducibility_manifest(benchmark_output_dir / "reproducibility_manifest.json", manifest)

    write_readiness_summary(
        output_dir / "PRE_RAG_READINESS_REPORT.md",
        dataset_path=dataset_path,
        benchmark_output_dir=benchmark_output_dir,
        output_dir=output_dir,
        bertscore_status=bertscore_status,
        subset_manifest=subset_manifest,
        grounding_paths=grounding_paths,
        human_review_paths=human_review_paths,
        background_report_path=background_report_path,
        tech_report_path=tech_report_path,
    )
    if benchmark_output_dir.exists():
        mirror_paths_to_benchmark_output(output_dir, benchmark_output_dir)
    print(f"Pre-RAG readiness assets written to {output_dir}")


def mirror_paths_to_benchmark_output(output_dir: Path, benchmark_output_dir: Path) -> None:
    for filename in (
        "PRE_RAG_READINESS_REPORT.md",
        "dataset_diversity_report.md",
        "dataset_strata_manifest.json",
        "citation_grounding_report.md",
        "citation_grounding_metrics.csv",
        "human_review_rubric.csv",
        "human_review_workflow_report.md",
        "background_jobs_readiness_report.md",
        "production_tech_gap_report.md",
    ):
        source = output_dir / filename
        if source.exists():
            (benchmark_output_dir / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def configure_cache_env() -> None:
    defaults = {
        "HF_HOME": "D:/hf_cache",
        "HF_HUB_CACHE": "D:/hf_cache/hub",
        "HF_DATASETS_CACHE": "D:/hf_cache/datasets",
        "TRANSFORMERS_CACHE": "D:/hf_cache/hub",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    c_drive = [f"{key}={value}" for key, value in defaults.items() if Path(os.environ[key]).drive.casefold() == "c:"]
    if c_drive:
        raise RuntimeError("Refusing to use Hugging Face cache on C drive: " + ", ".join(c_drive))


def update_bertscore_if_requested(
    *,
    comparison_path: Path,
    comparison_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, Any]],
    compute_bertscore: bool,
    model_type: str,
    device: str,
    batch_size: int,
) -> dict[str, Any]:
    if not compute_bertscore:
        return {"requested": False, "status": "not_requested"}
    os.environ["RAG_BERTSCORE_MODEL_TYPE"] = model_type
    os.environ["RAG_BERTSCORE_DEVICE"] = device
    os.environ["RAG_BERTSCORE_BATCH_SIZE"] = str(batch_size)
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prediction_rows:
        if row.get("status") == "completed" and row.get("generated_summary") and row.get("reference_summary"):
            by_provider[str(row.get("model_provider") or "unknown")].append(row)
    metrics_by_provider: dict[str, dict[str, Any]] = {}
    for provider, rows in by_provider.items():
        metrics_by_provider[provider] = compute_pairwise_metrics(
            [str(row["generated_summary"]) for row in rows],
            [str(row["reference_summary"]) for row in rows],
            include_bertscore=True,
        )
    if comparison_rows:
        fields = ordered_comparison_fields(comparison_rows, metrics_by_provider)
        updated = []
        for row in comparison_rows:
            provider = row.get("model_provider") or ""
            metrics = metrics_by_provider.get(provider)
            if metrics:
                for key in ("bertscore_precision", "bertscore_recall", "bertscore_f1", "bertscore_status", "bertscore_model_type", "bertscore_message"):
                    row[key] = "" if metrics.get(key) is None else str(metrics.get(key))
            updated.append(row)
        write_csv_rows(comparison_path, updated, fields)
    statuses = {provider: metrics.get("bertscore_status") for provider, metrics in metrics_by_provider.items()}
    return {
        "requested": True,
        "model_type": model_type,
        "device": device,
        "batch_size": batch_size,
        "providers": sorted(metrics_by_provider),
        "statuses": statuses,
    }


def load_prediction_rows(output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(output_dir.glob("*predictions.jsonl")):
        if path.name == "all_predictions.jsonl":
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def enrich_prediction_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        payload = dict(row)
        clinical = compute_clinical_record_metrics(payload)
        for key, value in clinical.items():
            if payload.get(key) in (None, "", []):
                payload[key] = value
        enriched.append(payload)
    return enriched


def write_posthoc_record_artifacts(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_per_record_metrics(output_dir / "per_record_metrics.csv", rows)
    write_per_record_failure_analysis(output_dir / "per_record_failure_analysis.jsonl", rows)


def write_per_record_metrics(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "stage",
        "note_id",
        "model_provider",
        "model_name",
        "status",
        "rouge1",
        "rouge2",
        "rougeL",
        "latency_ms",
        *PER_RECORD_CLINICAL_FIELDS,
        "error_message",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            payload = {field: row.get(field) for field in fields}
            payload["failure_categories"] = serialize_failure_categories(row.get("failure_categories"))
            writer.writerow(payload)


def write_per_record_failure_analysis(path: Path, rows: list[dict[str, Any]]) -> None:
    by_note: dict[str, dict[str, Any]] = {}
    for row in rows:
        note_id = str(row.get("note_id") or "")
        entry = by_note.setdefault(
            note_id,
            {
                "note_id": note_id,
                "patient_id": row.get("patient_id", ""),
                "encounter_id": row.get("encounter_id", ""),
                "dataset": row.get("dataset", ""),
                "input_note": row.get("source_note", ""),
                "reference_summary": row.get("reference_summary", ""),
                "retrieved_evidence": row.get("retrieved_evidence") or row.get("evidence") or "",
                "citations": row.get("citations") or [],
                "failure_labels": [],
                "model_outputs": [],
            },
        )
        labels = [item.strip() for item in serialize_failure_categories(row.get("failure_categories")).split(";") if item.strip()]
        entry["failure_labels"] = sorted(set(entry["failure_labels"]) | set(labels))
        entry["model_outputs"].append(
            {
                "model_provider": row.get("model_provider"),
                "model_name": row.get("model_name"),
                "status": row.get("status"),
                "generated_summary": row.get("generated_summary"),
                "rouge1": row.get("rouge1"),
                "rouge2": row.get("rouge2"),
                "rougeL": row.get("rougeL"),
                "latency_ms": row.get("latency_ms"),
                "clinical_metrics": {
                    field: row.get(field)
                    for field in PER_RECORD_CLINICAL_FIELDS
                    if field != "failure_categories"
                },
                "error_message": row.get("error_message"),
            }
        )
    with path.open("w", encoding="utf-8") as handle:
        for entry in by_note.values():
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def update_clinical_comparison_metrics(
    *,
    comparison_path: Path,
    comparison_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, Any]],
) -> None:
    if not comparison_rows:
        return
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prediction_rows:
        by_provider[str(row.get("model_provider") or "unknown")].append(row)
    fields = ordered_comparison_fields(comparison_rows, {})
    for key in (
        "latency_p50_ms",
        "latency_p95_ms",
        "citation_coverage",
        "unsupported_claim_rate",
        "factuality_proxy_score",
        "missing_diagnosis_rate",
        "missing_medication_rate",
        "timeline_completeness",
        "hallucinated_clinical_entity_count",
        "critical_info_omission_rate",
        "failure_counts",
    ):
        if key not in fields:
            fields.append(key)
    updated = []
    for row in comparison_rows:
        metrics = aggregate_clinical_metrics(by_provider.get(row.get("model_provider") or "", []))
        for key, value in metrics.items():
            if key == "failure_counts":
                row[key] = json.dumps(value or {}, ensure_ascii=False)
            elif value is not None:
                row[key] = str(value)
        updated.append(row)
    write_csv_rows(comparison_path, updated, fields)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    tmp_path.replace(path)


def ordered_comparison_fields(rows: list[dict[str, str]], metrics_by_provider: dict[str, dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    for key in ("bertscore_precision", "bertscore_recall", "bertscore_f1", "bertscore_status", "bertscore_model_type", "bertscore_message"):
        if key not in fields:
            fields.append(key)
    return fields


def model_checkpoints(comparison_rows: list[dict[str, str]]) -> dict[str, str]:
    checkpoints = {}
    for row in comparison_rows:
        provider = row.get("model_provider") or "unknown"
        checkpoints[provider] = row.get("checkpoint") or row.get("model_name") or "not_available"
    checkpoints.setdefault("retrieval_embedding", os.environ.get("RAG_SENTENCE_TRANSFORMERS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    checkpoints.setdefault("bertscore_evaluator", os.environ.get("RAG_BERTSCORE_MODEL_TYPE", "not_requested"))
    return checkpoints


def write_human_review_outputs(output_dir: Path, prediction_rows: list[dict[str, Any]]) -> dict[str, str]:
    rubric_path = output_dir / "human_review_rubric.csv"
    report_path = output_dir / "human_review_workflow_report.md"
    fields = [
        "note_id",
        "model_provider",
        "model_name",
        "input_note",
        "generated_summary",
        "reference_summary",
        "factual_correctness_score",
        "completeness_score",
        "medication_safety_score",
        "diagnosis_coverage_score",
        "timeline_accuracy_score",
        "citation_usefulness_score",
        "readability_score",
        "accept_reject",
        "reviewer_id",
        "reviewer_signature",
        "review_notes",
    ]
    with rubric_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in prediction_rows:
            writer.writerow(
                {
                    "note_id": row.get("note_id", ""),
                    "model_provider": row.get("model_provider", ""),
                    "model_name": row.get("model_name", ""),
                    "input_note": row.get("source_note", ""),
                    "generated_summary": row.get("generated_summary", ""),
                    "reference_summary": row.get("reference_summary", ""),
                }
            )
    report_path.write_text(
        "\n".join(
            [
                "# Human Review Workflow Readiness",
                "",
                f"> {PROXY_WARNING}",
                "",
                "## Implemented",
                "",
                "- Summary review start/edit/approve/reject API exists.",
                "- Review actions persist reviewer, timestamp, status transition, comments, rejection reason, and edit distance.",
                "- Approved summaries are no longer mutable through the normal edit/approve/reject transition set.",
                "- Audit metadata records actor, patient, summary, previous status, resulting status, and action context.",
                "",
                "## Added Artifact",
                "",
                f"- Human review rubric export: `{rubric_path}`",
                "",
                "## Remaining Production Hardening",
                "",
                "- Add cryptographic/e-signature integration for real reviewer signatures.",
                "- Add immutable final approved summary export/writeback lock after governance approval.",
                "- Add side-by-side doctor edit diff UI.",
                "- Aggregate approve/reject reason analytics on the dashboard.",
            ]
        ),
        encoding="utf-8",
    )
    return {"rubric_csv": str(rubric_path), "report": str(report_path)}


def write_background_jobs_readiness_report(output_dir: Path) -> Path:
    path = output_dir / "background_jobs_readiness_report.md"
    path.write_text(
        "\n".join(
            [
                "# Background Jobs Readiness",
                "",
                "Heavy model generation should not block request/response API calls.",
                "",
                "## Required Capabilities",
                "",
                "- Job queue for BART/Pegasus/Gemini generation.",
                "- Job status: queued, running, completed, failed, cancelled, timed_out.",
                "- Cancellation and timeout handling.",
                "- Model warmup command.",
                "- Cached model readiness screen.",
                "",
                "## Current Implementation Scope",
                "",
                "- This readiness artifact is generated before wiring model generation into the queue.",
                "- API scaffold should expose job creation/status/cancel/readiness before production traffic.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def write_production_tech_gap_report(output_dir: Path) -> Path:
    path = output_dir / "production_tech_gap_report.md"
    rows = [
        ("Qdrant", "Installed/integrated in RAG service", "Not yet used by summarization-only benchmark; needed for retrieval-grounded benchmark."),
        ("sentence-transformers/all-MiniLM-L6-v2", "Configured as default retrieval embedding", "Requires reingest/reindex for existing Qdrant points."),
        ("BERTScore", "Optional semantic metric", "Requires evaluator model cache such as roberta-large and explicit compute step."),
        ("MLflow", "Config fields present", "Not yet central experiment tracker for all benchmark runs."),
        ("FHIR mapping", "Prototype schemas/routes exist", "No production HIS/EMR writeback enabled."),
        ("Medical NLI", "Config fields present", "Model path/governance not active by default."),
        ("FastEmbed/ONNX", "Alternative embedding backend", "Not selected after MiniLM audit."),
        ("Google OAuth", "Client config supported", "Prototype auth still needs full production identity governance."),
        ("Background jobs", "Readiness plan added", "Model generation not yet queued by default."),
    ]
    lines = [
        "# Production-Ready Technology Gap Report",
        "",
        "| Technology | Current state | Remaining work |",
        "| --- | --- | --- |",
    ]
    for technology, state, gap in rows:
        lines.append(f"| {technology} | {state} | {gap} |")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_readiness_summary(
    path: Path,
    *,
    dataset_path: Path,
    benchmark_output_dir: Path,
    output_dir: Path,
    bertscore_status: dict[str, Any],
    subset_manifest: dict[str, Any],
    grounding_paths: dict[str, Any],
    human_review_paths: dict[str, str],
    background_report_path: Path,
    tech_report_path: Path,
) -> None:
    lines = [
        "# Pre-RAG Readiness Report",
        "",
        f"> {PROXY_WARNING}",
        "",
        "## Completed Checklist",
        "",
        "- [x] Reproducibility manifest v2",
        "- [x] Dataset diversity inventory and stratified subsets",
        "- [x] BERTScore post-hoc update path",
        "- [x] Citation-grounding validator artifacts",
        "- [x] Human review rubric/export",
        "- [x] Background job readiness report",
        "- [x] Production tech gap report",
        "",
        "## Key Paths",
        "",
        f"- Dataset: `{dataset_path}`",
        f"- Benchmark output: `{benchmark_output_dir}`",
        f"- Readiness output: `{output_dir}`",
        f"- Reproducibility manifest: `{output_dir / 'reproducibility_manifest.json'}`",
        f"- Dataset strata manifest: `{output_dir / 'dataset_strata_manifest.json'}`",
        f"- Citation report: `{grounding_paths.get('report')}`",
        f"- Human review rubric: `{human_review_paths.get('rubric_csv')}`",
        f"- Background jobs report: `{background_report_path}`",
        f"- Technology gap report: `{tech_report_path}`",
        "",
        "## BERTScore",
        "",
        f"```json\n{json.dumps(bertscore_status, ensure_ascii=False, indent=2)}\n```",
        "",
        "## Stratified Subsets",
        "",
    ]
    for name, item in sorted(subset_manifest.get("subsets", {}).items()):
        lines.append(f"- `{name}`: `{item['record_count']}` records")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "After these readiness assets are stable, build the retrieval-grounded benchmark that uses MiniLM + Qdrant before summarization.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build pre-RAG evaluation readiness assets.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--benchmark-output-dir", default=str(DEFAULT_BENCHMARK_OUTPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--subset-size", type=int, default=50)
    parser.add_argument("--compute-bertscore", action="store_true")
    parser.add_argument("--bertscore-model-type", default=os.environ.get("RAG_BERTSCORE_MODEL_TYPE", "roberta-large"))
    parser.add_argument("--bertscore-device", default=os.environ.get("RAG_BERTSCORE_DEVICE", "cpu"))
    parser.add_argument("--bertscore-batch-size", type=int, default=int(os.environ.get("RAG_BERTSCORE_BATCH_SIZE", "4")))
    return parser.parse_args()


if __name__ == "__main__":
    main()
