from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.evaluation.artifact_paths import configured_evaluation_artifact_root
from backend.app.evaluation.citation_grounding import analyze_prediction_row, write_grounding_outputs
from backend.app.evaluation.clinical_context_builder import (
    SECTION_QUERIES,
    build_clinical_context_from_chunks,
)
from backend.app.evaluation.clinical_metrics import compute_clinical_record_metrics
from backend.app.evaluation.reproducibility import build_reproducibility_manifest, write_reproducibility_manifest
from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics
from backend.app.schemas import ClinicalDocument
from backend.app.services.chunking import ClinicalChunker
from scripts.run_rag_grounded_benchmark import (
    MODEL_CHECKPOINTS,
    build_model_comparison,
    parse_models,
    write_json,
    write_jsonl,
    write_model_comparison,
    write_per_record_failure_analysis,
    write_per_record_metrics,
)
from src.data.dataset_loader import load_jsonl_dataset
from src.models import DeterministicSummarizer
from src.models.seq2seq import generate_seq2seq_summary, load_seq2seq_model


PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, "
    "or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as "
    "MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes."
)
DEFAULT_DATASET = Path("data/processed/governance/benchmark_set.jsonl")
DEFAULT_OUTPUT = configured_evaluation_artifact_root() / "clinical_context_benchmark"


def main() -> None:
    args = parse_args()
    configure_environment()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    log_path.write_text("", encoding="utf-8")
    started = time.perf_counter()
    log(log_path, "Starting clinical-context summarization benchmark.")
    records = load_jsonl_dataset(
        Path(args.dataset),
        dataset=args.dataset_name,
        split="train",
        require_reference=True,
        max_records=args.limit,
    )
    if not records:
        raise RuntimeError("No benchmark records were loaded.")
    log(log_path, f"Loaded {len(records)} records from {args.dataset}.")

    chunker = ClinicalChunker(Settings().chunk_max_chars, Settings().chunk_overlap_sentences)
    context_by_note: dict[str, dict[str, Any]] = {}
    context_rows: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        context_payload = build_record_context(record, chunker=chunker, args=args)
        context_by_note[record["note_id"]] = context_payload
        context_rows.append(context_payload["context_row"])
        if index % 25 == 0:
            log(log_path, f"Built clinical contexts for {index}/{len(records)} records.")

    write_jsonl(output_dir / "clinical_context_records.jsonl", context_rows)

    all_predictions: list[dict[str, Any]] = []
    model_rows: dict[str, list[dict[str, Any]]] = {}
    for provider in parse_models(args.models):
        rows = run_provider(provider, records, context_by_note, args, log_path)
        model_rows[provider] = rows
        all_predictions.extend(rows)
        write_jsonl(output_dir / f"{provider}_predictions.jsonl", rows)

    write_jsonl(output_dir / "all_predictions.jsonl", all_predictions)
    write_per_record_metrics(output_dir / "per_record_metrics.csv", all_predictions)
    write_per_record_failure_analysis(output_dir / "per_record_failure_analysis.jsonl", all_predictions)
    write_failure_analysis(output_dir / "failure_analysis.md", all_predictions)
    grounding_paths = write_grounding_outputs(output_dir, [analyze_prediction_row(row) for row in all_predictions])
    comparison_rows = build_model_comparison(model_rows, include_bertscore=args.include_bertscore)
    write_model_comparison(output_dir / "model_comparison.csv", comparison_rows)
    runtime = round(time.perf_counter() - started, 4)
    manifest = build_manifest(args, records, comparison_rows, context_rows, grounding_paths, runtime)
    write_json(output_dir / "clinical_context_manifest.json", manifest)
    write_reproducibility_manifest(output_dir / "reproducibility_manifest.json", manifest["reproducibility"])
    write_report(output_dir / "EVALUATION_REPORT.md", manifest, comparison_rows)
    log(log_path, f"Completed clinical-context benchmark in {runtime} seconds.")
    print(f"Clinical-context benchmark outputs written to {output_dir}")


