from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.evaluation.artifact_paths import configured_evaluation_artifact_root
from backend.app.evaluation.citation_grounding import analyze_prediction_row, split_claims, write_grounding_outputs
from backend.app.evaluation.clinical_context_builder import (
    SECTION_PATTERNS,
    SECTION_QUERIES,
    build_clinical_context,
    classify_evidence_section,
    clinical_salience_score,
    normalize_whitespace,
)
from backend.app.evaluation.clinical_metrics import (
    PER_RECORD_CLINICAL_FIELDS,
    aggregate_clinical_metrics,
    compute_clinical_record_metrics,
    serialize_failure_categories,
)
from backend.app.evaluation.llmgateway import GATEWAY_MODEL_PROVIDERS, generate_llm_summary, gateway_model_name
from backend.app.evaluation.reproducibility import build_reproducibility_manifest, write_reproducibility_manifest
from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics
from backend.app.schemas import ClinicalDocument, EvidenceChunk, IngestRequest
from backend.app.services.chunking import ClinicalChunker
from backend.app.services.embeddings import SentenceTransformersEmbeddingProvider
from backend.app.services.vector_store import QdrantVectorStore
from src.data.dataset_loader import load_jsonl_dataset
from src.models.seq2seq import generate_seq2seq_summary, load_seq2seq_model


PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, "
    "or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as "
    "MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes."
)
DEFAULT_DATASET = Path("data/processed/governance/benchmark_set.jsonl")
DEFAULT_OUTPUT = configured_evaluation_artifact_root() / "rag_best_models_benchmark"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODELS = "deterministic,bart,pegasus,qwen2.5,llama3.2,gemini2.5_flash_lite"
SECTION_CHUNK_QUOTAS = {
    "DIAGNOSIS": 2,
    "MEDICATIONS": 2,
    "TIMELINE": 2,
    "ASSESSMENT": 2,
    "PLAN": 2,
    "DIAGNOSTICS": 2,
}
QUERY_STOPWORDS = {
    "about",
    "after",
    "also",
    "before",
    "been",
    "being",
    "between",
    "clinical",
    "could",
    "from",
    "have",
    "into",
    "note",
    "only",
    "patient",
    "record",
    "should",
    "source",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "were",
    "with",
    "without",
}
MODEL_CHECKPOINTS = {
    "deterministic": "deterministic_context_baseline",
    "bart": "facebook/bart-large-cnn",
    "pegasus": "google/pegasus-cnn_dailymail",
    "qwen2.5": gateway_model_name("qwen2.5"),
    "llama3.2": gateway_model_name("llama3.2"),
    "gemini2.5_flash_lite": gateway_model_name("gemini2.5_flash_lite"),
}

NEGATIVE_MEDICATION_PATTERNS = [
    re.compile(r"\bno specific medications? (?:were|was)?\s*(?:mentioned|reported|documented|listed|administered|given|used|prescribed)\b", re.I),
    re.compile(r"\bno medications? (?:were|was)?\s*(?:mentioned|reported|documented|listed|administered|given|used|prescribed)\b", re.I),
    re.compile(r"\bno medications? (?:were|was)?\s*(?:administered|given|used|prescribed|reported)\b", re.I),
    re.compile(r"\b(?:the patient|he|she) (?:was )?not (?:given|taking|treated with|prescribed) medications?\b", re.I),
    re.compile(r"\b(?:did not|does not|didn'?t|doesn'?t) require (?:any )?(?:ongoing )?(?:treatment|medications?)\b", re.I),
    re.compile(r"\bwithout medications?\b", re.I),
]
UNSUPPORTED_PLAN_PATTERNS = [
    re.compile(r"\bfuture care (?:includes|included|will|should)\b", re.I),
    re.compile(r"\bregular follow[- ]?ups? (?:to|for)\b", re.I),
    re.compile(r"\b(?:follow[- ]?ups?|monitoring) (?:to|for) (?:monitor|detect|assess|evaluate)\b", re.I),
    re.compile(r"\b(?:will|should|must|is to|was to) (?:follow|return|continue|monitor|receive|undergo|start|take|be treated|be referred)\b", re.I),
    re.compile(r"\b(?:follow[- ]?up|treatment|monitoring|referral|discharge) (?:is|was|were)?\s*(?:planned|scheduled|recommended|arranged)\b", re.I),
    re.compile(r"\b(?:the )?plan (?:is|was|included|includes|will)\b", re.I),
]
NEGATIVE_CLINICAL_PATTERNS = {
    "MEDICATIONS": NEGATIVE_MEDICATION_PATTERNS,
    "PLAN": UNSUPPORTED_PLAN_PATTERNS,
}
PLAN_UNKNOWN_VARIANTS = [
    re.compile(r"\bfuture care is not specified(?: as it was not present in retrieved evidence)?\.?", re.I),
    re.compile(r"\bfuture care was not specified(?: as it was not present in retrieved evidence)?\.?", re.I),
]


