from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from backend.app.config import Settings
from backend.app.schemas import ClinicalDocument, EvidenceChunk
from backend.app.services.chunking import ClinicalChunker, HEADING_RE
from backend.app.services.embeddings import (
    EmbeddingProvider,
    FastEmbedProvider,
    HashingEmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
    TOKEN_RE,
)
from evaluation.data_governance.layers import HONESTY_WARNING, configure_d_drive_environment
from src.data.dataset_loader import load_jsonl_dataset


DEFAULT_OUTPUT_DIR = Path("outputs/evaluation/retrieval_audit")
DEFAULT_MODELS = (
    "current",
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "BAAI/bge-small-en-v1.5",
    "BAAI/bge-base-en-v1.5",
    "intfloat/e5-base-v2",
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
SPLIT_PATTERNS = {
    "Diagnosis split across chunks": re.compile(r"\b(diagnosis|diagnostic|diagnosed|impression)\b", re.IGNORECASE),
    "Medication split across chunks": re.compile(
        r"\b(medication|medications|drug|dose|treated with|therapy|antibiotic|albuterol|ciprofloxacin|isoniazid|rifampicin|ethambutol|pyrazinamide)\b",
        re.IGNORECASE,
    ),
    "Assessment split across chunks": re.compile(r"\b(assessment|clinical impression|clinical suspicion)\b", re.IGNORECASE),
    "Plan split across chunks": re.compile(r"\b(plan|follow[- ]?up|continue|monitor|discharged|referred)\b", re.IGNORECASE),
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "his",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


@dataclass(frozen=True)
class AuditConfig:
    input_path: Path
    dataset: str = "multiclinsum"
    limit: int | None = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    allow_model_downloads: bool = False
    models: tuple[str, ...] = DEFAULT_MODELS


@dataclass(frozen=True)
class ChunkAudit:
    chunks_by_note: dict[str, list[EvidenceChunk]]
    chunk_metrics: dict[str, Any]
    chunk_samples: list[dict[str, Any]]


@dataclass(frozen=True)
class ProviderPlan:
    label: str
    provider: EmbeddingProvider | None
    model_name: str
    status: str
    message: str = ""
    load_time_ms: float | None = None
    model_memory_mb: float | None = None


def run_retrieval_audit(config: AuditConfig) -> dict[str, Any]:
    cache_paths = configure_d_drive_environment()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    records = load_jsonl_dataset(
        config.input_path,
        dataset=config.dataset,
        split="test",
        require_reference=True,
        max_records=config.limit,
    )
    if not records:
        raise ValueError(f"No usable records found in {config.input_path}")

    chunk_audit = audit_chunking(records)
    provider_plans = [_build_provider(label, config, cache_paths) for label in config.models]
    retrieval_results = [
        benchmark_provider(plan, chunk_audit.chunks_by_note, records) for plan in provider_plans
    ]
    ranked_results = rank_embedding_results(retrieval_results)
    recommended = recommend_default_model(ranked_results)
    bottleneck = identify_bottleneck(chunk_audit.chunk_metrics, retrieval_results)
    opportunities = rank_improvement_opportunities(chunk_audit.chunk_metrics, retrieval_results, bottleneck)

    write_jsonl(config.output_dir / "chunk_samples.jsonl", chunk_audit.chunk_samples)
    write_comparison_csv(config.output_dir / "retrieval_model_comparison.csv", ranked_results)
    write_markdown(config.output_dir / "chunking_report.md", build_chunking_report(config, chunk_audit.chunk_metrics))
    write_markdown(
        config.output_dir / "retrieval_report.md",
        build_retrieval_report(config, cache_paths, ranked_results, bottleneck, opportunities, recommended),
    )
    write_markdown(
        config.output_dir / "EMBEDDING_EVALUATION_REPORT.md",
        build_embedding_evaluation_report(config, cache_paths, ranked_results, bottleneck, opportunities, recommended),
    )
    write_json(
        config.output_dir / "retrieval_audit_manifest.json",
        {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "input_path": str(config.input_path),
            "dataset": config.dataset,
            "limit": config.limit,
            "output_dir": str(config.output_dir),
            "allow_model_downloads": config.allow_model_downloads,
            "models": list(config.models),
            "cache_paths": cache_paths,
            "honesty_warning": HONESTY_WARNING,
            "outputs": {
                "chunking_report": "chunking_report.md",
                "chunk_samples": "chunk_samples.jsonl",
                "retrieval_report": "retrieval_report.md",
                "embedding_evaluation_report": "EMBEDDING_EVALUATION_REPORT.md",
                "model_comparison": "retrieval_model_comparison.csv",
            },
        },
    )
    return {
        "output_dir": str(config.output_dir),
        "chunk_metrics": chunk_audit.chunk_metrics,
        "retrieval_results": ranked_results,
        "bottleneck": bottleneck,
        "opportunities": opportunities,
        "recommended_model": recommended,
    }


def audit_chunking(records: list[dict[str, str]]) -> ChunkAudit:
    settings = Settings()
    chunker = ClinicalChunker(settings.chunk_max_chars, settings.chunk_overlap_sentences)
    chunks_by_note: dict[str, list[EvidenceChunk]] = {}
    samples: list[dict[str, Any]] = []
    all_lengths: list[int] = []
    chunk_counts: list[int] = []
    overlap_ratios: list[float] = []
    preserved_sections = 0
    sectioned_records = 0
    split_counts = {label: 0 for label in SPLIT_PATTERNS}

    for record in records:
        note_id = record.get("note_id") or "unknown_note"
        document = ClinicalDocument(
            document_id=note_id,
            document_type="evaluation_source_note",
            title=f"{record.get('dataset', 'dataset')} source note",
            encounter_id=record.get("encounter_id"),
            text=record.get("source_note", ""),
        )
        chunks = chunker.chunk_document("retrieval-audit", record.get("patient_id", "patient"), document)
        chunks_by_note[note_id] = chunks
        chunk_counts.append(len(chunks))
        all_lengths.extend(len(chunk.text.split()) for chunk in chunks)
        overlap_ratios.extend(_chunk_overlap_ratios(chunks))
        source_sections = _source_section_labels(document.text)
        if source_sections:
            sectioned_records += 1
            chunk_sections = {chunk.section.casefold() for chunk in chunks}
            if source_sections & chunk_sections:
                preserved_sections += 1
        for label, pattern in SPLIT_PATTERNS.items():
            if _pattern_split_across_chunks(chunks, pattern):
                split_counts[label] += 1
        for index, chunk in enumerate(chunks[:5]):
            samples.append(
                {
                    "note_id": note_id,
                    "chunk_index": index,
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "token_length": len(chunk.text.split()),
                    "text_preview": chunk.text[:500],
                }
            )

    chunk_metrics = {
        "record_count": len(records),
        "chunk_count": sum(chunk_counts),
        "average_chunks_per_record": _mean(chunk_counts),
        "average_chunk_length": _mean(all_lengths),
        "median_chunk_length": _median(all_lengths),
        "min_chunk_length": min(all_lengths) if all_lengths else None,
        "max_chunk_length": max(all_lengths) if all_lengths else None,
        "overlap_ratio": _mean(overlap_ratios),
        "configured_overlap_sentences": Settings().chunk_overlap_sentences,
        "section_preservation": _rate(preserved_sections, sectioned_records) if sectioned_records else None,
        "sectioned_record_count": sectioned_records,
        "split_flags": split_counts,
        "records_with_any_split_flag": sum(1 for note_chunks in chunks_by_note.values() if any(_pattern_split_across_chunks(note_chunks, pattern) for pattern in SPLIT_PATTERNS.values())),
        "honesty_warning": HONESTY_WARNING,
    }
    return ChunkAudit(chunks_by_note=chunks_by_note, chunk_metrics=chunk_metrics, chunk_samples=samples)


def _build_provider(label: str, config: AuditConfig, cache_paths: dict[str, str]) -> ProviderPlan:
    normalized = label.strip()
    if normalized.casefold() == "current":
        settings = Settings()
        try:
            before_mb = _rss_memory_mb()
            started = time.perf_counter()
            if settings.embedding_provider == "fastembed":
                provider: EmbeddingProvider = FastEmbedProvider(
                    settings.fastembed_model,
                    settings.ort_execution_provider,
                    settings.ort_intra_op_threads,
                )
                return ProviderPlan(
                    "current",
                    provider,
                    settings.fastembed_model,
                    "available",
                    load_time_ms=round((time.perf_counter() - started) * 1000, 4),
                    model_memory_mb=_memory_delta(before_mb),
                )
            provider = HashingEmbeddingProvider(settings.embedding_dimension)
            return ProviderPlan(
                "current",
                provider,
                provider.name,
                "available",
                load_time_ms=round((time.perf_counter() - started) * 1000, 4),
                model_memory_mb=_memory_delta(before_mb),
            )
        except Exception as exc:
            return ProviderPlan("current", None, settings.fastembed_model, "unavailable", str(exc))
    model_name = _canonical_model_name(normalized)
    if model_name:
        try:
            before_mb = _rss_memory_mb()
            started = time.perf_counter()
            provider = SentenceTransformersEmbeddingProvider(
                model_name,
                cache_folder=cache_paths.get("HF_HOME"),
                local_files_only=not config.allow_model_downloads,
            )
            return ProviderPlan(
                model_name,
                provider,
                model_name,
                "available",
                load_time_ms=round((time.perf_counter() - started) * 1000, 4),
                model_memory_mb=_memory_delta(before_mb),
            )
        except Exception as exc:
            message = str(exc)
            if not config.allow_model_downloads:
                message = f"{message} Model downloads are disabled; pass --allow-model-downloads to fetch intentionally."
            return ProviderPlan(model_name, None, model_name, "unavailable", message)
    raise ValueError(f"Unsupported retrieval model '{label}'")


def _canonical_model_name(label: str) -> str | None:
    aliases = {
        "all-minilm-l6-v2": "sentence-transformers/all-MiniLM-L6-v2",
        "sentence-transformers/all-minilm-l6-v2": "sentence-transformers/all-MiniLM-L6-v2",
        "paraphrase-multilingual-minilm-l12-v2": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "sentence-transformers/paraphrase-multilingual-minilm-l12-v2": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "baai/bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
        "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
        "baai/bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
        "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
        "intfloat/e5-base-v2": "intfloat/e5-base-v2",
        "e5-base-v2": "intfloat/e5-base-v2",
    }
    return aliases.get(label.casefold())


def benchmark_provider(
    plan: ProviderPlan,
    chunks_by_note: dict[str, list[EvidenceChunk]],
    records: list[dict[str, str]],
) -> dict[str, Any]:
    if plan.provider is None:
        return {
            "model_label": plan.label,
            "model_name": plan.model_name,
            "status": plan.status,
            "message": plan.message,
            "embedding_dimension": None,
            "index_size": 0,
            "load_time_ms": plan.load_time_ms,
            "indexing_time_ms": None,
            "model_memory_mb": plan.model_memory_mb,
            "index_memory_mb": None,
            "memory_usage_mb": plan.model_memory_mb,
            "retrieval_latency_ms": None,
            "recall_at_1": None,
            "recall_at_3": None,
            "recall_at_5": None,
            "recall_at_10": None,
            "mrr": None,
            "ndcg": None,
        }

    chunk_texts = [chunk.text for chunks in chunks_by_note.values() for chunk in chunks]
    started = time.perf_counter()
    vectors = plan.provider.embed_documents(chunk_texts) if chunk_texts else []
    build_latency_ms = (time.perf_counter() - started) * 1000
    vector_by_chunk: dict[str, list[float]] = {}
    offset = 0
    for chunks in chunks_by_note.values():
        for chunk in chunks:
            vector_by_chunk[chunk.chunk_id] = vectors[offset]
            offset += 1

    recalls = {1: [], 3: [], 5: [], 10: []}
    mrr_values: list[float] = []
    ndcg_values: list[float] = []
    latencies: list[float] = []

    for record in records:
        note_id = record.get("note_id", "")
        chunks = chunks_by_note.get(note_id, [])
        if not chunks:
            continue
        relevance = _graded_relevance(chunks, record.get("reference_summary", ""))
        relevant_ids = {chunk_id for chunk_id, score in relevance.items() if score > 0}
        started = time.perf_counter()
        query_vector = plan.provider.embed_query(record.get("reference_summary", ""))
        scored = sorted(
            (
                (chunk, _cosine(query_vector, vector_by_chunk[chunk.chunk_id]))
                for chunk in chunks
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        latencies.append((time.perf_counter() - started) * 1000)
        ranked_ids = [chunk.chunk_id for chunk, _score in scored]
        for k in recalls:
            recalls[k].append(_recall_at_k(ranked_ids, relevant_ids, k))
        mrr_values.append(_mrr(ranked_ids, relevant_ids))
        ndcg_values.append(_ndcg(ranked_ids, relevance, 10))

    return {
        "model_label": plan.label,
        "model_name": plan.model_name,
        "status": "completed",
        "message": "",
        "embedding_dimension": plan.provider.dimension,
        "index_size": len(chunk_texts),
        "load_time_ms": plan.load_time_ms,
        "indexing_time_ms": round(build_latency_ms, 4),
        "index_build_latency_ms": round(build_latency_ms, 4),
        "model_memory_mb": plan.model_memory_mb,
        "index_memory_mb": _index_memory_mb(vectors),
        "memory_usage_mb": _sum_optional(plan.model_memory_mb, _index_memory_mb(vectors)),
        "retrieval_latency_ms": _mean(latencies),
        "recall_at_1": _mean(recalls[1]),
        "recall_at_3": _mean(recalls[3]),
        "recall_at_5": _mean(recalls[5]),
        "recall_at_10": _mean(recalls[10]),
        "mrr": _mean(mrr_values),
        "ndcg": _mean(ndcg_values),
    }


def identify_bottleneck(chunk_metrics: dict[str, Any], retrieval_results: list[dict[str, Any]]) -> str:
    if chunk_metrics["record_count"] == 0 or chunk_metrics["chunk_count"] == 0:
        return "DATA"
    if chunk_metrics["min_chunk_length"] is not None and chunk_metrics["min_chunk_length"] < 8:
        return "CHUNKING"
    if chunk_metrics["max_chunk_length"] is not None and chunk_metrics["max_chunk_length"] > 450:
        return "CHUNKING"
    completed = [row for row in retrieval_results if row.get("status") == "completed"]
    if not completed:
        return "EMBEDDING"
    best_recall_3 = max(float(row.get("recall_at_3") or 0.0) for row in completed)
    best_mrr = max(float(row.get("mrr") or 0.0) for row in completed)
    current = next((row for row in completed if row["model_label"] == "current"), None)
    if best_recall_3 < 0.7 or best_mrr < 0.5:
        return "RETRIEVAL"
    if current and any(
        (row.get("recall_at_3") or 0.0) > (current.get("recall_at_3") or 0.0) + 0.1
        for row in completed
        if row["model_label"] != "current"
    ):
        return "EMBEDDING"
    return "SUMMARIZATION MODEL"


def rank_improvement_opportunities(
    chunk_metrics: dict[str, Any],
    retrieval_results: list[dict[str, Any]],
    bottleneck: str,
) -> list[dict[str, str]]:
    opportunities: list[dict[str, str]] = []
    if bottleneck == "EMBEDDING":
        best = recommend_default_model(retrieval_results)
        best_name = best["model_name"] if best else "the best ranked production embedder"
        opportunities.append(
            {
                "rank": str(len(opportunities) + 1),
                "area": "EMBEDDING",
                "expected_impact": "High",
                "action": f"Replace the development hashing embedder with {best_name} for evaluation; production embeddings improved Recall@3 on the audit set.",
            }
        )
    if bottleneck in {"DATA", "CHUNKING"} or chunk_metrics.get("section_preservation") == 0:
        opportunities.append(
            {
                "rank": str(len(opportunities) + 1),
                "area": "CHUNKING",
                "expected_impact": "High",
                "action": "Normalize clinical headings before chunking and add prose-aware section fallback for open proxy datasets.",
            }
        )
    completed = [row for row in retrieval_results if row.get("status") == "completed"]
    unavailable = [row for row in retrieval_results if row.get("status") != "completed"]
    current = next((row for row in completed if row["model_label"] == "current"), None)
    if unavailable:
        opportunities.append(
            {
                "rank": str(len(opportunities) + 1),
                "area": "EMBEDDING",
                "expected_impact": "Medium",
                "action": "Run the MiniLM comparison with cached or explicitly downloaded models before selecting an embedding backend.",
            }
        )
    if chunk_metrics.get("section_preservation") is None:
        opportunities.append(
            {
                "rank": str(len(opportunities) + 1),
                "area": "DATA",
                "expected_impact": "Medium",
                "action": "Run the same audit on sectioned clinical-note proxy data before generalizing from MultiClinSum case-report prose.",
            }
        )
    if current and (current.get("recall_at_3") or 0.0) < 0.8:
        opportunities.append(
            {
                "rank": str(len(opportunities) + 1),
                "area": "RETRIEVAL",
                "expected_impact": "High",
                "action": "Tune chunk size, query construction, and hybrid lexical/vector ranking before large summarizer benchmarks.",
            }
        )
    opportunities.append(
        {
            "rank": str(len(opportunities) + 1),
            "area": "SUMMARIZATION MODEL",
            "expected_impact": "Conditional",
            "action": "Run BART/Pegasus only after retrieval Recall@3 and MRR are acceptable on the proxy retrieval audit.",
        }
    )
    return opportunities


def rank_embedding_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row.get("status") == "completed"]
    max_latency = max((float(row.get("retrieval_latency_ms") or 0.0) for row in completed), default=0.0)
    max_memory = max((float(row.get("memory_usage_mb") or 0.0) for row in completed), default=0.0)
    ranked: list[dict[str, Any]] = []
    for row in rows:
        quality_score = _quality_score(row)
        latency_score = _inverse_score(row.get("retrieval_latency_ms"), max_latency)
        memory_score = _inverse_score(row.get("memory_usage_mb"), max_memory)
        if row.get("status") != "completed":
            total = 0.0
        else:
            total = 0.72 * quality_score + 0.18 * latency_score + 0.10 * memory_score
        ranked.append(
            {
                **row,
                "quality_score": round(quality_score, 6),
                "latency_score": round(latency_score, 6),
                "memory_score": round(memory_score, 6),
                "rank_score": round(total, 6),
            }
        )
    production = [
        row for row in ranked if row.get("status") == "completed" and row.get("model_label") != "current"
    ]
    production.sort(
        key=lambda item: (
            item["rank_score"],
            item.get("recall_at_3") or 0,
            -(item.get("retrieval_latency_ms") or 999999),
        ),
        reverse=True,
    )
    for index, row in enumerate(production, start=1):
        row["rank"] = index
    current = [row for row in ranked if row.get("model_label") == "current"]
    for row in current:
        row["rank"] = "dev-baseline"
    unavailable = [row for row in ranked if row.get("status") != "completed" and row.get("model_label") != "current"]
    for row in unavailable:
        row["rank"] = None
    return production + current + unavailable


def recommend_default_model(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    completed = [row for row in rows if row.get("status") == "completed" and row.get("model_label") != "current"]
    if not completed:
        return next((row for row in rows if row.get("status") == "completed"), None)
    return completed[0]


def _quality_score(row: dict[str, Any]) -> float:
    if row.get("status") != "completed":
        return 0.0
    return (
        0.25 * float(row.get("recall_at_1") or 0.0)
        + 0.28 * float(row.get("recall_at_3") or 0.0)
        + 0.12 * float(row.get("recall_at_5") or 0.0)
        + 0.05 * float(row.get("recall_at_10") or 0.0)
        + 0.15 * float(row.get("mrr") or 0.0)
        + 0.15 * float(row.get("ndcg") or 0.0)
    )


def _inverse_score(value: Any, worst: float) -> float:
    if value is None or worst <= 0:
        return 0.0
    numeric = float(value)
    return max(0.0, min(1.0, 1.0 - (numeric / worst)))


def build_chunking_report(config: AuditConfig, metrics: dict[str, Any]) -> str:
    split_lines = [f"- {label}: `{count}` records" for label, count in metrics["split_flags"].items()]
    return "\n".join(
        [
            "# Chunking Report",
            "",
            f"> {HONESTY_WARNING}",
            "",
            "## Configuration",
            "",
            f"- Dataset: `{config.dataset}`",
            f"- Input: `{config.input_path}`",
            f"- Limit: `{config.limit if config.limit is not None else 'all'}`",
            f"- Chunk max chars: `{Settings().chunk_max_chars}`",
            f"- Configured overlap sentences: `{metrics['configured_overlap_sentences']}`",
            "",
            "## Measurements",
            "",
            f"- Chunk count: `{metrics['chunk_count']}`",
            f"- Average chunks per record: `{metrics['average_chunks_per_record']}`",
            f"- Average chunk length: `{metrics['average_chunk_length']}` tokens",
            f"- Median chunk length: `{metrics['median_chunk_length']}` tokens",
            f"- Min chunk length: `{metrics['min_chunk_length']}` tokens",
            f"- Max chunk length: `{metrics['max_chunk_length']}` tokens",
            f"- Overlap ratio: `{metrics['overlap_ratio']}`",
            f"- Section preservation: `{_display(metrics['section_preservation'])}`",
            f"- Sectioned record count: `{metrics['sectioned_record_count']}`",
            "",
            "## Split Detection",
            "",
            *split_lines,
            "",
            "## Notes",
            "",
            "Section preservation is not applicable when the source record has no recognizable section headings. "
            "Open proxy datasets such as MultiClinSum often use case-report prose, so weak section preservation there is a data-format signal rather than proof that the chunker is broken for EHR notes.",
            "",
            "Chunk samples are written to `chunk_samples.jsonl` with short previews only.",
        ]
    )


def build_retrieval_report(
    config: AuditConfig,
    cache_paths: dict[str, str],
    results: list[dict[str, Any]],
    bottleneck: str,
    opportunities: list[dict[str, str]],
    recommended: dict[str, Any] | None,
) -> str:
    lines = [
        "# Retrieval Report",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Executive Summary",
        "",
        f"- Identified bottleneck: `{bottleneck}`",
        f"- Recommended embedding model: `{recommended['model_name'] if recommended else 'not_available'}`",
        f"- Should we improve chunking? `{_yes_no(bottleneck in {'DATA', 'CHUNKING', 'RETRIEVAL'})}`",
        f"- Should we change embeddings? `{_yes_no(bottleneck in {'EMBEDDING', 'RETRIEVAL'})}`",
        f"- Should we run BART/Pegasus now? `{_bart_pegasus_decision(bottleneck, results, recommended)}`",
        "",
        "This audit uses proxy relevance labels derived from overlap between each reference summary and chunks from the same source note. It is useful for finding retrieval bottlenecks before summarizer benchmarking, but it is not a clinical citation benchmark.",
        "",
        "## Embedding Configuration",
        "",
        f"- Current provider from settings: `{Settings().embedding_provider}`",
        f"- Current FastEmbed model setting: `{Settings().fastembed_model}`",
        f"- HF_HOME: `{cache_paths.get('HF_HOME')}`",
        f"- Model downloads allowed: `{config.allow_model_downloads}`",
        "",
        "## Retrieval Metrics",
        "",
        "| Rank | Model | Status | Dimension | Index size | Index ms | Query ms | Memory MB | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | nDCG@10 | Score | Notes |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in results:
        lines.append(
            "| {rank} | {model} | {status} | {dim} | {size} | {index_ms} | {latency} | {memory} | {r1} | {r3} | {r5} | {r10} | {mrr} | {ndcg} | {score} | {notes} |".format(
                rank=_display(row.get("rank")),
                model=row["model_label"],
                status=row["status"],
                dim=_display(row.get("embedding_dimension")),
                size=_display(row.get("index_size")),
                index_ms=_display(row.get("indexing_time_ms")),
                latency=_display(row.get("retrieval_latency_ms")),
                memory=_display(row.get("memory_usage_mb")),
                r1=_display(row.get("recall_at_1")),
                r3=_display(row.get("recall_at_3")),
                r5=_display(row.get("recall_at_5")),
                r10=_display(row.get("recall_at_10")),
                mrr=_display(row.get("mrr")),
                ndcg=_display(row.get("ndcg")),
                score=_display(row.get("rank_score")),
                notes=_table_cell(row.get("message") or ""),
            )
        )
    lines.extend(["", "## Improvement Opportunities", ""])
    lines.extend(
        f"{item['rank']}. `{item['area']}` ({item['expected_impact']}): {item['action']}"
        for item in opportunities
    )
    lines.extend(
        [
            "",
            "## Bottleneck Decision Rules",
            "",
            "- `DATA`: no usable records or no chunks.",
            "- `CHUNKING`: pathological chunk lengths or obvious split/section failures.",
            "- `EMBEDDING`: current embedder is unavailable or a stronger embedder clearly improves retrieval.",
            "- `RETRIEVAL`: best available Recall@3 or MRR is still weak.",
            "- `SUMMARIZATION MODEL`: retrieval is acceptable, so summarizer quality is the next likely bottleneck.",
        ]
    )
    return "\n".join(lines)


def build_embedding_evaluation_report(
    config: AuditConfig,
    cache_paths: dict[str, str],
    results: list[dict[str, Any]],
    bottleneck: str,
    opportunities: list[dict[str, str]],
    recommended: dict[str, Any] | None,
) -> str:
    recommendation = recommended["model_name"] if recommended else "not_available"
    can_benchmark = _retrieval_sufficient_for_summarization(recommended)
    lines = [
        "# Embedding Evaluation Report",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Executive Decision",
        "",
        f"- Recommended default embedding model for the Medical Record Summarization MVP: `{recommendation}`",
        f"- Which embedding model should be used for the next large-scale benchmark? `{recommendation}`",
        f"- Is retrieval quality sufficient to begin BART/Pegasus evaluation? `{_yes_no(can_benchmark)} after switching to the recommended embedding model`",
        f"- Current bottleneck classification: `{bottleneck}`",
        "",
        "Recommendation rationale: choose the highest ranked non-development embedding model, prioritizing Recall@3/MRR/nDCG over latency and memory. The current hashing embedder remains development-only and should not be the default for benchmark claims.",
        "",
        "## Current Retrieval Implementation",
        "",
        "- Embeddings are generated in `backend/app/services/embeddings.py`.",
        "- Runtime indexing is orchestrated by `RagService.ingest()` in `backend/app/services/rag.py`.",
        "- Chunks are generated by `ClinicalChunker` before embeddings are computed.",
        "- Vectors are upserted into `QdrantVectorStore`; retrieval embeds the query and uses cosine scoring through Qdrant.",
        "- Configurable providers now include `hashing`, `fastembed`, and `sentence_transformers`.",
        "",
        "## Benchmark Setup",
        "",
        f"- Dataset: `{config.dataset}`",
        f"- Input: `{config.input_path}`",
        f"- Limit: `{config.limit if config.limit is not None else 'all'}`",
        f"- HF cache: `{cache_paths.get('HF_HOME')}`",
        f"- Downloaded models stored on D drive: `{cache_paths.get('HF_HOME')}`",
        f"- Fresh in-memory vector index generated for each embedding model: `yes`",
        "",
        "## Model Ranking",
        "",
        "| Rank | Model | Dimension | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | nDCG@10 | Query ms | Memory MB | Rank score |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in results:
        if row.get("status") != "completed":
            continue
        lines.append(
            "| {rank} | {model} | {dim} | {r1} | {r3} | {r5} | {r10} | {mrr} | {ndcg} | {latency} | {memory} | {score} |".format(
                rank=row.get("rank"),
                model=row.get("model_label"),
                dim=row.get("embedding_dimension"),
                r1=row.get("recall_at_1"),
                r3=row.get("recall_at_3"),
                r5=row.get("recall_at_5"),
                r10=row.get("recall_at_10"),
                mrr=row.get("mrr"),
                ndcg=row.get("ndcg"),
                latency=row.get("retrieval_latency_ms"),
                memory=row.get("memory_usage_mb"),
                score=row.get("rank_score"),
            )
        )
    lines.extend(
        [
            "",
            "## Remaining Retrieval Improvements Before Real EHR Datasets",
            "",
            "- Re-run this benchmark on sectioned clinical-note proxy data and, later, governed MIMIC-IV-Note/MIMIC-IV-BHC.",
            "- Add gold citation-span labels when available; current relevance labels are proxy lexical-overlap labels.",
            "- Validate patient-level filtering and wrong-patient retrieval resistance at realistic index sizes.",
            "- Consider hybrid lexical plus dense retrieval for medication names, abbreviations, labs, and rare diagnoses.",
            "- Re-tune chunk size/overlap on real discharge summaries and progress notes.",
            "",
            "## Improvement Opportunities",
            "",
        ]
    )
    lines.extend(
        f"{item['rank']}. `{item['area']}` ({item['expected_impact']}): {item['action']}"
        for item in opportunities
    )
    return "\n".join(lines)


def _retrieval_sufficient_for_summarization(recommended: dict[str, Any] | None) -> bool:
    if not recommended:
        return False
    return (
        (recommended.get("recall_at_3") or 0.0) >= 0.9
        and (recommended.get("mrr") or 0.0) >= 0.8
        and (recommended.get("ndcg") or 0.0) >= 0.85
    )


def _graded_relevance(chunks: list[EvidenceChunk], reference: str) -> dict[str, float]:
    ref_tokens = set(_informative_tokens(reference))
    scores: dict[str, float] = {}
    best_score = 0.0
    best_chunk_id = chunks[0].chunk_id if chunks else ""
    for chunk in chunks:
        chunk_tokens = set(_informative_tokens(chunk.text))
        score = len(ref_tokens & chunk_tokens) / max(1, len(ref_tokens))
        if score > best_score:
            best_score = score
            best_chunk_id = chunk.chunk_id
        scores[chunk.chunk_id] = round(score, 6) if score >= 0.08 else 0.0
    if best_chunk_id and not any(score > 0 for score in scores.values()):
        scores[best_chunk_id] = round(best_score, 6) or 1.0
    return scores


def _informative_tokens(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.casefold()) if len(token) > 2 and token not in STOPWORDS]


def _recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return round(len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids), 6)


def _mrr(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    for index, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in relevant_ids:
            return round(1.0 / index, 6)
    return 0.0


def _ndcg(ranked_ids: list[str], relevance: dict[str, float], k: int) -> float:
    gains = [relevance.get(chunk_id, 0.0) for chunk_id in ranked_ids[:k]]
    ideal = sorted(relevance.values(), reverse=True)[:k]
    dcg = sum((2**gain - 1) / math.log2(index + 2) for index, gain in enumerate(gains))
    idcg = sum((2**gain - 1) / math.log2(index + 2) for index, gain in enumerate(ideal))
    return round(dcg / idcg, 6) if idcg else 0.0


def _source_section_labels(text: str) -> set[str]:
    line_headings = {match.group("header").casefold() for match in HEADING_RE.finditer(text)}
    inline_headings = {match.group(1).casefold() for match in SECTION_LABEL_RE.finditer(text)}
    return line_headings | inline_headings


def _pattern_split_across_chunks(chunks: list[EvidenceChunk], pattern: re.Pattern[str]) -> bool:
    matching = [chunk for chunk in chunks if pattern.search(f"{chunk.section} {chunk.text}")]
    return len(matching) > 1


def _chunk_overlap_ratios(chunks: list[EvidenceChunk]) -> list[float]:
    ratios: list[float] = []
    ordered = sorted(chunks, key=lambda chunk: (chunk.document_id, chunk.char_start, chunk.char_end))
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous.document_id != current.document_id:
            continue
        overlap = max(0, min(previous.char_end, current.char_end) - max(previous.char_start, current.char_start))
        denominator = max(1, current.char_end - current.char_start)
        ratios.append(round(overlap / denominator, 6))
    return ratios or [0.0]


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _mean(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(mean(float(value) for value in values), 4)


def _median(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(float(median(values)), 4)


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _display(value: Any) -> str:
    if value is None or value == "":
        return "not_available"
    return str(value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _bart_pegasus_decision(
    bottleneck: str,
    results: list[dict[str, Any]],
    recommended: dict[str, Any] | None,
) -> str:
    comparison_unavailable = any(row.get("status") != "completed" for row in results if row.get("model_label") != "current")
    if _retrieval_sufficient_for_summarization(recommended):
        return "yes after switching to the recommended embedding model"
    if bottleneck != "SUMMARIZATION MODEL":
        return "no"
    if comparison_unavailable:
        return "small controlled run yes; large-scale run after embedding comparison"
    return "yes"


def _table_cell(value: Any) -> str:
    compact = re.sub(r"\s+", " ", str(value)).replace("|", "/").strip()
    if len(compact) > 220:
        return compact[:217] + "..."
    return compact


def _rss_memory_mb() -> float | None:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def _memory_delta(before_mb: float | None) -> float | None:
    after_mb = _rss_memory_mb()
    if before_mb is None or after_mb is None:
        return None
    return round(max(0.0, after_mb - before_mb), 4)


def _index_memory_mb(vectors: list[list[float]]) -> float:
    if not vectors:
        return 0.0
    return round(sum(len(vector) for vector in vectors) * 4 / (1024 * 1024), 4)


def _sum_optional(*values: float | None) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return round(sum(numeric), 4)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_markdown(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "rank",
        "model_label",
        "model_name",
        "status",
        "embedding_dimension",
        "index_size",
        "load_time_ms",
        "indexing_time_ms",
        "retrieval_latency_ms",
        "model_memory_mb",
        "index_memory_mb",
        "memory_usage_mb",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "recall_at_10",
        "mrr",
        "ndcg",
        "quality_score",
        "latency_score",
        "memory_score",
        "rank_score",
        "message",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit chunking and retrieval before summarization benchmarks.")
    parser.add_argument("--input", required=True, help="Processed JSONL dataset path.")
    parser.add_argument("--dataset", default="multiclinsum")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--allow-model-downloads", action="store_true")
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="Comma-separated retrieval models to audit.",
    )
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> AuditConfig:
    return AuditConfig(
        input_path=Path(args.input),
        dataset=args.dataset,
        limit=args.limit,
        output_dir=Path(args.output_dir),
        allow_model_downloads=args.allow_model_downloads,
        models=tuple(item.strip() for item in args.models.split(",") if item.strip()),
    )


def main() -> None:
    result = run_retrieval_audit(config_from_args(parse_args()))
    print(f"Retrieval audit outputs written to {result['output_dir']}")
    print(f"Identified bottleneck: {result['bottleneck']}")


if __name__ == "__main__":
    main()
