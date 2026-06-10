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
DEFAULT_OUTPUT = Path("D:/clin_summ_outputs/rag_best_models_benchmark")
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
    re.compile(r"\bno medications? (?:were|was)?\s*(?:administered|given|used|prescribed|reported)\b", re.I),
    re.compile(r"\b(?:the patient|he|she) (?:was )?not (?:given|taking|treated with|prescribed) medications?\b", re.I),
    re.compile(r"\bwithout medications?\b", re.I),
]
NEGATIVE_CLINICAL_PATTERNS = {
    "MEDICATIONS": NEGATIVE_MEDICATION_PATTERNS,
}


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

    # Update global latest pointer for the UI to pick up automatically.
    latest_pointer = Path("D:/clin_summ_outputs/latest_rag_best_models.json")
    try:
        write_json(latest_pointer, {"selected_output_dir": str(output_dir)})
    except Exception as exc:
        log(log_path, f"Failed to write latest pointer file: {exc}")

    manifest = build_manifest(args, records, comparison_rows, runtime, grounding_paths, retrieval_rows)
    write_json(output_dir / "rag_benchmark_manifest.json", manifest)
    write_reproducibility_manifest(output_dir / "reproducibility_manifest.json", manifest["reproducibility"])
    write_report(output_dir / "EVALUATION_REPORT.md", manifest, comparison_rows, retrieval_rows)
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
        "critical_fact_counts": json.dumps(context.critical_fact_counts, ensure_ascii=False),
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
        reranked.append(chunk.model_copy(update={"section": inferred_section, "score": round(score, 6)}))
    return sorted(reranked, key=lambda item: float(item.score or 0.0), reverse=True)