def main() -> None:
    args = parse_args()
    configure_environment(args.embedding_model)
    configure_llm_gateway(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    log_path.write_text("", encoding="utf-8")
    started = time.perf_counter()
    log(log_path, "Starting Flow 2.1 RAG Best Models benchmark.")
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
        f"rag_best_models_{int(time.time())}",
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

        # Validate provider outputs: ensure predictions correspond to the input note_ids.
        expected_note_ids = [record["note_id"] for record in records]
        expected_set = set(expected_note_ids)
        provider_note_ids = [row.get("note_id") for row in rows]
        unexpected = [nid for nid in provider_note_ids if nid not in expected_set]
        if unexpected:
            log(log_path, f"{provider}: unexpected prediction note_ids detected: {unexpected}")
            if getattr(args, "fail_on_unexpected_predictions", False):
                raise RuntimeError(f"{provider}: unexpected prediction note_ids found: {unexpected}")
            if getattr(args, "drop_unexpected_predictions", False):
                # Rebuild rows so the output contains exactly one row per input record in input order.
                row_map = {row.get("note_id"): row for row in rows}
                rebuilt: list[dict[str, Any]] = []
                for record in records:
                    nid = record["note_id"]
                    if nid in row_map:
                        rebuilt.append(row_map[nid])
                    else:
                        # create a failed placeholder row to preserve ordering and counts
                        rebuilt.append(failed_prediction_row(record, context_by_note.get(nid, {}), provider, model_checkpoint(provider), "missing_prediction_filtered"))
                rows = rebuilt

        model_rows[provider] = rows
        all_predictions.extend(rows)
        write_jsonl(output_dir / f"{provider}_predictions.jsonl", rows)

    write_jsonl(output_dir / "all_predictions.jsonl", all_predictions)
    write_per_record_metrics(output_dir / "per_record_metrics.csv", all_predictions)
    write_per_record_failure_analysis(output_dir / "per_record_failure_analysis.jsonl", all_predictions)
    grounding_paths = write_grounding_outputs(output_dir, [analyze_prediction_row(row) for row in all_predictions])

    # Build model comparison; if BERTScore computation fails, log and
    # continue without BERTScore so artifacts are still produced.
    bertscore_status = "not_requested"
    try:
        comparison_rows = build_model_comparison(model_rows, include_bertscore=args.include_bertscore)
        bertscore_status = "completed" if args.include_bertscore else "not_requested"
    except Exception as exc:
        log(log_path, f"BERTScore computation failed: {exc}")
        print(f"BERTScore computation failed: {type(exc).__name__}: {exc}")
        try:
            comparison_rows = build_model_comparison(model_rows, include_bertscore=False)
        except Exception as exc2:
            log(log_path, f"Failed to build model comparison without BERTScore: {exc2}")
            comparison_rows = []
        # mark bertscore as failed and clear bertscore columns
        bertscore_status = "failed"
        for row in comparison_rows:
            row["bertscore_status"] = "failed"
            row["bertscore_precision"] = None
            row["bertscore_recall"] = None
            row["bertscore_f1"] = None

    # Ensure output directory exists and write required UI artifacts.
    output_dir.mkdir(parents=True, exist_ok=True)
    log(log_path, f"Writing Flow 2.1 artifacts to {output_dir}")
    write_model_comparison(output_dir / "model_comparison.csv", comparison_rows)
    log(log_path, "model_comparison.csv written")

    # Write per-provider prediction/result files were written earlier during provider runs.
    # Write run summary and artifact manifest for the UI.
    runtime = round(time.perf_counter() - started, 4)
    run_summary = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pipeline": "rag_best_models_benchmark",
        "selected_output_dir": str(output_dir),
        "bertscore_status": bertscore_status,
        "record_count": len(records),
        "model_count": len(comparison_rows),
        "runtime_seconds": runtime,
        "notes": PROXY_WARNING,
    }
    write_json(output_dir / "run_summary.json", run_summary)

    artifact_manifest = {
        "model_comparison": str(output_dir / "model_comparison.csv") if (output_dir / "model_comparison.csv").exists() else None,
        "per_record_metrics": str(output_dir / "per_record_metrics.csv") if (output_dir / "per_record_metrics.csv").exists() else None,
        "per_record_failure_analysis": str(output_dir / "per_record_failure_analysis.jsonl") if (output_dir / "per_record_failure_analysis.jsonl").exists() else None,
        "predictions": {provider: str(output_dir / f"{provider}_predictions.jsonl") if (output_dir / f"{provider}_predictions.jsonl").exists() else None for provider in model_rows},
        "all_predictions": str(output_dir / "all_predictions.jsonl") if (output_dir / "all_predictions.jsonl").exists() else None,
        "retrieved_evidence": str(output_dir / "retrieved_evidence.jsonl") if (output_dir / "retrieved_evidence.jsonl").exists() else None,
        "retrieval_metrics": str(output_dir / "retrieval_metrics.csv") if (output_dir / "retrieval_metrics.csv").exists() else None,
        "run_log": str(log_path) if log_path.exists() else None,
        "evaluation_report": str(output_dir / "EVALUATION_REPORT.md") if (output_dir / "EVALUATION_REPORT.md").exists() else None,
        "reproducibility_manifest": str(output_dir / "reproducibility_manifest.json") if (output_dir / "reproducibility_manifest.json").exists() else None,
        "rag_benchmark_manifest": str(output_dir / "rag_benchmark_manifest.json") if (output_dir / "rag_benchmark_manifest.json").exists() else None,
        "run_summary": str(output_dir / "run_summary.json"),
    }
    write_json(output_dir / "artifact_manifest.json", artifact_manifest)

    if not args.skip_latest_pointer:
        latest_pointer = configured_evaluation_artifact_root() / "latest_rag_best_models.json"
        try:
            write_json(latest_pointer, {"selected_output_dir": str(output_dir)})
        except Exception as exc:
            log(log_path, f"Failed to write latest pointer file: {exc}")

    manifest = build_manifest(args, records, comparison_rows, runtime, grounding_paths, retrieval_rows)
    write_json(output_dir / "rag_benchmark_manifest.json", manifest)
    write_reproducibility_manifest(output_dir / "reproducibility_manifest.json", manifest["reproducibility"])
    write_report(output_dir / "EVALUATION_REPORT.md", manifest, comparison_rows, retrieval_rows)
    if args.terminal_smoke_report:
        print_terminal_smoke_report(records, context_by_note, model_rows, max_records=args.terminal_smoke_records)
    log(log_path, f"Completed retrieval-grounded benchmark in {runtime} seconds.")
    log(log_path, f"RAG Best Models benchmark outputs written to {output_dir}")
    print(f"RAG Best Models benchmark outputs written to {output_dir}")


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
    retrieved_by_section: dict[str, list[EvidenceChunk]] = {}
    query_payloads: list[dict[str, Any]] = []
    for section, query in SECTION_QUERIES.items():
        expanded_query = build_source_aware_section_query(section, query, record.get("source_note", ""))
        query_vector = embedding_provider.embed_query(expanded_query)
        retrieved = vector_store.search(tenant_id, patient_id, query_vector, top_k_per_query)
        reranked = rerank_section_evidence(section, retrieved)
        retrieved_by_section[section] = reranked
        query_payloads.append(
            {
                "section": section,
                "query": expanded_query,
                "retrieved_chunk_ids": [chunk.chunk_id for chunk in reranked],
                "scores": [round(float(chunk.score or 0.0), 6) for chunk in reranked],
            }
        )
    evidence = select_balanced_evidence(retrieved_by_section, max_context_chunks=max_context_chunks)
    context = build_clinical_context(evidence, max_chunks=max_context_chunks)
    relevant_ids = relevant_chunk_ids(chunks, record.get("reference_summary", ""))
    ranked_ids = [chunk.chunk_id for chunk in evidence]
    unique_ranked_ids = list(dict.fromkeys(ranked_ids))
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000, 4)
    retrieval_row = {
        "note_id": record["note_id"],
        "patient_id": patient_id,
        "encounter_id": record.get("encounter_id"),
        "chunk_count": len(chunks),
        "retrieved_chunk_count": len(unique_ranked_ids),
        "context_chunk_count": len(context.evidence),
        "context_token_count": context.token_count,
        "recall_at_1": recall_at_k(unique_ranked_ids, relevant_ids, 1),
        "recall_at_3": recall_at_k(unique_ranked_ids, relevant_ids, 3),
        "recall_at_5": recall_at_k(unique_ranked_ids, relevant_ids, 5),
        "mrr": reciprocal_rank(unique_ranked_ids, relevant_ids),
        "ndcg_at_5": ndcg_at_k(unique_ranked_ids, chunks, record.get("reference_summary", ""), 5),
        "retrieval_latency_ms": retrieval_ms,
        "section_counts": json.dumps(context.section_counts, ensure_ascii=False),
        "critical_fact_counts": json.dumps(context.critical_fact_counts, ensure_ascii=False),
    }
    retrieval_gate = evaluate_retrieval_quality(record, retrieval_row, context)
    retrieval_row.update(retrieval_gate)
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
        "retrieval_gate": retrieval_gate,
        "section_counts": context.section_counts,
        "critical_fact_counts": context.critical_fact_counts,
    }
    return retrieval_row, evidence_payload, context_payload


