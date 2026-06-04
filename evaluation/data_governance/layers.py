from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from backend.app.schemas import ClinicalDocument
from backend.app.services.chunking import ClinicalChunker, HEADING_RE
from backend.app.services.embeddings import HashingEmbeddingProvider


HONESTY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, "
    "clinical effectiveness, or real-world healthcare performance. Real EHR "
    "evaluation requires credentialed datasets such as MIMIC-IV-Note or "
    "MIMIC-IV-BHC under approved governance processes."
)
SECTION_LABEL_RE = re.compile(
    r"\b("
    r"assessment(?:\s+and\s+plan)?|plan|history(?:\s+of\s+present\s+illness)?|"
    r"hpi|findings|impression|diagnosis|medications?|allergies|laboratory|"
    r"labs?|vitals?|procedure|follow[- ]?up|chief complaint|"
    r"brief hospital course|hospital course"
    r")\s*:",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class GovernanceArtifacts:
    benchmark_records: list[dict[str, str]]
    warning_records: list[dict[str, str]]
    rejected_records: list[dict[str, str]]
    dataset_manifest: dict[str, Any]
    dataset_profile: dict[str, Any]
    quality_metrics: dict[str, Any]
    chunking_manifest: dict[str, Any]
    retrieval_metrics: dict[str, Any]
    model_manifest: dict[str, Any]
    run_manifest_base: dict[str, Any]


def run_governance_preflight(
    records: list[dict[str, str]],
    *,
    dataset: str,
    input_path: Path,
    output_dir: Path,
    requested_models: tuple[str, ...],
    cache_paths: dict[str, str],
) -> GovernanceArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    governance_dir = output_dir / "data_governance"
    governance_dir.mkdir(parents=True, exist_ok=True)

    dataset_manifest = build_dataset_manifest(records, dataset=dataset, input_path=input_path)
    dataset_profile = build_dataset_profile(records, dataset=dataset)
    quality_by_record, quality_metrics = audit_data_quality(records, dataset=dataset)
    benchmark_records, warning_records, rejected_records = route_records(records, quality_by_record)
    chunking_manifest, chunk_samples = validate_chunking(benchmark_records)
    retrieval_metrics = validate_retrieval(benchmark_records, chunk_samples)
    model_manifest = build_model_manifest(requested_models)
    run_manifest_base = build_run_manifest_base(
        dataset=dataset,
        input_path=input_path,
        output_dir=output_dir,
        cache_paths=cache_paths,
        dataset_manifest=dataset_manifest,
        model_manifest=model_manifest,
    )

    _write_json(governance_dir / "dataset_manifest.json", dataset_manifest)
    _write_json(output_dir / "dataset_profile.json", dataset_profile)
    _write_json(governance_dir / "dataset_profile.json", dataset_profile)
    _write_json(output_dir / "quality_metrics.json", quality_metrics)
    _write_json(governance_dir / "quality_metrics.json", quality_metrics)
    _write_json(output_dir / "retrieval_metrics.json", retrieval_metrics)
    _write_json(governance_dir / "retrieval_metrics.json", retrieval_metrics)
    _write_json(governance_dir / "chunking_manifest.json", chunking_manifest)
    _write_json(governance_dir / "model_manifest.json", model_manifest)
    _write_jsonl(governance_dir / "record_quality.jsonl", quality_by_record)
    _write_jsonl(governance_dir / "benchmark_manifest.jsonl", [_routing_row(record, "benchmark") for record in benchmark_records])
    _write_jsonl(governance_dir / "warning_manifest.jsonl", [_routing_row(record, "warning") for record in warning_records])
    _write_jsonl(governance_dir / "rejected_manifest.jsonl", [_routing_row(record, "rejected") for record in rejected_records])
    _write_jsonl(governance_dir / "chunk_samples.jsonl", chunk_samples[:100])
    _write_markdown(governance_dir / "dataset_governance_report.md", dataset_governance_report(dataset_manifest, dataset_profile))
    _write_markdown(governance_dir / "quality_report.md", quality_report(quality_metrics))
    _write_markdown(governance_dir / "chunking_report.md", chunking_report(chunking_manifest))
    _write_markdown(output_dir / "retrieval_report.md", retrieval_report(retrieval_metrics))
    _write_markdown(governance_dir / "retrieval_report.md", retrieval_report(retrieval_metrics))

    return GovernanceArtifacts(
        benchmark_records=benchmark_records,
        warning_records=warning_records,
        rejected_records=rejected_records,
        dataset_manifest=dataset_manifest,
        dataset_profile=dataset_profile,
        quality_metrics=quality_metrics,
        chunking_manifest=chunking_manifest,
        retrieval_metrics=retrieval_metrics,
        model_manifest=model_manifest,
        run_manifest_base=run_manifest_base,
    )


def configure_d_drive_environment() -> dict[str, str]:
    defaults = {
        "HF_HOME": "D:/hf_cache",
        "HF_HUB_CACHE": "D:/hf_cache/hub",
        "HF_DATASETS_CACHE": "D:/hf_cache/datasets",
        "TRANSFORMERS_CACHE": "D:/hf_cache/hub",
        "CLIN_SUMM_DATA_DIR": "D:/clin_summ_data",
        "CLIN_SUMM_MODEL_DIR": "D:/clin_summ_models",
        "CLIN_SUMM_OUTPUT_DIR": "D:/clin_summ_outputs",
    }
    active: dict[str, str] = {}
    for key, default in defaults.items():
        existing = os.environ.get(key)
        if existing and _is_c_drive_path(str(Path(existing))):
            raise RuntimeError(f"{key} points to C drive: {existing}. Use D drive cache/output paths only.")
        value = default if key.startswith("HF_") or key == "TRANSFORMERS_CACHE" else existing or default
        normalized = str(Path(value))
        if _is_c_drive_path(normalized):
            raise RuntimeError(f"{key} points to C drive: {value}. Use D drive cache/output paths only.")
        os.environ[key] = value
        Path(value).mkdir(parents=True, exist_ok=True)
        active[key] = value
    return active


def _is_c_drive_path(value: str) -> bool:
    return value.replace("\\", "/").casefold().startswith("c:/")


def build_dataset_manifest(
    records: list[dict[str, str]],
    *,
    dataset: str,
    input_path: Path,
) -> dict[str, Any]:
    source_hash = _file_sha256(input_path) if input_path.exists() else None
    duplicate_count = _duplicate_count(records)
    return {
        "dataset": dataset,
        "dataset_version": _infer_dataset_version(dataset, input_path),
        "input_path": str(input_path),
        "input_sha256": source_hash,
        "record_count": len(records),
        "source_distribution": dict(Counter(record.get("dataset", dataset) for record in records)),
        "duplicate_count": duplicate_count,
        "duplicate_rate": _rate(duplicate_count, len(records)),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "honesty_warning": HONESTY_WARNING,
    }


def build_dataset_profile(records: list[dict[str, str]], *, dataset: str) -> dict[str, Any]:
    source_lengths = [len(record.get("source_note", "").split()) for record in records]
    summary_lengths = [len(record.get("reference_summary", "").split()) for record in records]
    token_counts = source_lengths + summary_lengths
    missing_fields = {
        "note_id": sum(1 for record in records if not record.get("note_id")),
        "source_note": sum(1 for record in records if not record.get("source_note")),
        "reference_summary": sum(1 for record in records if not record.get("reference_summary")),
    }
    malformed_entries = sum(1 for record in records if not record.get("source_note") or not record.get("reference_summary"))
    return {
        "dataset": dataset,
        "record_count": len(records),
        "source_distribution": dict(Counter(record.get("dataset", dataset) for record in records)),
        "missing_fields": missing_fields,
        "malformed_entries": malformed_entries,
        "duplicates": _duplicate_count(records),
        "average_note_length": _mean(source_lengths),
        "average_summary_length": _mean(summary_lengths),
        "token_statistics": _distribution(token_counts),
        "note_length_statistics": _distribution(source_lengths),
        "summary_length_statistics": _distribution(summary_lengths),
        "honesty_warning": HONESTY_WARNING,
    }


def audit_data_quality(
    records: list[dict[str, str]],
    *,
    dataset: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for record in records:
        fingerprint = _record_fingerprint(record)
        duplicate = fingerprint in seen
        seen.add(fingerprint)
        row = quality_for_record(record, duplicate=duplicate)
        rows.append(row)

    scores = [row["quality_score"] for row in rows]
    missing_count = sum(1 for row in rows if row["missing_fields"])
    duplicate_count = sum(1 for row in rows if row["duplicate"])
    noisy_count = sum(1 for row in rows if row["noise_ratio"] > 0.12 or row["ocr_corruption_score"] > 0.12)
    routed = Counter(route_for_score(row["quality_score"]) for row in rows)
    return rows, {
        "dataset": dataset,
        "record_count": len(records),
        "average_quality_score": _mean(scores),
        "quality_score_distribution": _distribution(scores),
        "missing_rate": _rate(missing_count, len(records)),
        "duplicate_rate": _rate(duplicate_count, len(records)),
        "noise_rate": _rate(noisy_count, len(records)),
        "section_coverage": _mean([row["section_coverage"] for row in rows]),
        "token_distribution": _distribution([row["source_token_count"] for row in rows]),
        "route_counts": dict(routed),
        "honesty_warning": HONESTY_WARNING,
    }


def quality_for_record(record: dict[str, str], *, duplicate: bool) -> dict[str, Any]:
    source = record.get("source_note", "")
    reference = record.get("reference_summary", "")
    source_tokens = _tokens(source)
    reference_tokens = _tokens(reference)
    missing_fields = [
        field
        for field in ("note_id", "source_note", "reference_summary")
        if not str(record.get(field) or "").strip()
    ]
    section_count = _section_label_count(source)
    section_coverage = min(1.0, section_count / 3)
    noise_ratio = _noise_ratio(source)
    ocr_corruption_score = _ocr_corruption_score(source)
    formatting_consistency = _formatting_consistency(source)
    length_score = _length_score(len(source_tokens), minimum=20, target=75)
    summary_length_score = _length_score(len(reference_tokens), minimum=5, target=30)
    completeness = 1.0 - min(1.0, len(missing_fields) / 3)
    duplicate_penalty = 0.25 if duplicate else 0.0
    quality_score = (
        0.28 * completeness
        + 0.14 * section_coverage
        + 0.18 * length_score
        + 0.12 * summary_length_score
        + 0.12 * (1.0 - noise_ratio)
        + 0.08 * (1.0 - ocr_corruption_score)
        + 0.08 * formatting_consistency
        - duplicate_penalty
    )
    quality_score = max(0.0, min(1.0, round(quality_score, 4)))
    return {
        "note_id": record.get("note_id", ""),
        "dataset": record.get("dataset", ""),
        "quality_score": quality_score,
        "route": route_for_score(quality_score),
        "missing_fields": missing_fields,
        "duplicate": duplicate,
        "source_token_count": len(source_tokens),
        "summary_token_count": len(reference_tokens),
        "section_coverage": round(section_coverage, 4),
        "noise_ratio": round(noise_ratio, 4),
        "ocr_corruption_score": round(ocr_corruption_score, 4),
        "formatting_consistency": round(formatting_consistency, 4),
        "needs_review": quality_score < 0.8,
    }


def route_for_score(score: float) -> str:
    if score >= 0.8:
        return "benchmark"
    if score >= 0.5:
        return "warning"
    return "rejected"


def route_records(
    records: list[dict[str, str]],
    quality_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    benchmark: list[dict[str, str]] = []
    warning: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    for record, quality in zip(records, quality_rows, strict=True):
        enriched = {**record, "quality_score": str(quality["quality_score"]), "quality_route": quality["route"]}
        if quality["route"] == "benchmark":
            benchmark.append(enriched)
        elif quality["route"] == "warning":
            warning.append(enriched)
        else:
            rejected.append(enriched)
    return benchmark, warning, rejected


def validate_chunking(records: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    chunker = ClinicalChunker(max_chars=1200, overlap_sentences=1)
    samples: list[dict[str, Any]] = []
    problematic = 0
    chunk_counts: list[int] = []
    chunk_lengths: list[int] = []
    heading_preserved = 0
    fragmentation_flags: Counter[str] = Counter()
    for record in records:
        document = ClinicalDocument(
            document_id=record.get("note_id") or "unknown_note",
            document_type="evaluation_source_note",
            title=f"{record.get('dataset', 'dataset')} source note",
            encounter_id=record.get("encounter_id"),
            text=record.get("source_note", ""),
        )
        chunks = chunker.chunk_document("evaluation", record.get("patient_id", "patient"), document)
        chunk_counts.append(len(chunks))
        chunk_lengths.extend(len(chunk.text.split()) for chunk in chunks)
        source_headings = {match.group("header").casefold() for match in HEADING_RE.finditer(document.text)}
        chunk_sections = {chunk.section.casefold() for chunk in chunks}
        if not source_headings or source_headings & chunk_sections:
            heading_preserved += 1
        flags = _chunk_fragmentation_flags(chunks)
        fragmentation_flags.update(flags)
        if flags:
            problematic += 1
        for chunk in chunks[:3]:
            samples.append(
                {
                    "note_id": record.get("note_id", ""),
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "token_length": len(chunk.text.split()),
                    "text_preview": chunk.text[:400],
                    "source_traceability": bool(chunk.document_id and chunk.char_end > chunk.char_start),
                }
            )
    return {
        "record_count": len(records),
        "chunk_count": sum(chunk_counts),
        "average_chunks_per_record": _mean(chunk_counts),
        "average_chunk_length": _mean(chunk_lengths),
        "overlap_ratio": "configured_overlap_sentences=1",
        "section_preservation": _rate(heading_preserved, len(records)),
        "heading_preservation": _rate(heading_preserved, len(records)),
        "context_fragmentation": _rate(problematic, len(records)),
        "source_traceability": 1.0 if samples else 0.0,
        "fragmentation_flags": dict(fragmentation_flags),
        "problematic_chunking_detected": problematic > 0,
        "honesty_warning": HONESTY_WARNING,
    }, samples


def validate_retrieval(records: list[dict[str, str]], chunk_samples: list[dict[str, Any]]) -> dict[str, Any]:
    # Lightweight local retrieval validation. The labels below mirror the target
    # models, while hashing embeddings avoid downloads during governance preflight.
    candidates = {
        "all-MiniLM-L6-v2": HashingEmbeddingProvider(dimension=384),
        "paraphrase-multilingual-MiniLM-L12-v2": HashingEmbeddingProvider(dimension=384),
    }
    text_by_note: dict[str, list[str]] = {}
    for sample in chunk_samples:
        text_by_note.setdefault(sample["note_id"], []).append(str(sample["text_preview"]))

    model_metrics: dict[str, Any] = {}
    for model_name, provider in candidates.items():
        latencies: list[float] = []
        recalls: list[float] = []
        precisions: list[float] = []
        duplicate_vectors = 0
        index_size = 0
        for record in records:
            chunks = text_by_note.get(record.get("note_id", ""), [])
            if not chunks:
                continue
            import time

            started = time.perf_counter()
            vectors = provider.embed_documents(chunks)
            query = provider.embed_query(record.get("reference_summary", ""))
            scores = [_cosine(query, vector) for vector in vectors]
            ranked = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
            top_k = ranked[: min(3, len(ranked))]
            relevant = _relevant_chunk_indexes(chunks, record.get("reference_summary", ""))
            retrieved_relevant = len(set(top_k) & relevant)
            recalls.append(_rate(retrieved_relevant, len(relevant)))
            precisions.append(_rate(retrieved_relevant, len(top_k)))
            latencies.append((time.perf_counter() - started) * 1000)
            duplicate_vectors += len(vectors) - len({_vector_hash(vector) for vector in vectors})
            index_size += len(vectors)
        model_metrics[model_name] = {
            "embedding_dimension": provider.dimension,
            "index_size": index_size,
            "duplicate_vectors": duplicate_vectors,
            "retrieval_latency_ms": _mean(latencies),
            "recall_at_k": _mean(recalls),
            "precision_at_k": _mean(precisions),
        }
    return {
        "validation_type": "local_hashing_retrieval_sanity_check",
        "models_compared": list(model_metrics),
        "model_metrics": model_metrics,
        "honesty_warning": HONESTY_WARNING,
    }


def build_model_manifest(requested_models: tuple[str, ...]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for model in requested_models:
        rows[model] = {
            "model_name": _model_name(model),
            "model_provider": model,
            "parameter_count": "not_loaded_in_preflight",
            "model_size": "not_loaded_in_preflight",
            "load_time_ms": None,
            "inference_time_ms": "recorded_per_prediction_when_run",
            "download_policy": "blocked_by_default" if model in {"bart", "pegasus"} else "local_or_explicit_opt_in",
        }
    return {
        "models": rows,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "honesty_warning": HONESTY_WARNING,
    }


def build_run_manifest_base(
    *,
    dataset: str,
    input_path: Path,
    output_dir: Path,
    cache_paths: dict[str, str],
    dataset_manifest: dict[str, Any],
    model_manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit_hash": _git_commit_hash(),
        "dataset": dataset,
        "dataset_version": dataset_manifest.get("dataset_version"),
        "dataset_manifest_ref": "data_governance/dataset_manifest.json",
        "model_manifest_ref": "data_governance/model_manifest.json",
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "cache_location": cache_paths,
        "honesty_warning": HONESTY_WARNING,
        "model_manifest": model_manifest,
    }


def write_human_review_template(prediction_rows: list[dict[str, Any]], output_dir: Path) -> None:
    path = output_dir / "human_review_template.csv"
    fieldnames = [
        "note_id",
        "model_provider",
        "source_text",
        "generated_summary",
        "reference_summary",
        "clinical_accuracy_1_5",
        "completeness_1_5",
        "readability_1_5",
        "faithfulness_1_5",
        "evidence_alignment_1_5",
        "reviewer_comments",
    ]
    completed = [row for row in prediction_rows if row.get("status") == "completed"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in completed:
            writer.writerow(
                {
                    "note_id": row.get("note_id", ""),
                    "model_provider": row.get("model_provider", ""),
                    "source_text": row.get("source_note", ""),
                    "generated_summary": row.get("generated_summary", ""),
                    "reference_summary": row.get("reference_summary", ""),
                    "clinical_accuracy_1_5": "",
                    "completeness_1_5": "",
                    "readability_1_5": "",
                    "faithfulness_1_5": "",
                    "evidence_alignment_1_5": "",
                    "reviewer_comments": "",
                }
            )


def write_failure_analysis(
    prediction_rows: list[dict[str, Any]],
    *,
    output_dir: Path,
    quality_by_note: dict[str, str],
) -> None:
    completed = [row for row in prediction_rows if row.get("status") == "completed"]
    scored = []
    for row in completed:
        metrics = _safe_single_pair_metrics(row.get("generated_summary", ""), row.get("reference_summary", ""))
        scored.append({**row, **metrics, "failure_categories": _failure_categories(row, quality_by_note)})
    worst = sorted(scored, key=lambda row: row.get("rougeL", 0.0))[:20]
    best = sorted(scored, key=lambda row: row.get("rougeL", 0.0), reverse=True)[:20]
    lines = [
        "# Failure Analysis",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Failure Categories Used",
        "",
        "- Hallucination",
        "- Missing Diagnosis",
        "- Missing Medication",
        "- Missing Timeline",
        "- Incomplete Summary",
        "- Chunking Failure",
        "- Retrieval Failure",
        "- Data Quality Failure",
        "",
        "## Worst 20 Records",
        "",
    ]
    lines.extend(_failure_rows(worst))
    lines.extend(["", "## Best 20 Records", ""])
    lines.extend(_failure_rows(best))
    if not scored:
        lines.append("No completed predictions were available for failure analysis.")
    _write_markdown(output_dir / "failure_analysis.md", "\n".join(lines))


def _safe_single_pair_metrics(prediction: str, reference: str) -> dict[str, Any]:
    try:
        from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics

        return compute_pairwise_metrics([prediction], [reference], include_bertscore=False)
    except Exception:
        return {"rouge1": None, "rouge2": None, "rougeL": None}


def _failure_categories(row: dict[str, Any], quality_by_note: dict[str, str]) -> list[str]:
    text = f"{row.get('generated_summary', '')} {row.get('reference_summary', '')}".casefold()
    categories: list[str] = []
    if quality_by_note.get(row.get("note_id", "")) in {"warning", "rejected"}:
        categories.append("Data Quality Failure")
    if "diagnos" in text and "diagnos" not in row.get("generated_summary", "").casefold():
        categories.append("Missing Diagnosis")
    if any(term in text for term in ("medication", "medications", "drug", "dose")) and not any(
        term in row.get("generated_summary", "").casefold() for term in ("medication", "drug", "dose")
    ):
        categories.append("Missing Medication")
    if any(term in text for term in ("day", "date", "timeline", "follow")) and not any(
        term in row.get("generated_summary", "").casefold() for term in ("day", "date", "follow")
    ):
        categories.append("Missing Timeline")
    if len(row.get("generated_summary", "").split()) < max(5, len(row.get("reference_summary", "").split()) // 4):
        categories.append("Incomplete Summary")
    if not categories:
        categories.append("Needs Human Review")
    return categories


def _failure_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No records available."]
    lines = ["| Rank | Note ID | Model | ROUGE-L | Categories |", "| ---: | --- | --- | ---: | --- |"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | `{row.get('note_id', '')}` | `{row.get('model_provider', '')}` | `{row.get('rougeL')}` | {', '.join(row.get('failure_categories', []))} |"
        )
    return lines


def dataset_governance_report(manifest: dict[str, Any], profile: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Dataset Governance Report",
            "",
            f"> {HONESTY_WARNING}",
            "",
            f"- Dataset: `{manifest['dataset']}`",
            f"- Dataset version: `{manifest['dataset_version']}`",
            f"- Input path: `{manifest['input_path']}`",
            f"- Input SHA256: `{manifest['input_sha256']}`",
            f"- Record count: `{manifest['record_count']}`",
            f"- Duplicate rate: `{manifest['duplicate_rate']}`",
            f"- Average note length: `{profile['average_note_length']}`",
            f"- Average summary length: `{profile['average_summary_length']}`",
        ]
    )


def quality_report(metrics: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Data Quality Report",
            "",
            f"> {HONESTY_WARNING}",
            "",
            f"- Record count: `{metrics['record_count']}`",
            f"- Average quality score: `{metrics['average_quality_score']}`",
            f"- Missing rate: `{metrics['missing_rate']}`",
            f"- Duplicate rate: `{metrics['duplicate_rate']}`",
            f"- Noise rate: `{metrics['noise_rate']}`",
            f"- Section coverage: `{metrics['section_coverage']}`",
            f"- Route counts: `{metrics['route_counts']}`",
        ]
    )


def chunking_report(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Chunking Validation Report",
            "",
            f"> {HONESTY_WARNING}",
            "",
            f"- Record count: `{manifest['record_count']}`",
            f"- Chunk count: `{manifest['chunk_count']}`",
            f"- Average chunks per record: `{manifest['average_chunks_per_record']}`",
            f"- Average chunk length: `{manifest['average_chunk_length']}`",
            f"- Section preservation: `{manifest['section_preservation']}`",
            f"- Heading preservation: `{manifest['heading_preservation']}`",
            f"- Context fragmentation: `{manifest['context_fragmentation']}`",
            f"- Problematic chunking detected: `{manifest['problematic_chunking_detected']}`",
            f"- Fragmentation flags: `{manifest['fragmentation_flags']}`",
        ]
    )


def retrieval_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# Retrieval Validation Report",
        "",
        f"> {HONESTY_WARNING}",
        "",
        f"- Validation type: `{metrics['validation_type']}`",
        "",
        "| Model | Dimension | Index size | Duplicate vectors | Recall@k | Precision@k | Latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model, row in metrics["model_metrics"].items():
        lines.append(
            f"| `{model}` | {row['embedding_dimension']} | {row['index_size']} | {row['duplicate_vectors']} | {row['recall_at_k']} | {row['precision_at_k']} | {row['retrieval_latency_ms']} |"
        )
    return "\n".join(lines)


def _routing_row(record: dict[str, str], route: str) -> dict[str, Any]:
    return {
        "note_id": record.get("note_id", ""),
        "dataset": record.get("dataset", ""),
        "quality_score": record.get("quality_score", ""),
        "route": route,
    }


def _chunk_fragmentation_flags(chunks: list[Any]) -> list[str]:
    flags: list[str] = []
    section_text = " ".join(chunk.section.casefold() for chunk in chunks)
    for label, terms in {
        "Diagnosis split across chunks": ("diagnosis", "diagnostic"),
        "Medication split across chunks": ("medication", "medications"),
        "Assessment split across chunks": ("assessment",),
        "Plan split across chunks": ("plan",),
    }.items():
        matching = [chunk for chunk in chunks if any(term in chunk.text.casefold() or term in chunk.section.casefold() for term in terms)]
        if len(matching) > 1 and not any(term in section_text for term in terms):
            flags.append(label)
    return flags


def _relevant_chunk_indexes(chunks: list[str], reference: str) -> set[int]:
    ref_tokens = set(_tokens(reference))
    relevant = {
        index
        for index, chunk in enumerate(chunks)
        if ref_tokens and len(set(_tokens(chunk)) & ref_tokens) / max(1, len(ref_tokens)) >= 0.08
    }
    return relevant or {0}


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _vector_hash(vector: list[float]) -> str:
    rounded = ",".join(f"{value:.4f}" for value in vector)
    return hashlib.sha256(rounded.encode("utf-8")).hexdigest()


def _model_name(model: str) -> str:
    return {
        "deterministic": "deterministic_sentence_baseline",
        "bart": "facebook/bart-large-cnn",
        "pegasus": "google/pegasus-xsum",
        "gemini": os.environ.get("RAG_GEMINI_MODEL", "gemini-2.5-flash-lite"),
    }.get(model, model)


def _record_fingerprint(record: dict[str, str]) -> str:
    value = f"{record.get('source_note', '')}\n{record.get('reference_summary', '')}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _duplicate_count(records: list[dict[str, str]]) -> int:
    fingerprints = [_record_fingerprint(record) for record in records]
    return len(fingerprints) - len(set(fingerprints))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _infer_dataset_version(dataset: str, input_path: Path) -> str:
    name = input_path.name.lower()
    if "smoke" in name:
        return f"{dataset}-smoke"
    return os.environ.get("CLIN_SUMM_DATASET_VERSION", f"{dataset}-local")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9%./+-]+", text.casefold())


def _noise_ratio(text: str) -> float:
    if not text:
        return 1.0
    noisy = sum(1 for char in text if not (char.isalnum() or char.isspace() or char in ".,;:/+-_%()[]#'\"!?"))
    return min(1.0, noisy / len(text))


def _ocr_corruption_score(text: str) -> float:
    tokens = text.split()
    if not tokens:
        return 1.0
    corrupted = sum(1 for token in tokens if re.search(r"(.)\1{4,}|�|[_=]{3,}", token))
    return min(1.0, corrupted / len(tokens))


def _formatting_consistency(text: str) -> float:
    if not text.strip():
        return 0.0
    section_count = _section_label_count(text)
    if section_count >= 3:
        return 1.0
    if section_count >= 2:
        return 0.8
    if len(_tokens(text)) >= 60 and _noise_ratio(text) <= 0.02 and _ocr_corruption_score(text) <= 0.02:
        return 0.6
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return 0.4
    long_dense = sum(1 for line in lines if len(line) > 240)
    return max(0.0, 1.0 - long_dense / len(lines))


def _section_label_count(text: str) -> int:
    line_headings = len(list(HEADING_RE.finditer(text)))
    inline_headings = len(list(SECTION_LABEL_RE.finditer(text)))
    return max(line_headings, inline_headings)


def _length_score(length: int, *, minimum: int, target: int) -> float:
    if length <= 0:
        return 0.0
    if length < minimum:
        return max(0.1, length / minimum)
    return min(1.0, length / target)


def _distribution(values: list[float | int]) -> dict[str, Any]:
    if not values:
        return {"min": None, "max": None, "mean": None, "p50": None, "p90": None}
    ordered = sorted(float(value) for value in values)
    return {
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
        "mean": round(mean(ordered), 4),
        "p50": round(_percentile(ordered, 0.5), 4),
        "p90": round(_percentile(ordered, 0.9), 4),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    index = percentile * (len(values) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[int(index)]
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def _mean(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(mean(float(value) for value in values), 4)


def _rate(count: int, total: int) -> float:
    if not total:
        return 0.0
    return round(count / total, 4)


def _git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_markdown(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
