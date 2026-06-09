from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.evaluation.citation_grounding import analyze_prediction_row, write_grounding_outputs
from backend.app.evaluation.clinical_context_builder import SECTION_QUERIES, build_clinical_context
from backend.app.evaluation.clinical_metrics import (
    PER_RECORD_CLINICAL_FIELDS,
    aggregate_clinical_metrics,
    compute_clinical_record_metrics,
    serialize_failure_categories,
)
from backend.app.evaluation.reproducibility import build_reproducibility_manifest, write_reproducibility_manifest
from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics
from backend.app.schemas import ClinicalDocument, EvidenceChunk, IngestRequest
from backend.app.services.chunking import ClinicalChunker
from backend.app.services.embeddings import SentenceTransformersEmbeddingProvider
from backend.app.services.vector_store import QdrantVectorStore
from src.data.dataset_loader import load_jsonl_dataset
from src.models import DeterministicSummarizer
from src.models.seq2seq import generate_seq2seq_summary, load_seq2seq_model


PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, "
    "or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as "
    "MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes."
)
DEFAULT_DATASET = Path("data/processed/governance/benchmark_set.jsonl")
DEFAULT_OUTPUT = Path("D:/clin_summ_outputs/rag_grounded_benchmark")
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_CHECKPOINTS = {
    "deterministic": "deterministic_context_baseline",
    "bart": "facebook/bart-large-cnn",
    "pegasus": "google/pegasus-xsum",
    "pegasus_pubmed": "google/pegasus-pubmed",
    "pegasus_cnn_dailymail": "google/pegasus-cnn_dailymail",
}


def main() -> None:
    args = parse_args()
    configure_environment(args.embedding_model)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    log_path.write_text("", encoding="utf-8")
    started = time.perf_counter()
    log(log_path, "Starting retrieval-grounded summarization benchmark.")
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

    embedding_provider = SentenceTransformersEmbeddingProvider(args.embedding_model, local_files_only=args.local_files_only)
    vector_store = QdrantVectorStore(
        f"rag_grounded_{int(time.time())}",
        embedding_provider.dimension,
        path=Path(args.qdrant_path) if args.qdrant_mode == "persistent" and args.qdrant_path else None,
    )
    chunker = ClinicalChunker(Settings().chunk_max_chars, Settings().chunk_overlap_sentences)

    retrieval_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    context_by_note: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        retrieval, evidence_payload, context_payload = build_record_context(
            record,
            chunker=chunker,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            top_k_per_query=args.top_k_per_query,
            max_context_chunks=args.max_context_chunks,
        )
        retrieval_rows.append(retrieval)
        evidence_rows.extend(evidence_payload)
        context_by_note[record["note_id"]] = context_payload
        if index % 10 == 0:
            log(log_path, f"Prepared retrieval contexts for {index}/{len(records)} records.")

    write_jsonl(output_dir / "retrieved_evidence.jsonl", evidence_rows)
    write_retrieval_metrics(output_dir / "retrieval_metrics.csv", retrieval_rows)

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
    grounding_paths = write_grounding_outputs(output_dir, [analyze_prediction_row(row) for row in all_predictions])
    comparison_rows = build_model_comparison(model_rows, include_bertscore=args.include_bertscore)
    write_model_comparison(output_dir / "model_comparison.csv", comparison_rows)
    runtime = round(time.perf_counter() - started, 4)
    manifest = build_manifest(args, records, comparison_rows, runtime, grounding_paths, retrieval_rows)
    write_json(output_dir / "rag_benchmark_manifest.json", manifest)
    write_reproducibility_manifest(output_dir / "reproducibility_manifest.json", manifest["reproducibility"])
    write_report(output_dir / "EVALUATION_REPORT.md", manifest, comparison_rows, retrieval_rows)
    log(log_path, f"Completed retrieval-grounded benchmark in {runtime} seconds.")
    print(f"RAG-grounded benchmark outputs written to {output_dir}")