def build_source_aware_section_query(section: str, base_query: str, source_note: str) -> str:
    """Build retrieval queries from available source text, not reference labels."""

    section_terms = extract_section_terms(section, source_note)
    query_parts = [
        base_query,
        f"Find patient-specific evidence for {section.lower()} in the clinical source note.",
    ]
    if section_terms:
        query_parts.append("Key source terms: " + " ".join(section_terms))
    return normalize_whitespace(" ".join(query_parts))[:1200]


def evaluate_retrieval_quality(
    record: dict[str, str],
    retrieval: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    fact_counts = context.critical_fact_counts or {}
    diagnosis_ok = int(fact_counts.get("DIAGNOSIS") or 0) > 0
    medication_ok = int(fact_counts.get("MEDICATIONS") or 0) > 0
    timeline_ok = int(fact_counts.get("TIMELINE") or 0) > 0
    expected_patient = record.get("patient_id") or record.get("note_id")
    expected_encounter = record.get("encounter_id")
    same_patient = all(str(chunk.patient_id or "") == str(expected_patient or "") for chunk in context.evidence)
    same_encounter = True
    if expected_encounter:
        same_encounter = all(
            not getattr(chunk, "encounter_id", None) or str(chunk.encounter_id) == str(expected_encounter)
            for chunk in context.evidence
        )
    recall = float(retrieval.get("recall_at_5") or 0.0)
    context_chunks = int(retrieval.get("context_chunk_count") or 0)
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    if not diagnosis_ok:
        blocking_reasons.append("missing_diagnosis_evidence")
    if not timeline_ok:
        blocking_reasons.append("missing_timeline_evidence")
    if not same_patient:
        blocking_reasons.append("wrong_patient_evidence")
    if not same_encounter:
        blocking_reasons.append("wrong_encounter_evidence")
    if context_chunks == 0:
        blocking_reasons.append("no_retrieved_context")
    if recall < 0.5:
        blocking_reasons.append("low_recall_at_5_proxy")
    if not medication_ok:
        warnings.append("missing_medication_evidence")
    status = "failed" if blocking_reasons else "warning" if warnings else "passed"
    decision = "review_retrieval_first" if status == "failed" else "proceed_with_caution" if status == "warning" else "proceed"
    return {
        "retrieval_quality_status": status,
        "retrieval_gate_decision": decision,
        "retrieval_gate_reasons": "; ".join(blocking_reasons),
        "retrieval_gate_warnings": "; ".join(warnings),
        "diagnosis_evidence_present": diagnosis_ok,
        "medication_evidence_present": medication_ok,
        "timeline_evidence_present": timeline_ok,
        "same_patient_evidence": same_patient,
        "same_encounter_evidence": same_encounter,
    }


def extract_section_terms(section: str, source_note: str, *, limit: int = 28) -> list[str]:
    pattern = SECTION_PATTERNS.get(section)
    candidate_text = source_note
    if pattern:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", source_note or "")
            if pattern.search(sentence)
        ]
        if sentences:
            candidate_text = " ".join(sentences[:6])
    tokens = [
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9%./+-]{2,}", candidate_text or "")
        if token.casefold() not in QUERY_STOPWORDS
    ]
    counts = Counter(tokens)
    return [token for token, _count in counts.most_common(limit)]