def build_record_context(record: dict[str, str], *, chunker: ClinicalChunker, args: argparse.Namespace) -> dict[str, Any]:
    tenant_id = "clinical-context-benchmark"
    patient_id = record.get("patient_id") or record["note_id"]
    document = ClinicalDocument(
        document_id=record["note_id"],
        document_type="benchmark-source-note",
        title=f"{record.get('dataset', 'benchmark')} source note",
        encounter_id=record.get("encounter_id"),
        text=record["source_note"],
        metadata={"dataset": record.get("dataset", ""), "split": record.get("split", "")},
    )
    started = time.perf_counter()
    chunks = chunker.chunk_document(tenant_id, patient_id, document)
    context = build_clinical_context_from_chunks(
        chunks,
        max_chunks=args.max_context_chunks,
        max_chunks_per_section=args.max_chunks_per_section,
        max_chars_per_chunk=args.max_chars_per_chunk,
    )
    context_ms = round((time.perf_counter() - started) * 1000, 4)
    evidence_payload = [
        {
            "note_id": record["note_id"],
            "patient_id": patient_id,
            "encounter_id": record.get("encounter_id"),
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "section": chunk.section,
            "score": chunk.score,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "text": chunk.text,
        }
        for chunk in context.evidence
    ]
    return {
        "context_text": context.text,
        "evidence": context.evidence,
        "evidence_payload": evidence_payload,
        "context_row": {
            "note_id": record["note_id"],
            "patient_id": patient_id,
            "encounter_id": record.get("encounter_id", ""),
            "chunk_count": len(chunks),
            "context_chunk_count": len(context.evidence),
            "context_token_count": context.token_count,
            "context_build_latency_ms": context_ms,
            "section_counts": context.section_counts,
            "clinical_context": context.text,
        },
    }