def build_record_context(
    record: dict[str, str],
    *,
    chunker: ClinicalChunker,
    embedding_provider: SentenceTransformersEmbeddingProvider,
    vector_store: QdrantVectorStore,
    top_k_per_query: int,
    max_context_chunks: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    tenant_id = "rag-benchmark"
    patient_id = record.get("patient_id") or record["note_id"]
    document = ClinicalDocument(
        document_id=record["note_id"],
        document_type="benchmark-source-note",
        title=f"{record.get('dataset', 'benchmark')} source note",
        encounter_id=record.get("encounter_id"),
        text=record["source_note"],
        metadata={"dataset": record.get("dataset", ""), "split": record.get("split", "")},
    )
    chunks = chunker.chunk_document(tenant_id, patient_id, document)
    vectors = embedding_provider.embed_documents([chunk.text for chunk in chunks])
    vector_store.upsert(tenant_id, chunks, vectors)
    retrieval_started = time.perf_counter()
    retrieved_by_id: dict[str, EvidenceChunk] = {}
    query_payloads: list[dict[str, Any]] = []
    for section, query in SECTION_QUERIES.items():
        query_vector = embedding_provider.embed_query(f"{query}. {record.get('reference_summary', '')[:500]}")
        retrieved = vector_store.search(tenant_id, patient_id, query_vector, top_k_per_query)
        query_payloads.append(
            {
                "section": section,
                "query": query,
                "retrieved_chunk_ids": [chunk.chunk_id for chunk in retrieved],
                "scores": [round(float(chunk.score or 0.0), 6) for chunk in retrieved],
            }
        )
        for chunk in retrieved:
            retrieved_by_id[chunk.chunk_id] = chunk
    evidence = sorted(retrieved_by_id.values(), key=lambda chunk: float(chunk.score or 0.0), reverse=True)
    context = build_clinical_context(evidence, max_chunks=max_context_chunks)
    relevant_ids = relevant_chunk_ids(chunks, record.get("reference_summary", ""))
    ranked_ids = [chunk.chunk_id for chunk in evidence]
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 4)
    retrieval_row = {
        "note_id": record["note_id"],
        "patient_id": patient_id,
        "chunk_count": len(chunks),
        "retrieved_chunk_count": len(evidence),
        "context_chunk_count": len(context.evidence),
        "context_token_count": context.token_count,
        "recall_at_1": recall_at_k(ranked_ids, relevant_ids, 1),
        "recall_at_3": recall_at_k(ranked_ids, relevant_ids, 3),
        "recall_at_5": recall_at_k(ranked_ids, relevant_ids, 5),
        "mrr": reciprocal_rank(ranked_ids, relevant_ids),
        "ndcg_at_5": ndcg_at_k(ranked_ids, chunks, record.get("reference_summary", ""), 5),
        "retrieval_latency_ms": retrieval_ms,
        "section_counts": json.dumps(context.section_counts, ensure_ascii=False),
    }
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
            "query_retrieval": query_payloads,
        }
        for chunk in context.evidence
    ]
    context_payload = {
        "context_text": context.text,
        "evidence": context.evidence,
        "evidence_payload": evidence_payload,
        "retrieval": retrieval_row,
    }
    return retrieval_row, evidence_payload, context_payload


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
        if index % 10 == 0:
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
        "evaluation_type": "rag_grounded_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "stage": "rag_grounded",
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
        "reference_summary": record["reference_summary"],
        "generated_summary": generated_summary,
        "citations": citations,
        "latency_ms": latency_ms,
        "retrieval_latency_ms": context["retrieval"]["retrieval_latency_ms"],
        "context_token_count": context["retrieval"]["context_token_count"],
        "rouge1": metrics["rouge1"],
        "rouge2": metrics["rouge2"],
        "rougeL": metrics["rougeL"],
    }
    row.update(compute_clinical_record_metrics(row))
    return row