def rerank_section_evidence(section: str, retrieved: list[EvidenceChunk]) -> list[EvidenceChunk]:
    reranked: list[EvidenceChunk] = []
    for rank, chunk in enumerate(retrieved):
        inferred_section = classify_evidence_section(chunk)
        vector_score = float(chunk.score or 0.0)
        salience = clinical_salience_score(chunk, section)
        section_bonus = 0.18 if inferred_section == section else 0.0
        rank_penalty = rank * 0.006
        score = vector_score + (0.035 * salience) + section_bonus - rank_penalty
        reranked.append(chunk.model_copy(update={"section": section, "score": round(score, 6)}))
    return sorted(reranked, key=lambda item: float(item.score or 0.0), reverse=True)


def select_balanced_evidence(
    retrieved_by_section: dict[str, list[EvidenceChunk]],
    *,
    max_context_chunks: int,
) -> list[EvidenceChunk]:
    selected: list[EvidenceChunk] = []
    selected_ids: set[tuple[str, str]] = set()

    for section in SECTION_QUERIES:
        quota = min(SECTION_CHUNK_QUOTAS.get(section, 1), max_context_chunks)
        for chunk in retrieved_by_section.get(section, [])[:quota]:
            key = (section, chunk.chunk_id)
            if key in selected_ids:
                continue
            selected.append(chunk)
            selected_ids.add(key)
            if len(selected) >= max_context_chunks:
                return selected

    leftovers = [
        chunk
        for section, chunks in retrieved_by_section.items()
        for chunk in chunks
        if (section, chunk.chunk_id) not in selected_ids
    ]
    for chunk in sorted(leftovers, key=lambda item: float(item.score or 0.0), reverse=True):
        key = (str(chunk.section), chunk.chunk_id)
        if key in selected_ids:
            continue
        selected.append(chunk)
        selected_ids.add(key)
        if len(selected) >= max_context_chunks:
            break
    return selected


def deterministic_citation_first_summary(context_text: str, *, max_facts: int = 8) -> str:
    fact_lines = []
    in_fact_block = False
    for line in context_text.splitlines():
        stripped = line.strip()
        if stripped == "[CITATION_FIRST_CLINICAL_FACTS]":
            in_fact_block = True
            continue
        if stripped == "[RETRIEVED_EVIDENCE_BY_SECTION]":
            break
        if not in_fact_block:
            continue
        if (
            not stripped.startswith("- (")
            or "not available in retrieved evidence" in stripped
            or "not present in retrieved evidence" in stripped
        ):
            continue
        fact_lines.append(stripped[2:].strip())
    if fact_lines:
        return " ".join(fact_lines[:max_facts])

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", context_text)
        if sentence.strip()
    ]
    return " ".join(sentences[:4]).strip()