def run_provider(
    provider: str,
    records: list[dict[str, str]],
    context_by_note: dict[str, dict[str, Any]],
    args: argparse.Namespace,
    log_path: Path,
) -> list[dict[str, Any]]:
    log(log_path, f"Running provider {provider}.")
    rows: list[dict[str, Any]] = []
    if provider == "deterministic":
        summarizer = DeterministicSummarizer(max_sentences=4)
        for record in records:
            context = context_by_note[record["note_id"]]
            output = summarizer.generate({"source_note": context["context_text"], "reference_summary": record["reference_summary"]})
            rows.append(prediction_row(record, context, provider, MODEL_CHECKPOINTS[provider], output.generated_summary, output.latency_ms))
        return rows

    model_name = MODEL_CHECKPOINTS[provider]
    tokenizer, model, torch_device = load_seq2seq_model(model_name, args.device, local_files_only=args.local_files_only)
    for index, record in enumerate(records, start=1):
        context = context_by_note[record["note_id"]]
        started = time.perf_counter()
        try:
            generated = generate_seq2seq_summary(
                tokenizer=tokenizer,
                model=model,
                torch_device=torch_device,
                source_note=context["context_text"],
                max_input_tokens=args.max_input_tokens,
                max_new_tokens=args.max_new_tokens,
                num_beams=args.num_beams,
                no_repeat_ngram_size=args.no_repeat_ngram_size,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            rows.append(prediction_row(record, context, provider, model_name, generated, latency_ms))
        except Exception as exc:
            rows.append(failed_prediction_row(record, context, provider, model_name, str(exc)))
        if index % 25 == 0:
            log(log_path, f"{provider}: completed {index}/{len(records)} records.")
    return rows


def prediction_row(
    record: dict[str, str],
    context: dict[str, Any],
    provider: str,
    model_name: str,
    generated_summary: str,
    latency_ms: int,
) -> dict[str, Any]:
    metrics = compute_pairwise_metrics([generated_summary], [record["reference_summary"]], include_bertscore=False)
    citations = [
        {
            "claim_index": None,
            "chunk_id": item["chunk_id"],
            "patient_id": item["patient_id"],
            "encounter_id": item.get("encounter_id"),
            "source_text": item["text"],
        }
        for item in context["evidence_payload"]
    ]
    row = {
        "evaluation_type": "clinical_context_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "stage": "clinical_context",
        "dataset": record.get("dataset", ""),
        "split": record.get("split", ""),
        "note_id": record["note_id"],
        "patient_id": record.get("patient_id", ""),
        "encounter_id": record.get("encounter_id", ""),
        "model_provider": provider,
        "model_name": model_name,
        "status": "completed",
        "error_message": None,
        "source_note": record["source_note"],
        "retrieved_evidence": context["context_text"],
        "clinical_context": context["context_text"],
        "reference_summary": record["reference_summary"],
        "generated_summary": generated_summary,
        "citations": citations,
        "latency_ms": latency_ms,
        "retrieval_latency_ms": None,
        "context_build_latency_ms": context["context_row"]["context_build_latency_ms"],
        "context_token_count": context["context_row"]["context_token_count"],
        "section_counts": context["context_row"]["section_counts"],
        "rouge1": metrics["rouge1"],
        "rouge2": metrics["rouge2"],
        "rougeL": metrics["rougeL"],
    }
    row.update(compute_clinical_record_metrics(row))
    return row


def failed_prediction_row(record: dict[str, str], context: dict[str, Any], provider: str, model_name: str, error: str) -> dict[str, Any]:
    return {
        "evaluation_type": "clinical_context_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "stage": "clinical_context",
        "dataset": record.get("dataset", ""),
        "split": record.get("split", ""),
        "note_id": record["note_id"],
        "patient_id": record.get("patient_id", ""),
        "encounter_id": record.get("encounter_id", ""),
        "model_provider": provider,
        "model_name": model_name,
        "status": "failed",
        "error_message": error,
        "source_note": record["source_note"],
        "retrieved_evidence": context["context_text"],
        "clinical_context": context["context_text"],
        "reference_summary": record["reference_summary"],
        "generated_summary": "",
        "citations": [],
        "latency_ms": None,
        "retrieval_latency_ms": None,
        "context_build_latency_ms": context["context_row"]["context_build_latency_ms"],
        "context_token_count": context["context_row"]["context_token_count"],
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
    }


def build_manifest(
    args: argparse.Namespace,
    records: list[dict[str, str]],
    comparison_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    grounding_paths: dict[str, Any],
    runtime: float,
) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    reproducibility = build_reproducibility_manifest(
        run_name="clinical_context_benchmark",
        dataset_path=Path(args.dataset),
        output_dir=output_dir,
        model_checkpoints={provider: MODEL_CHECKPOINTS[provider] for provider in parse_models(args.models)},
        prompt_template_version="clinical_context_builder.v1.raw_note_section_salience",
        retrieval_config={
            "used": False,
            "embedding_provider": None,
            "vector_store": None,
            "clinical_context_builder": "section_salience_from_source_chunks.v1",
            "clinical_sections": list(SECTION_QUERIES),
            "max_context_chunks": args.max_context_chunks,
            "max_chunks_per_section": args.max_chunks_per_section,
        },
        generation_params={
            "max_input_tokens": args.max_input_tokens,
            "max_new_tokens": args.max_new_tokens,
            "num_beams": args.num_beams,
            "no_repeat_ngram_size": args.no_repeat_ngram_size,
            "device": args.device,
        },
        extra={"proxy_warning": PROXY_WARNING},
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pipeline": "clinical_context_benchmark",
        "benchmark_type": "clinical_context",
        "proxy_warning": PROXY_WARNING,
        "input_path": str(args.dataset),
        "output_dir": str(output_dir),
        "records_loaded": len(records),
        "models": parse_models(args.models),
        "comparison_rows": comparison_rows,
        "context_summary": {
            "average_chunks": mean(row["chunk_count"] for row in context_rows),
            "average_context_chunks": mean(row["context_chunk_count"] for row in context_rows),
            "average_context_tokens": mean(row["context_token_count"] for row in context_rows),
            "average_context_build_latency_ms": mean(row["context_build_latency_ms"] for row in context_rows),
        },
        "citation_grounding": grounding_paths,
        "runtime_seconds": runtime,
        "reproducibility": reproducibility,
    }


def write_report(path: Path, manifest: dict[str, Any], comparison_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Clinical Context Summarization Benchmark",
        "",
        f"> {PROXY_WARNING}",
        "",
        "## Summary",
        "",
        f"- Records loaded: `{manifest['records_loaded']}`",
        f"- Runtime seconds: `{manifest['runtime_seconds']}`",
        "- Retrieval used: `false`",
        "- Context builder: `section_salience_from_source_chunks.v1`",
        f"- Average context chunks: `{manifest['context_summary']['average_context_chunks']}`",
        f"- Average context tokens: `{manifest['context_summary']['average_context_tokens']}`",
        "",
        "## Model Comparison",
        "",
        "| Model | Status | Records | ROUGE-L | BERTScore F1 | Citation coverage | Unsupported claim rate | Faithfulness | Latency p95 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in comparison_rows:
        lines.append(
            f"| `{row['model_provider']}` | `{row['status']}` | {row['completed_count']} | {row.get('rougeL')} | {row.get('bertscore_f1')} | {row.get('citation_coverage')} | {row.get('unsupported_claim_rate')} | {row.get('factuality_proxy_score')} | {row.get('latency_p95_ms')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This Flow 1.5 benchmark controls model input by converting each source note into structured clinical sections.",
            "- It does not test embedding quality or vector retrieval quality.",
            "- Compare it against Flow 1 to measure whether structured context improves summaries.",
            "- Compare it against Flow 2 to measure whether retrieval adds value beyond sectioned context.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_failure_analysis(path: Path, rows: list[dict[str, Any]]) -> None:
    counts = Counter()
    for row in rows:
        categories = row.get("failure_categories") or []
        if isinstance(categories, str):
            categories = [item.strip() for item in categories.split(";") if item.strip()]
        for category in categories:
            counts[str(category)] += 1
    lines = [
        "# Failure Analysis",
        "",
        f"> {PROXY_WARNING}",
        "",
        "## Failure Counts",
        "",
    ]
    if counts:
        lines.extend(f"- {category}: `{count}`" for category, count in sorted(counts.items()))
    else:
        lines.append("- No failure labels were generated.")
    path.write_text("\n".join(lines), encoding="utf-8")


def configure_environment() -> None:
    os.environ.setdefault("HF_HOME", "D:/hf_cache")
    os.environ.setdefault("HF_HUB_CACHE", "D:/hf_cache/hub")
    os.environ.setdefault("HF_DATASETS_CACHE", "D:/hf_cache/datasets")
    os.environ.setdefault("TRANSFORMERS_CACHE", "D:/hf_cache/hub")
    for key in ("HF_HOME", "HF_HUB_CACHE", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE"):
        if Path(os.environ[key]).drive.casefold() == "c:":
            raise RuntimeError(f"Refusing to use {key} on C drive: {os.environ[key]}")


def mean(values: Any) -> float | None:
    clean = [float(value) for value in values if value not in (None, "")]
    return round(sum(clean) / len(clean), 4) if clean else None


def log(path: Path, message: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}"
    print(message)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Flow 1.5 clinical-context summarization benchmark.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--dataset-name", default="multiclinsum")
    parser.add_argument("--models", default="deterministic")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-context-chunks", type=int, default=12)
    parser.add_argument("--max-chunks-per-section", type=int, default=2)
    parser.add_argument("--max-chars-per-chunk", type=int, default=700)
    parser.add_argument("--max-input-tokens", type=int, default=1024)
    parser.add_argument("--max-new-tokens", type=int, default=160)
    parser.add_argument("--num-beams", type=int, default=4)
    parser.add_argument("--no-repeat-ngram-size", type=int, default=3)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--include-bertscore", action="store_true")
    parser.add_argument("--allow-model-downloads", action="store_true")
    args = parser.parse_args()
    args.local_files_only = not args.allow_model_downloads
    return args


if __name__ == "__main__":
    main()