def failed_prediction_row(record: dict[str, str], context: dict[str, Any], provider: str, model_name: str, error: str) -> dict[str, Any]:
    return {
        "evaluation_type": "rag_grounded_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "stage": "rag_grounded",
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
        "reference_summary": record["reference_summary"],
        "generated_summary": "",
        "citations": [],
        "latency_ms": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
    }


def build_model_comparison(model_rows: dict[str, list[dict[str, Any]]], *, include_bertscore: bool) -> list[dict[str, Any]]:
    rows = []
    for provider, predictions in model_rows.items():
        completed = [row for row in predictions if row.get("status") == "completed"]
        failed = [row for row in predictions if row.get("status") == "failed"]
        metrics = (
            compute_pairwise_metrics(
                [row["generated_summary"] for row in completed],
                [row["reference_summary"] for row in completed],
                include_bertscore=include_bertscore,
            )
            if completed
            else {}
        )
        clinical = aggregate_clinical_metrics(predictions)
        rows.append(
            {
                "model_provider": provider,
                "model_name": MODEL_CHECKPOINTS[provider],
                "status": "completed" if completed and not failed else "partial" if completed else "failed",
                "record_count": len(predictions),
                "completed_count": len(completed),
                "failed_count": len(failed),
                "skipped_count": 0,
                "rouge1": metrics.get("rouge1"),
                "rouge2": metrics.get("rouge2"),
                "rougeL": metrics.get("rougeL"),
                "bertscore_precision": metrics.get("bertscore_precision"),
                "bertscore_recall": metrics.get("bertscore_recall"),
                "bertscore_f1": metrics.get("bertscore_f1"),
                "bertscore_status": metrics.get("bertscore_status", "not_requested" if not include_bertscore else "not_available"),
                "bertscore_model_type": metrics.get("bertscore_model_type"),
                "average_latency_ms": mean(row.get("latency_ms") for row in completed),
                **clinical,
                "notes": PROXY_WARNING,
                "error_message": "; ".join(sorted({str(row.get("error_message")) for row in failed if row.get("error_message")})) or None,
            }
        )
    return rows


def write_model_comparison(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "model_provider",
        "model_name",
        "status",
        "record_count",
        "completed_count",
        "failed_count",
        "skipped_count",
        "rouge1",
        "rouge2",
        "rougeL",
        "bertscore_precision",
        "bertscore_recall",
        "bertscore_f1",
        "bertscore_status",
        "bertscore_model_type",
        "average_latency_ms",
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
        "notes",
        "error_message",
    ]
    write_csv(path, rows, fields)


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
        "retrieval_latency_ms",
        "context_token_count",
        *PER_RECORD_CLINICAL_FIELDS,
        "error_message",
    ]
    serializable = []
    for row in rows:
        payload = {field: row.get(field) for field in fields}
        payload["failure_categories"] = serialize_failure_categories(row.get("failure_categories"))
        serializable.append(payload)
    write_csv(path, serializable, fields)