def build_posthoc_citations(
    generated_summary: str,
    evidence_payload: list[dict[str, Any]],
    *,
    min_support_overlap: float = 0.18,
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for claim_index, claim in enumerate(split_claims(generated_summary)):
        best = best_evidence_match(claim, evidence_payload)
        if not best or best["support_score"] < min_support_overlap:
            continue
        citations.append(
            {
                "claim_index": claim_index,
                "chunk_id": best["chunk_id"],
                "patient_id": best["patient_id"],
                "encounter_id": best.get("encounter_id"),
                "support_score": best["support_score"],
                "source_text": best["text"],
            }
        )
    return citations


def best_evidence_match(claim: str, evidence_payload: list[dict[str, Any]]) -> dict[str, Any] | None:
    claim_tokens = informative_tokens(claim)
    if not claim_tokens:
        return None
    best: dict[str, Any] | None = None
    best_score = 0.0
    for item in evidence_payload:
        evidence_tokens = informative_tokens(str(item.get("text") or ""))
        if not evidence_tokens:
            continue
        recall = len(claim_tokens & evidence_tokens) / max(1, len(claim_tokens))
        precision = len(claim_tokens & evidence_tokens) / max(1, len(evidence_tokens))
        support_score = round((0.82 * recall) + (0.18 * precision), 4)
        if support_score > best_score:
            best_score = support_score
            best = {**item, "support_score": support_score}
    return best


def render_summary_with_citations(generated_summary: str, citations: list[dict[str, Any]]) -> str:
    claims = split_claims(generated_summary)
    if not claims:
        return generated_summary
    citations_by_claim = defaultdict(list)
    for citation in citations:
        citations_by_claim[int(citation.get("claim_index") or 0)].append(str(citation.get("chunk_id") or ""))
    rendered = []
    for index, claim in enumerate(claims):
        chunk_ids = [chunk_id for chunk_id in citations_by_claim.get(index, []) if chunk_id]
        suffix = " " + " ".join(f"[chunk:{chunk_id}]" for chunk_id in chunk_ids) if chunk_ids else ""
        rendered.append(f"{claim}{suffix}")
    return " ".join(rendered)


def build_gateway_summary_prompt(context_text: str) -> str:
    return (
        "Create a clinically precise, evidence-grounded medical record summary for proxy clinical NLP evaluation.\n\n"
        "Non-negotiable clinical RAG rules:\n"
        "1. Use [CITATION_FIRST_CLINICAL_FACTS] as the authoritative fact list. Raw evidence is support only.\n"
        "2. Strict section isolation: do not use TIMELINE facts to fill MEDICATIONS, PLAN, DIAGNOSIS, ASSESSMENT, or DIAGNOSTICS.\n"
        "3. Empty facts block means unknown. Do not infer absence. Do not write 'no medications', 'no diagnosis', 'no plan', or 'no treatment' unless the facts explicitly say so.\n"
        "4. PLAN is only future/intended/scheduled care. Past surgery, biopsy, imaging, or treatment belongs to TIMELINE, ASSESSMENT, or DIAGNOSTICS, not PLAN.\n"
        "5. Preserve critical details exactly when present: diagnosis, tumor/pathology type, procedure, medication name/dose/route, timeline, outcome, and follow-up.\n"
        "6. Do not complete cut-off evidence or add facts not visible in a cited chunk.\n"
        "7. If medication facts are empty, write exactly: 'Medication information was not present in retrieved evidence.'\n"
        "8. If plan facts are empty, do not invent follow-up or treatment plans. Only say plan information was not present if clinically relevant.\n"
        "9. Write 5 to 8 compact sentences. Return only the summary text. No XML, ChatML, markdown fences, or hidden reasoning.\n\n"
        f"Retrieved clinical context:\n{context_text}\n\n"
        "Summary:"
    )


def apply_generation_guardrails(generated_summary: str, context: dict[str, Any]) -> tuple[str, list[str]]:
    flags: list[str] = []
    guarded = normalize_whitespace(generated_summary)
    critical_fact_counts = context.get("critical_fact_counts") or {}

    if int(critical_fact_counts.get("MEDICATIONS") or 0) == 0:
        updated = replace_unsupported_negative_claims(
            guarded,
            NEGATIVE_CLINICAL_PATTERNS["MEDICATIONS"],
            "Medication information was not present in retrieved evidence.",
        )
        if updated != guarded:
            flags.append("replaced_unsupported_negative_medication_inference")
            guarded = updated

    if int(critical_fact_counts.get("PLAN") or 0) == 0:
        updated = replace_unsupported_negative_claims(
            guarded,
            NEGATIVE_CLINICAL_PATTERNS["PLAN"],
            "Plan information was not present in retrieved evidence.",
        )
        if updated != guarded:
            flags.append("replaced_unsupported_plan_inference")
            guarded = updated
        updated = replace_variant_statements(
            guarded,
            PLAN_UNKNOWN_VARIANTS,
            "Plan information was not present in retrieved evidence.",
        )
        if updated != guarded:
            flags.append("normalized_plan_unknown_statement")
            guarded = updated

    return guarded, flags


def replace_variant_statements(summary: str, patterns: list[re.Pattern[str]], replacement: str) -> str:
    updated = summary
    for pattern in patterns:
        updated = pattern.sub(replacement, updated)
    return normalize_whitespace(updated)


def replace_unsupported_negative_claims(summary: str, patterns: list[re.Pattern[str]], replacement: str) -> str:
    claims = split_claims(summary)
    if not claims:
        return summary
    guarded_claims: list[str] = []
    replacement_added = False
    for claim in claims:
        if any(pattern.search(claim) for pattern in patterns):
            if not replacement_added:
                guarded_claims.append(replacement)
                replacement_added = True
            continue
        guarded_claims.append(claim)
    return " ".join(guarded_claims).strip()


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
        for record in records:
            context = context_by_note[record["note_id"]]
            if retrieval_gate_blocks(context, args):
                rows.append(retrieval_blocked_prediction_row(record, context, provider, model_checkpoint(provider)))
                continue
            started = time.perf_counter()
            generated = deterministic_citation_first_summary(context["context_text"])
            latency_ms = int((time.perf_counter() - started) * 1000)
            rows.append(prediction_row(record, context, provider, model_checkpoint(provider), generated, latency_ms))
        return rows
    model_name = model_checkpoint(provider)
    if provider in GATEWAY_MODEL_PROVIDERS:
        for index, record in enumerate(records, start=1):
            context = context_by_note[record["note_id"]]
            if retrieval_gate_blocks(context, args):
                rows.append(retrieval_blocked_prediction_row(record, context, provider, model_name))
                continue
            started = time.perf_counter()
            try:
                generated = generate_llm_summary(
                    build_gateway_summary_prompt(context["context_text"]),
                    provider,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                rows.append(prediction_row(record, context, provider, model_name, generated, latency_ms))
            except Exception as exc:
                rows.append(failed_prediction_row(record, context, provider, model_name, str(exc)))
            if index % 10 == 0:
                log(log_path, f"{provider}: completed {index}/{len(records)} records.")
        return rows
    try:
        tokenizer, model, torch_device = load_seq2seq_model(model_name, args.device, local_files_only=args.local_files_only)
    except Exception as exc:
        log(log_path, f"{provider}: model load failed; recording failed rows and continuing. Error: {exc}")
        return [
            failed_prediction_row(record, context_by_note[record["note_id"]], provider, model_name, str(exc))
            for record in records
        ]
    for index, record in enumerate(records, start=1):
        context = context_by_note[record["note_id"]]
        if retrieval_gate_blocks(context, args):
            rows.append(retrieval_blocked_prediction_row(record, context, provider, model_name))
            continue
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
    generated_summary, guardrail_flags = apply_generation_guardrails(generated_summary, context)
    metrics = compute_pairwise_metrics([generated_summary], [record["reference_summary"]], include_bertscore=False)
    citations = build_posthoc_citations(generated_summary, context["evidence_payload"])
    row = {
        "evaluation_type": "rag_best_models_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "stage": "rag_best_models",
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
        "generated_summary_cited": render_summary_with_citations(generated_summary, citations),
        "generation_guardrail_flags": guardrail_flags,
        "citations": citations,
        "latency_ms": latency_ms,
        "retrieval_latency_ms": context["retrieval"]["retrieval_latency_ms"],
        "context_token_count": context["retrieval"]["context_token_count"],
        "retrieval_quality_status": context.get("retrieval_gate", {}).get("retrieval_quality_status"),
        "retrieval_gate_decision": context.get("retrieval_gate", {}).get("retrieval_gate_decision"),
        "retrieval_gate_reasons": context.get("retrieval_gate", {}).get("retrieval_gate_reasons"),
        "retrieval_gate_warnings": context.get("retrieval_gate", {}).get("retrieval_gate_warnings"),
        "rouge1": metrics["rouge1"],
        "rouge2": metrics["rouge2"],
        "rougeL": metrics["rougeL"],
    }
    row.update(compute_clinical_record_metrics(row))
    return row


def failed_prediction_row(record: dict[str, str], context: dict[str, Any], provider: str, model_name: str, error: str) -> dict[str, Any]:
    return {
        "evaluation_type": "rag_best_models_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "stage": "rag_best_models",
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
        "generated_summary_cited": "",
        "generation_guardrail_flags": [],
        "citations": [],
        "latency_ms": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
        "retrieval_latency_ms": context["retrieval"].get("retrieval_latency_ms"),
        "context_token_count": context["retrieval"].get("context_token_count"),
        "retrieval_quality_status": context.get("retrieval_gate", {}).get("retrieval_quality_status"),
        "retrieval_gate_decision": context.get("retrieval_gate", {}).get("retrieval_gate_decision"),
        "retrieval_gate_reasons": context.get("retrieval_gate", {}).get("retrieval_gate_reasons"),
        "retrieval_gate_warnings": context.get("retrieval_gate", {}).get("retrieval_gate_warnings"),
    }


def retrieval_gate_blocks(context: dict[str, Any], args: argparse.Namespace) -> bool:
    if getattr(args, "disable_retrieval_gate", False):
        return False
    return str(context.get("retrieval_gate", {}).get("retrieval_quality_status") or "") == "failed"


def retrieval_blocked_prediction_row(record: dict[str, str], context: dict[str, Any], provider: str, model_name: str) -> dict[str, Any]:
    gate = context.get("retrieval_gate", {})
    reasons = gate.get("retrieval_gate_reasons") or "retrieval quality gate failed"
    row = failed_prediction_row(
        record,
        context,
        provider,
        model_name,
        f"review retrieval first: {reasons}",
    )
    row["status"] = "failed"
    row["failure_categories"] = ["retrieval-related failure"]
    row["retrieval_quality_status"] = gate.get("retrieval_quality_status")
    row["retrieval_gate_decision"] = gate.get("retrieval_gate_decision")
    row["retrieval_gate_reasons"] = gate.get("retrieval_gate_reasons")
    row["retrieval_gate_warnings"] = gate.get("retrieval_gate_warnings")
    return row


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
                "model_name": model_checkpoint(provider),
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
        "retrieval_quality_status",
        "retrieval_gate_decision",
        "retrieval_gate_reasons",
        "retrieval_gate_warnings",
        *PER_RECORD_CLINICAL_FIELDS,
        "generation_guardrail_flags",
        "error_message",
    ]
    serializable = []
    for row in rows:
        payload = {field: row.get(field) for field in fields}
        payload["failure_categories"] = serialize_failure_categories(row.get("failure_categories"))
        if isinstance(payload.get("generation_guardrail_flags"), list):
            payload["generation_guardrail_flags"] = "; ".join(payload["generation_guardrail_flags"])
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
                "generated_summary_cited": row.get("generated_summary_cited"),
                "generation_guardrail_flags": row.get("generation_guardrail_flags") or [],
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
        "critical_fact_counts",
        "retrieval_quality_status",
        "retrieval_gate_decision",
        "retrieval_gate_reasons",
        "retrieval_gate_warnings",
        "diagnosis_evidence_present",
        "medication_evidence_present",
        "timeline_evidence_present",
        "same_patient_evidence",
        "same_encounter_evidence",
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
        run_name="rag_best_models_benchmark",
        dataset_path=Path(args.dataset),
        output_dir=output_dir,
        model_checkpoints={provider: model_checkpoint(provider) for provider in parse_models(args.models)}
        | {"retrieval_embedding": args.embedding_model},
        prompt_template_version="clinical_context_builder.strict_section_isolated_facts.gateway_v4",
        retrieval_config={
            "embedding_provider": "sentence_transformers",
            "embedding_model": args.embedding_model,
            "vector_store": "qdrant",
            "qdrant_mode": args.qdrant_mode,
            "retrieval_strategy": "section_aware_source_query_balanced_strict_fact_extraction_v4",
            "context_builder": "strict_section_isolated_citation_first_context.v4",
            "reference_summary_used_for_retrieval": False,
            "top_k_per_query": args.top_k_per_query,
            "max_context_chunks": args.max_context_chunks,
            "section_chunk_quotas": SECTION_CHUNK_QUOTAS,
            "clinical_sections": list(SECTION_QUERIES),
            "strict_section_isolation": True,
            "plan_requires_future_intent": True,
            "facts_are_left_blank_when_section_has_no_valid_evidence": True,
            "retrieval_quality_gate_enabled": not args.disable_retrieval_gate,
            "retrieval_quality_gate_blocks_generation_on_failed_gate": not args.disable_retrieval_gate,
            "retrieval_quality_gate_required_sections": ["DIAGNOSIS", "TIMELINE"],
            "retrieval_quality_gate_warning_sections": ["MEDICATIONS"],
        },
        generation_params={
            "max_input_tokens": args.max_input_tokens,
            "max_new_tokens": args.max_new_tokens,
            "num_beams": args.num_beams,
            "no_repeat_ngram_size": args.no_repeat_ngram_size,
            "device": args.device,
            "llm_gateway_base_url": args.llm_gateway_base_url,
            "llm_gateway_timeout_seconds": args.llm_gateway_timeout_seconds,
            "llm_gateway_temperature": args.llm_gateway_temperature,
            "llm_gateway_max_tokens": args.llm_gateway_max_tokens,
            "llm_gateway_local_num_ctx": args.llm_gateway_local_num_ctx,
        },
        extra={"proxy_warning": PROXY_WARNING},
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pipeline": "rag_best_models_benchmark",
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
        "# Flow 2.1 RAG Best Models Benchmark",
        "",
        f"> {PROXY_WARNING}",
        "",
        "## Summary",
        "",
        f"- Records loaded: `{manifest['records_loaded']}`",
        f"- Runtime seconds: `{manifest['runtime_seconds']}`",
        f"- Retrieval embedding: `{manifest['reproducibility']['retrieval_config']['embedding_model']}`",
        f"- Vector store: `Qdrant ({manifest['reproducibility']['retrieval_config']['qdrant_mode']})`",
        f"- LLM gateway: `{manifest['reproducibility']['generation_params'].get('llm_gateway_base_url')}`",
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
            "- Retrieval uses section-aware source-note queries, balanced clinical context packing, and citation-first fact extraction; reference summaries are not used for retrieval.",
            "- The context builder uses strict section-isolated fact extraction: empty section facts remain blank, and facts are never borrowed across clinical sections.",
            "- PLAN facts require future intent; completed surgery, biopsy, imaging, and treatment are treated as timeline/assessment/diagnostic evidence, not care plans.",
            "- The context builder places cited clinical facts before raw evidence to reduce missing diagnosis, medication, timeline, assessment, and plan details.",
            "- Flow 2.1 compares deterministic, BART, Pegasus, Qwen2.5, Llama3.2, and Gemini 2.5 Flash Lite when requested.",
            "- Pegasus PubMed and Pegasus XSum are not part of the Flow 2.1 default; provider `pegasus` uses the configured baseline checkpoint.",
            "- Qwen2.5, Llama3.2, and Gemini 2.5 Flash Lite are routed through the centralized LLM gateway with low-temperature medical summarization settings.",
            "- Generated claims are post-hoc matched to retrieved chunks for proxy citation coverage; unmatched claims remain unsupported in citation-grounding outputs.",
            "- Retrieval labels are proxy labels derived from reference-summary token overlap with chunks.",
            "- Citation metrics indicate whether generated claims are covered by retrieved evidence; they are not a clinical safety guarantee.",
            "- Human review remains required before any real clinical use.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def print_terminal_smoke_report(
    records: list[dict[str, str]],
    context_by_note: dict[str, dict[str, Any]],
    model_rows: dict[str, list[dict[str, Any]]],
    *,
    max_records: int,
) -> None:
    print("\n" + "=" * 96)
    print("FLOW 2.1 TERMINAL SMOKE REPORT")
    print(PROXY_WARNING)
    print("=" * 96)
    for record in records[:max_records]:
        note_id = record["note_id"]
        context = context_by_note[note_id]
        retrieval = context["retrieval"]
        print(f"\nNOTE_ID: {note_id}")
        print("-" * 96)
        print("[SOURCE NOTE PREVIEW]")
        print(_terminal_clip(record.get("source_note", ""), 1000))
        print("\n[REFERENCE SUMMARY]")
        print(_terminal_clip(record.get("reference_summary", ""), 800))
        print("\n[RETRIEVAL JUDGEMENT]")
        print(_retrieval_judgement(retrieval))
        print("\n[RETRIEVAL QUALITY GATE]")
        print(json.dumps(context.get("retrieval_gate") or {}, ensure_ascii=False, indent=2))
        print("\n[SECTION FACT COUNTS]")
        print(json.dumps(context.get("critical_fact_counts") or {}, ensure_ascii=False, indent=2))
        print("\n[TOP RETRIEVED EVIDENCE BY SECTION]")
        for section, chunks in _evidence_by_section(context.get("evidence_payload") or []).items():
            print(f"\n{section}")
            for chunk in chunks[:2]:
                print(f"- ({chunk.get('chunk_id')}) score={_score(chunk.get('score'))} {_terminal_clip(chunk.get('text') or '', 420)}")
        print("\n[MODEL OUTPUTS]")
        for provider, rows in model_rows.items():
            row = next((item for item in rows if item.get("note_id") == note_id), None)
            if not row:
                continue
            print(f"\n## {provider} :: {row.get('status')}")
            if row.get("error_message"):
                print(f"ERROR: {row.get('error_message')}")
                continue
            print(
                "metrics: "
                f"rougeL={_score(row.get('rougeL'))}, "
                f"citation={_score(row.get('citation_coverage'))}, "
                f"faithfulness={_score(row.get('factuality_proxy_score'))}, "
                f"latency_ms={row.get('latency_ms')}"
            )
            failures = serialize_failure_categories(row.get("failure_categories"))
            flags = "; ".join(row.get("generation_guardrail_flags") or [])
            print(f"failures: {failures or 'none'}")
            if flags:
                print(f"guardrails: {flags}")
            print(_terminal_clip(row.get("generated_summary") or "", 900))
    print("\n" + "=" * 96)
    print("END TERMINAL SMOKE REPORT")
    print("=" * 96 + "\n")