def select_balanced_evidence(
    retrieved_by_section: dict[str, list[EvidenceChunk]],
    *,
    max_context_chunks: int,
) -> list[EvidenceChunk]:
    selected: list[EvidenceChunk] = []
    selected_ids: set[str] = set()

    for section in SECTION_QUERIES:
        quota = min(SECTION_CHUNK_QUOTAS.get(section, 1), max_context_chunks)
        for chunk in retrieved_by_section.get(section, [])[:quota]:
            if chunk.chunk_id in selected_ids:
                continue
            selected.append(chunk)
            selected_ids.add(chunk.chunk_id)
            if len(selected) >= max_context_chunks:
                return selected

    leftovers = [
        chunk
        for chunks in retrieved_by_section.values()
        for chunk in chunks
        if chunk.chunk_id not in selected_ids
    ]
    for chunk in sorted(leftovers, key=lambda item: float(item.score or 0.0), reverse=True):
        selected.append(chunk)
        selected_ids.add(chunk.chunk_id)
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
        "Create a concise, evidence-grounded medical record summary for proxy clinical NLP evaluation.\n\n"
        "Clinical safety rules:\n"
        "- Use the citation-first clinical facts before raw evidence.\n"
        "- Preserve diagnosis, medications, timeline, assessment, and plan when evidence is present.\n"
        "- Do not invent facts, labs, medications, dates, diagnoses, procedures, outcomes, or plans.\n"
        "- Do not convert 'not present in retrieved evidence' into a negative clinical claim.\n"
        "- If medication evidence is missing, write exactly: 'Medication information was not present in retrieved evidence.'\n"
        "- If diagnosis, timeline, assessment, or plan evidence is missing, say the section was not present in retrieved evidence.\n"
        "- Never write 'no medications', 'no treatment', 'no diagnosis', or 'no plan' unless a cited evidence sentence explicitly says that.\n"
        "- Prefer 4 to 7 compact sentences. Avoid bullets unless the evidence is strongly structured.\n"
        "- Return only the summary text. Do not include XML, ChatML, markdown fences, or hidden reasoning.\n\n"
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

    return guarded, flags


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
            started = time.perf_counter()
            generated = deterministic_citation_first_summary(context["context_text"])
            latency_ms = int((time.perf_counter() - started) * 1000)
            rows.append(prediction_row(record, context, provider, model_checkpoint(provider), generated, latency_ms))
        return rows
    model_name = model_checkpoint(provider)
    if provider in GATEWAY_MODEL_PROVIDERS:
        # If the gateway is configured to use litellm, call litellm.completion
        # with provider-specific routing and options. Otherwise fall back to
        # centralized gateway proxy behavior (unchanged).
        gateway_mode = os.environ.get("LLM_GATEWAY_MODE", "proxy").strip().casefold()
        if gateway_mode == "litellm":
            LITELLM_MODEL_MAP = {
                "qwen2.5": "ollama_chat/qwen2.5:3b",
                "llama3.2": "ollama_chat/llama3.2:3b",
                "gemini2.5_flash_lite": "gemini/gemini-2.5-flash-lite",
            }
            from backend.app.evaluation import llmgateway as _llmgateway

            for index, record in enumerate(records, start=1):
                context = context_by_note[record["note_id"]]
                started = time.perf_counter()
                try:
                    try:
                        import litellm
                    except Exception as exc:
                        mapped_model = LITELLM_MODEL_MAP.get(provider, _llmgateway.gateway_model_name(provider))
                        print(
                            f"litellm import failed; provider={provider} mapped_model={mapped_model} note_id={record.get('note_id') or ''} {type(exc).__name__}: {exc}"
                        )
                        raise

                    messages = _llmgateway._summary_messages(
                        build_gateway_summary_prompt(context["context_text"])
                    )
                    mapped_model = LITELLM_MODEL_MAP.get(provider, _llmgateway.gateway_model_name(provider))
                    config = _llmgateway.gateway_config_from_env()

                    kwargs = {
                        "model": mapped_model,
                        "messages": messages,
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                        "timeout": config.timeout_seconds,
                    }

                    # pass explicit local context size if available
                    if provider in _llmgateway.LOCAL_GATEWAY_PROVIDERS:
                        env_num_ctx = os.environ.get("LLM_GATEWAY_LOCAL_NUM_CTX")
                        if env_num_ctx not in (None, ""):
                            try:
                                kwargs["num_ctx"] = int(env_num_ctx)
                            except ValueError:
                                kwargs["num_ctx"] = config.local_num_ctx
                        else:
                            kwargs["num_ctx"] = config.local_num_ctx

                    # pass api_base for ollama-backed providers
                    if provider in ("qwen2.5", "llama3.2"):
                        kwargs["api_base"] = os.environ.get("OLLAMA_API_BASE", "http://127.0.0.1:11434")

                    # gemini API key if available
                    if provider == "gemini2.5_flash_lite" and os.environ.get("GEMINI_API_KEY"):
                        kwargs["api_key"] = os.environ["GEMINI_API_KEY"]

                    response = litellm.completion(**kwargs)
                    generated = str(response.choices[0].message.content or "")
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    rows.append(prediction_row(record, context, provider, mapped_model, generated, latency_ms))
                except Exception as exc:
                    mapped_model = locals().get("mapped_model") or _llmgateway.gateway_model_name(provider)
                    print(
                        f"LiteLLM exception provider={provider} mapped_model={mapped_model} note_id={record.get('note_id') or ''} {type(exc).__name__}: {exc}"
                    )
                    raise

                if index % 10 == 0:
                    log(log_path, f"{provider}: completed {index}/{len(records)} records.")
            return rows

        # Fallback: use centralized gateway proxy (existing behavior)
        for index, record in enumerate(records, start=1):
            context = context_by_note[record["note_id"]]
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
        prompt_template_version="clinical_context_builder.citation_first.gateway_v3",
        retrieval_config={
            "embedding_provider": "sentence_transformers",
            "embedding_model": args.embedding_model,
            "vector_store": "qdrant",
            "qdrant_mode": args.qdrant_mode,
            "retrieval_strategy": "section_aware_source_query_balanced_citation_first_v3",
            "context_builder": "citation_first_clinical_context.v2",
            "reference_summary_used_for_retrieval": False,
            "top_k_per_query": args.top_k_per_query,
            "max_context_chunks": args.max_context_chunks,
            "section_chunk_quotas": SECTION_CHUNK_QUOTAS,
            "clinical_sections": list(SECTION_QUERIES),
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
    args = parser.parse_args()
    args.local_files_only = not args.allow_model_downloads
    return args


if __name__ == "__main__":
    main()