def write_per_record_failure_analysis(path: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        note_id = row.get("note_id", "")
        entry = grouped.setdefault(
            note_id,
            {
                "note_id": note_id,
                "patient_id": row.get("patient_id", ""),
                "encounter_id": row.get("encounter_id", ""),
                "dataset": row.get("dataset", ""),
                "input_note": row.get("source_note", ""),
                "reference_summary": row.get("reference_summary", ""),
                "retrieved_evidence": row.get("retrieved_evidence", ""),
                "citations": row.get("citations", []),
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
                "rougeL": row.get("rougeL"),
                "clinical_metrics": {field: row.get(field) for field in PER_RECORD_CLINICAL_FIELDS if field != "failure_categories"},
                "error_message": row.get("error_message"),
            }
        )
    write_jsonl(path, list(grouped.values()))


def write_retrieval_metrics(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "note_id",
        "patient_id",
        "chunk_count",
        "retrieved_chunk_count",
        "context_chunk_count",
        "context_token_count",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "retrieval_latency_ms",
        "section_counts",
    ]
    write_csv(path, rows, fields)


def build_manifest(
    args: argparse.Namespace,
    records: list[dict[str, str]],
    comparison_rows: list[dict[str, Any]],
    runtime: float,
    grounding_paths: dict[str, Any],
    retrieval_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    reproducibility = build_reproducibility_manifest(
        run_name="rag_grounded_benchmark",
        dataset_path=Path(args.dataset),
        output_dir=output_dir,
        model_checkpoints={provider: MODEL_CHECKPOINTS[provider] for provider in parse_models(args.models)}
        | {"retrieval_embedding": args.embedding_model},
        prompt_template_version="clinical_context_builder.v1",
        retrieval_config={
            "embedding_provider": "sentence_transformers",
            "embedding_model": args.embedding_model,
            "vector_store": "qdrant",
            "qdrant_mode": args.qdrant_mode,
            "top_k_per_query": args.top_k_per_query,
            "max_context_chunks": args.max_context_chunks,
            "clinical_sections": list(SECTION_QUERIES),
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
        "pipeline": "rag_grounded_benchmark",
        "proxy_warning": PROXY_WARNING,
        "input_path": str(args.dataset),
        "output_dir": str(output_dir),
        "records_loaded": len(records),
        "models": parse_models(args.models),
        "comparison_rows": comparison_rows,
        "retrieval_summary": {
            "average_chunks": mean(row["chunk_count"] for row in retrieval_rows),
            "average_retrieved_chunks": mean(row["retrieved_chunk_count"] for row in retrieval_rows),
            "average_context_tokens": mean(row["context_token_count"] for row in retrieval_rows),
            "average_recall_at_5": mean(row["recall_at_5"] for row in retrieval_rows),
            "average_mrr": mean(row["mrr"] for row in retrieval_rows),
            "average_ndcg_at_5": mean(row["ndcg_at_5"] for row in retrieval_rows),
        },
        "citation_grounding": grounding_paths,
        "runtime_seconds": runtime,
        "reproducibility": reproducibility,
    }


def write_report(path: Path, manifest: dict[str, Any], comparison_rows: list[dict[str, Any]], retrieval_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Retrieval-Grounded Summarization Benchmark",
        "",
        f"> {PROXY_WARNING}",
        "",
        "## Summary",
        "",
        f"- Records loaded: `{manifest['records_loaded']}`",
        f"- Runtime seconds: `{manifest['runtime_seconds']}`",
        f"- Retrieval embedding: `{manifest['reproducibility']['retrieval_config']['embedding_model']}`",
        f"- Vector store: `Qdrant ({manifest['reproducibility']['retrieval_config']['qdrant_mode']})`",
        "",
        "## Retrieval Metrics",
        "",
        f"- Average chunks per record: `{manifest['retrieval_summary']['average_chunks']}`",
        f"- Average retrieved chunks: `{manifest['retrieval_summary']['average_retrieved_chunks']}`",
        f"- Average context tokens: `{manifest['retrieval_summary']['average_context_tokens']}`",
        f"- Average Recall@5 proxy: `{manifest['retrieval_summary']['average_recall_at_5']}`",
        f"- Average MRR proxy: `{manifest['retrieval_summary']['average_mrr']}`",
        f"- Average nDCG@5 proxy: `{manifest['retrieval_summary']['average_ndcg_at_5']}`",
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
            "- This benchmark uses retrieved evidence context instead of raw full source notes.",
            "- Retrieval labels are proxy labels derived from reference-summary token overlap with chunks.",
            "- Citation metrics indicate whether generated claims are covered by retrieved evidence; they are not a clinical safety guarantee.",
            "- Human review remains required before any real clinical use.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def relevant_chunk_ids(chunks: list[EvidenceChunk], reference: str) -> set[str]:
    reference_tokens = informative_tokens(reference)
    scored = []
    for chunk in chunks:
        chunk_tokens = informative_tokens(chunk.text)
        score = len(reference_tokens & chunk_tokens) / max(1, len(reference_tokens))
        scored.append((chunk.chunk_id, score))
    relevant = {chunk_id for chunk_id, score in scored if score >= 0.08}
    if not relevant and scored:
        relevant.add(max(scored, key=lambda item: item[1])[0])
    return relevant


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return round(len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids), 4)


def reciprocal_rank(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    for index, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in relevant_ids:
            return round(1.0 / index, 4)
    return 0.0


def ndcg_at_k(ranked_ids: list[str], chunks: list[EvidenceChunk], reference: str, k: int) -> float:
    reference_tokens = informative_tokens(reference)
    relevance = {}
    for chunk in chunks:
        chunk_tokens = informative_tokens(chunk.text)
        relevance[chunk.chunk_id] = len(reference_tokens & chunk_tokens) / max(1, len(reference_tokens))
    gains = [relevance.get(chunk_id, 0.0) for chunk_id in ranked_ids[:k]]
    ideal = sorted(relevance.values(), reverse=True)[:k]
    if not ideal or sum(ideal) == 0:
        return 0.0
    import math

    dcg = sum((2**gain - 1) / math.log2(index + 2) for index, gain in enumerate(gains))
    idcg = sum((2**gain - 1) / math.log2(index + 2) for index, gain in enumerate(ideal))
    return round(dcg / idcg, 4) if idcg else 0.0


def informative_tokens(text: str) -> set[str]:
    import re

    stop = {"the", "and", "with", "for", "was", "were", "that", "this", "from", "after", "before", "patient"}
    return {token for token in re.findall(r"[A-Za-z0-9%./+-]+", (text or "").casefold()) if len(token) > 3 and token not in stop}


def mean(values: Any) -> float | None:
    clean = [float(value) for value in values if value not in (None, "")]
    return round(sum(clean) / len(clean), 4) if clean else None


def parse_models(value: str) -> list[str]:
    models = [item.strip() for item in value.split(",") if item.strip()]
    invalid = [item for item in models if item not in MODEL_CHECKPOINTS]
    if invalid:
        raise ValueError(f"Unsupported model(s): {', '.join(invalid)}")
    return models


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            payload = dict(row)
            if isinstance(payload.get("failure_counts"), dict):
                payload["failure_counts"] = json.dumps(payload["failure_counts"], ensure_ascii=False)
            writer.writerow({field: payload.get(field) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def configure_environment(embedding_model: str) -> None:
    os.environ.setdefault("HF_HOME", "D:/hf_cache")
    os.environ.setdefault("HF_HUB_CACHE", "D:/hf_cache/hub")
    os.environ.setdefault("HF_DATASETS_CACHE", "D:/hf_cache/datasets")
    os.environ.setdefault("TRANSFORMERS_CACHE", "D:/hf_cache/hub")
    os.environ["RAG_EMBEDDING_PROVIDER"] = "sentence_transformers"
    os.environ["RAG_SENTENCE_TRANSFORMERS_MODEL"] = embedding_model
    os.environ.setdefault("RAG_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY", "true")
    for key in ("HF_HOME", "HF_HUB_CACHE", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE"):
        if Path(os.environ[key]).drive.casefold() == "c:":
            raise RuntimeError(f"Refusing to use {key} on C drive: {os.environ[key]}")


def log(path: Path, message: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}"
    print(message)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval-grounded summarization benchmark with MiniLM + Qdrant.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--dataset-name", default="multiclinsum")
    parser.add_argument("--models", default="deterministic")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--qdrant-mode", choices=["memory", "persistent"], default="memory")
    parser.add_argument("--qdrant-path", default="")
    parser.add_argument("--top-k-per-query", type=int, default=3)
    parser.add_argument("--max-context-chunks", type=int, default=10)
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