def _retrieval_judgement(retrieval: dict[str, Any]) -> str:
    fact_counts = _json_object(retrieval.get("critical_fact_counts"))
    section_counts = _json_object(retrieval.get("section_counts"))
    required = ("DIAGNOSIS", "TIMELINE", "ASSESSMENT", "DIAGNOSTICS")
    missing_facts = [section for section in required if int(fact_counts.get(section) or 0) == 0]
    sparse_sections = [section for section in SECTION_QUERIES if int(section_counts.get(section) or 0) == 0]
    verdict = "sufficient_for_smoke" if len(missing_facts) <= 1 else "needs_retrieval_review"
    return (
        f"verdict={verdict}; chunks={retrieval.get('chunk_count')}; "
        f"context_chunks={retrieval.get('context_chunk_count')}; tokens={retrieval.get('context_token_count')}; "
        f"recall@5_proxy={retrieval.get('recall_at_5')}; mrr_proxy={retrieval.get('mrr')}; "
        f"missing_fact_sections={missing_facts or 'none'}; sparse_retrieved_sections={sparse_sections or 'none'}"
    )


def _evidence_by_section(evidence_payload: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_QUERIES}
    for item in evidence_payload:
        section = str(item.get("section") or "ASSESSMENT").upper()
        grouped.setdefault(section, []).append(item)
    return grouped


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _terminal_clip(text: str, max_chars: int) -> str:
    clean = normalize_whitespace(str(text or ""))
    return clean if len(clean) <= max_chars else clean[:max_chars].rstrip() + "..."


def _score(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


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


def model_checkpoint(provider: str) -> str:
    if provider in GATEWAY_MODEL_PROVIDERS:
        return gateway_model_name(provider)
    if provider == "bart":
        return os.environ.get("BART_MODEL_NAME") or MODEL_CHECKPOINTS[provider]
    if provider == "pegasus":
        return os.environ.get("PEGASUS_MODEL_NAME") or MODEL_CHECKPOINTS[provider]
    return MODEL_CHECKPOINTS[provider]


def parse_models(value: str) -> list[str]:
    models = [item.strip() for item in value.split(",") if item.strip()]
    invalid = [item for item in models if item not in MODEL_CHECKPOINTS]
    if invalid:
        supported = ", ".join(MODEL_CHECKPOINTS)
        raise ValueError(
            f"Unsupported Flow 2.1 model(s): {', '.join(invalid)}. "
            f"Supported models: {supported}."
        )
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


def configure_llm_gateway(args: argparse.Namespace) -> None:
    os.environ["LLM_GATEWAY_BASE_URL"] = args.llm_gateway_base_url
    os.environ["LLM_GATEWAY_TIMEOUT_SECONDS"] = str(args.llm_gateway_timeout_seconds)
    os.environ["LLM_GATEWAY_TEMPERATURE"] = str(args.llm_gateway_temperature)
    os.environ["LLM_GATEWAY_MAX_TOKENS"] = str(args.llm_gateway_max_tokens)
    os.environ["LLM_GATEWAY_LOCAL_NUM_CTX"] = str(args.llm_gateway_local_num_ctx)
    if args.llm_gateway_mode:
        os.environ["LLM_GATEWAY_MODE"] = args.llm_gateway_mode


def log(path: Path, message: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}"
    print(message)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Flow 2.1 RAG Best Models benchmark with MiniLM + Qdrant + LLM Gateway.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--dataset-name", default="multiclinsum")
    parser.add_argument(
        "--models",
        default=DEFAULT_MODELS,
        help="Comma-separated models. Supported: deterministic,bart,pegasus,qwen2.5,llama3.2,gemini2.5_flash_lite.",
    )
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
    parser.add_argument("--llm-gateway-base-url", default=os.environ.get("LLM_GATEWAY_BASE_URL", "http://localhost:4000"))
    parser.add_argument("--llm-gateway-mode", choices=["proxy", "litellm"], default=os.environ.get("LLM_GATEWAY_MODE", "proxy"))
    parser.add_argument("--llm-gateway-timeout-seconds", type=float, default=float(os.environ.get("LLM_GATEWAY_TIMEOUT_SECONDS", "120")))
    parser.add_argument("--llm-gateway-temperature", type=float, default=float(os.environ.get("LLM_GATEWAY_TEMPERATURE", "0.1")))
    parser.add_argument("--llm-gateway-max-tokens", type=int, default=int(os.environ.get("LLM_GATEWAY_MAX_TOKENS", "384")))
    parser.add_argument("--llm-gateway-local-num-ctx", type=int, default=int(os.environ.get("LLM_GATEWAY_LOCAL_NUM_CTX", "8192")))
    parser.add_argument("--terminal-smoke-report", action="store_true", help="Print source/evidence/facts/model outputs directly to the terminal.")
    parser.add_argument("--terminal-smoke-records", type=int, default=1, help="Number of records to print in the terminal smoke report.")
    parser.add_argument(
        "--skip-latest-pointer",
        action="store_true",
        help="Do not update latest_rag_best_models.json under the configured evaluation artifact root.",
    )
    parser.add_argument("--disable-retrieval-gate", action="store_true", help="Force summarization even when retrieval quality gate says review retrieval first.")
    parser.add_argument(
        "--drop-unexpected-predictions",
        action="store_true",
        help=(
            "Drop prediction rows whose `note_id` is not present in the input dataset. "
            "This prevents provider outputs from substituting unexpected records."
        ),
    )
    parser.add_argument(
        "--fail-on-unexpected-predictions",
        action="store_true",
        help=(
            "Raise an error if provider predictions contain `note_id`s not in the input dataset. "
            "Useful for detecting accidental replacement behavior."
        ),
    )
    args = parser.parse_args()
    args.local_files_only = not args.allow_model_downloads
    return args


if __name__ == "__main__":
    main()
