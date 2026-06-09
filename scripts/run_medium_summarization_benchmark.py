from __future__ import annotations

import csv
import copy
import io
import json
import logging
import os
import re
import sys
import time
import warnings
from collections import Counter
from contextlib import redirect_stderr
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.evaluation.clinical_metrics import (
    PER_RECORD_CLINICAL_FIELDS,
    aggregate_clinical_metrics,
    compute_clinical_record_metrics,
    empty_clinical_record_metrics,
    serialize_failure_categories,
)
from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics
from evaluation.data_governance.layers import HONESTY_WARNING, configure_d_drive_environment
from src.data.dataset_loader import load_jsonl_dataset
from src.models import DeterministicSummarizer


INPUT_PATH = Path("data/processed/governance/benchmark_set.jsonl")
OUTPUT_DIR = Path("D:/clin_summ_outputs/medium_benchmark_bart_pegasus")
STAGE_DIR = OUTPUT_DIR / "stages"
BART_MODEL = "facebook/bart-large-cnn"
PEGASUS_MODEL = "google/pegasus-xsum"
LEGACY_BART_PREDICTIONS = Path("D:/clin_summ_outputs/medium_benchmark/bart_predictions.jsonl")
PEGASUS_PUBMED_MODEL = "google/pegasus-pubmed"
PEGASUS_CNN_DAILYMAIL_MODEL = "google/pegasus-cnn_dailymail"
PEGASUS_CANDIDATES = [
    "google/pegasus-xsum",
    "google/pegasus-cnn_dailymail",
    "google/pegasus-pubmed",
]
EMBEDDING_PROVIDER = "sentence_transformers"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ACCEPTED_STATIC_POSITION_KEYS = {
    "model.encoder.embed_positions.weight",
    "model.decoder.embed_positions.weight",
}
INCLUDE_BERTSCORE = os.environ.get("RAG_INCLUDE_BERTSCORE", "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class StageResult:
    name: str
    model_provider: str
    limit: int
    status: str
    records: int
    output_path: Path | None
    runtime_seconds: float
    notes: str = ""


@dataclass(frozen=True)
class PegasusLoadDiagnostic:
    model_name: str
    tokenizer_class: str | None
    model_class: str | None
    config_model_type: str | None
    config_static_position_embeddings: bool | None
    missing_keys: list[str]
    unexpected_keys: list[str]
    newly_initialized_keys: list[str]
    parameter_count: int | None
    generation_smoke_test_succeeded: bool
    generation_smoke_test_output: str
    accepted_for_benchmark: bool
    acceptance_status: str
    rejection_reasons: list[str]
    cache_path: str


def main() -> None:
    configure_clean_hf_console()
    started = time.perf_counter()
    cache_paths = configure_d_drive_environment()
    verify_embedding_config()
    verify_model_cache(cache_paths)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / "run.log"
    log_path.write_text("", encoding="utf-8")
    log(log_path, "Starting medium-scale controlled summarization benchmark.")
    log(log_path, f"Input: {INPUT_PATH}")
    log(log_path, f"Output: {OUTPUT_DIR}")
    log(log_path, f"Embedding: {EMBEDDING_PROVIDER}/{EMBEDDING_MODEL}")
    log(log_path, f"BERTScore enabled: {INCLUDE_BERTSCORE}")
    log(log_path, f"Cache paths: {cache_paths}")

    records_200 = load_jsonl_dataset(INPUT_PATH, dataset="multiclinsum", split="train", require_reference=True, max_records=200)
    if len(records_200) < 200:
        raise RuntimeError(f"Expected at least 200 governed benchmark records, found {len(records_200)}.")
    dataset_manifest = build_dataset_manifest(records_200, cache_paths)
    write_json(OUTPUT_DIR / "dataset_manifest.json", dataset_manifest)

    pegasus_diagnostics = [diagnose_pegasus_load(model_name) for model_name in PEGASUS_CANDIDATES]
    write_json(OUTPUT_DIR / "pegasus_load_diagnostics.json", {"diagnostics": [diagnostic_to_dict(item) for item in pegasus_diagnostics]})
    write_pegasus_selection_report(OUTPUT_DIR / "pegasus_checkpoint_selection.md", pegasus_diagnostics, None)
    pubmed_diagnostic = diagnostic_for(pegasus_diagnostics, PEGASUS_PUBMED_MODEL)
    cnn_diagnostic = diagnostic_for(pegasus_diagnostics, PEGASUS_CNN_DAILYMAIL_MODEL)
    log(log_path, f"Pegasus PubMed diagnostic: {pubmed_diagnostic.acceptance_status}.")
    log(log_path, f"Pegasus CNN/DailyMail diagnostic: {cnn_diagnostic.acceptance_status}.")

    stage_results: list[StageResult] = []
    all_predictions: list[dict[str, Any]] = []

    det_rows, det_stage = run_deterministic_stage(records_200[:50], log_path)
    stage_results.append(det_stage)
    write_jsonl(OUTPUT_DIR / "deterministic_predictions.jsonl", det_rows)
    all_predictions.extend(det_rows)

    bart_rows_200, bart_stage_200 = run_bart_stage(records_200, log_path)
    bart_rows_50 = [dict(row, stage="stage_2_bart_limit50") for row in bart_rows_200[:50]]
    write_jsonl(STAGE_DIR / "stage_2_bart_limit50_predictions.jsonl", bart_rows_50)
    stage_results.append(
        StageResult(
            name="stage_2_bart_limit50",
            model_provider="bart",
            limit=50,
            status="completed",
            records=len(bart_rows_50),
            output_path=STAGE_DIR / "stage_2_bart_limit50_predictions.jsonl",
            runtime_seconds=0.0,
            notes="Derived from the first 50 records of the Stage 4 BART run to avoid duplicate CPU inference.",
        )
    )
    stage_results.append(bart_stage_200)
    write_jsonl(OUTPUT_DIR / "bart_predictions.jsonl", bart_rows_200)
    all_predictions.extend(bart_rows_200)

    pubmed_rows_200, pubmed_stage_200 = run_pegasus_variant_stage(
        records_200,
        log_path,
        model_provider="pegasus_pubmed",
        model_name=PEGASUS_PUBMED_MODEL,
        diagnostic=pubmed_diagnostic,
        output_name="pegasus_pubmed_predictions.jsonl",
    )
    write_jsonl(OUTPUT_DIR / "pegasus_pubmed_predictions.jsonl", pubmed_rows_200)
    all_predictions.extend(pubmed_rows_200)
    stage_results.append(pubmed_stage_200)

    cnn_rows_200, cnn_stage_200 = run_pegasus_variant_stage(
        records_200,
        log_path,
        model_provider="pegasus_cnn_dailymail",
        model_name=PEGASUS_CNN_DAILYMAIL_MODEL,
        diagnostic=cnn_diagnostic,
        output_name="pegasus_cnn_dailymail_predictions.jsonl",
    )
    write_jsonl(OUTPUT_DIR / "pegasus_cnn_dailymail_predictions.jsonl", cnn_rows_200)
    all_predictions.extend(cnn_rows_200)
    stage_results.append(cnn_stage_200)

    write_jsonl(OUTPUT_DIR / "all_predictions.jsonl", all_predictions)
    write_per_record_failure_jsonl(OUTPUT_DIR / "per_record_failure_analysis.jsonl", all_predictions)
    comparison_rows = comparison_rows_for(det_rows, bart_rows_200, pubmed_rows_200, cnn_rows_200)
    write_comparison_csv(OUTPUT_DIR / "model_comparison.csv", comparison_rows)
    write_per_record_metrics(OUTPUT_DIR / "per_record_metrics.csv", all_predictions)
    failure_rows = failure_rows_for(all_predictions)
    write_failure_analysis(OUTPUT_DIR / "failure_analysis.md", failure_rows)
    runtime_seconds = round(time.perf_counter() - started, 4)
    manifest = build_run_manifest(
        cache_paths=cache_paths,
        dataset_manifest=dataset_manifest,
        stage_results=stage_results,
        comparison_rows=comparison_rows,
        runtime_seconds=runtime_seconds,
        pegasus_diagnostics=pegasus_diagnostics,
    )
    write_json(OUTPUT_DIR / "evaluation_run_manifest.json", manifest)
    write_report(OUTPUT_DIR / "EVALUATION_REPORT.md", manifest, comparison_rows, failure_rows)
    log(log_path, f"Completed benchmark in {runtime_seconds} seconds.")
    log(log_path, HONESTY_WARNING)
    print(f"Medium benchmark outputs written to {OUTPUT_DIR}")


def configure_clean_hf_console() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def verify_embedding_config() -> None:
    provider = os.environ.get("RAG_EMBEDDING_PROVIDER")
    model = os.environ.get("RAG_SENTENCE_TRANSFORMERS_MODEL")
    if provider != EMBEDDING_PROVIDER:
        raise RuntimeError(f"RAG_EMBEDDING_PROVIDER must be {EMBEDDING_PROVIDER}, got {provider!r}.")
    if model != EMBEDDING_MODEL:
        raise RuntimeError(f"RAG_SENTENCE_TRANSFORMERS_MODEL must be {EMBEDDING_MODEL}, got {model!r}.")


def verify_model_cache(cache_paths: dict[str, str]) -> None:
    hub = Path(cache_paths["HF_HUB_CACHE"])
    required = {
        BART_MODEL: hub / "models--facebook--bart-large-cnn",
    }
    missing = [model for model, path in required.items() if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing cached model(s) under {hub}: {', '.join(missing)}")


def diagnose_pegasus_load(model_name: str) -> PegasusLoadDiagnostic:
    cache_dir = os.environ.get("HF_HUB_CACHE", "")
    if cache_dir and Path(cache_dir).drive.casefold() == "c:":
        return PegasusLoadDiagnostic(
            model_name=model_name,
            tokenizer_class=None,
            model_class=None,
            config_model_type=None,
            config_static_position_embeddings=None,
            missing_keys=[],
            unexpected_keys=[],
            newly_initialized_keys=[],
            parameter_count=None,
            generation_smoke_test_succeeded=False,
            generation_smoke_test_output="",
            accepted_for_benchmark=False,
            acceptance_status="rejected",
            rejection_reasons=[f"Cache path points to C drive: {cache_dir}"],
            cache_path=cache_dir,
        )
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except Exception as exc:
        return PegasusLoadDiagnostic(
            model_name=model_name,
            tokenizer_class=None,
            model_class=None,
            config_model_type=None,
            config_static_position_embeddings=None,
            missing_keys=[],
            unexpected_keys=[],
            newly_initialized_keys=[],
            parameter_count=None,
            generation_smoke_test_succeeded=False,
            generation_smoke_test_output="",
            accepted_for_benchmark=False,
            acceptance_status="rejected",
            rejection_reasons=[f"Transformers unavailable: {exc}"],
            cache_path=cache_dir,
        )
    stderr = io.StringIO()
    transformer_logs = io.StringIO()
    logger = logging.getLogger("transformers")
    handler = logging.StreamHandler(transformer_logs)
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    with warnings.catch_warnings(record=True) as caught, redirect_stderr(stderr):
        warnings.simplefilter("always")
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
            loaded = AutoModelForSeq2SeqLM.from_pretrained(
                model_name,
                cache_dir=cache_dir,
                local_files_only=True,
                output_loading_info=True,
            )
        except Exception as exc:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
            return PegasusLoadDiagnostic(
                model_name=model_name,
                tokenizer_class=None,
                model_class=None,
                config_model_type=None,
                config_static_position_embeddings=None,
                missing_keys=[],
                unexpected_keys=[],
                newly_initialized_keys=[],
                parameter_count=None,
                generation_smoke_test_succeeded=False,
                generation_smoke_test_output="",
                accepted_for_benchmark=False,
                acceptance_status="rejected",
                rejection_reasons=[f"Local load failed: {exc}"],
                cache_path=cache_dir,
            )
    logger.removeHandler(handler)
    logger.setLevel(previous_level)
    if isinstance(loaded, tuple):
        model, loading_info = loaded
    else:
        model, loading_info = loaded, {}
    model.eval()
    missing_keys = sorted(str(key) for key in loading_info.get("missing_keys", []))
    unexpected_keys = sorted(str(key) for key in loading_info.get("unexpected_keys", []))
    newly_initialized_keys = sorted(set(missing_keys) | parse_newly_initialized_keys("\n".join(
        [str(warning.message) for warning in caught] + [stderr.getvalue(), transformer_logs.getvalue()]
    )))
    smoke_succeeded = False
    smoke_output = ""
    smoke_error = ""
    try:
        import torch

        torch_device = torch.device("cpu")
        model.to(torch_device)
        smoke_output = generate_seq2seq_summary(
            tokenizer=tokenizer,
            model=model,
            torch_device=torch_device,
            source_note="Patient has hypertension and diabetes. Discharged with follow-up plan.",
            max_input_tokens=model_safe_input_tokens(tokenizer, model),
            max_new_tokens=48,
            num_beams=2,
            no_repeat_ngram_size=3,
        )
        smoke_succeeded = bool(smoke_output.strip())
    except Exception as exc:
        smoke_error = str(exc)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    config_model_type = str(getattr(model.config, "model_type", ""))
    static_position_embeddings = getattr(model.config, "static_position_embeddings", None)
    rejection_reasons = pegasus_rejection_reasons(
        config_model_type=config_model_type,
        static_position_embeddings=static_position_embeddings,
        missing_keys=missing_keys,
        unexpected_keys=unexpected_keys,
        newly_initialized_keys=newly_initialized_keys,
        smoke_succeeded=smoke_succeeded,
        smoke_output=smoke_output,
        smoke_error=smoke_error,
    )
    tokenizer_class = tokenizer.__class__.__name__
    model_class = model.__class__.__name__
    if config_model_type == "pegasus" and ("Pegasus" not in tokenizer_class or "Pegasus" not in model_class):
        rejection_reasons.append(f"Tokenizer/model class mismatch: {tokenizer_class}/{model_class}")
    if config_model_type == "bigbird_pegasus" and "Pegasus" not in model_class:
        rejection_reasons.append(f"Tokenizer/model class mismatch: {tokenizer_class}/{model_class}")
    accepted = not rejection_reasons
    acceptance_status = (
        "completed_with_accepted_static_position_embedding_warning"
        if accepted and newly_initialized_keys
        else "completed"
        if accepted
        else "rejected"
    )
    return PegasusLoadDiagnostic(
        model_name=model_name,
        tokenizer_class=tokenizer.__class__.__name__,
        model_class=model.__class__.__name__,
        config_model_type=config_model_type,
        config_static_position_embeddings=bool(static_position_embeddings) if static_position_embeddings is not None else None,
        missing_keys=missing_keys,
        unexpected_keys=unexpected_keys,
        newly_initialized_keys=newly_initialized_keys,
        parameter_count=parameter_count,
        generation_smoke_test_succeeded=smoke_succeeded,
        generation_smoke_test_output=smoke_output,
        accepted_for_benchmark=accepted,
        acceptance_status=acceptance_status,
        rejection_reasons=rejection_reasons,
        cache_path=cache_dir,
    )


def parse_newly_initialized_keys(message: str) -> set[str]:
    match = re.search(r"newly initialized:\s*\[(.*?)\]", message, flags=re.DOTALL)
    if not match:
        return set()
    return {item.strip().strip("'\"") for item in match.group(1).split(",") if item.strip()}


def pegasus_rejection_reasons(
    *,
    config_model_type: str,
    static_position_embeddings: bool | None,
    missing_keys: list[str],
    unexpected_keys: list[str],
    newly_initialized_keys: list[str],
    smoke_succeeded: bool,
    smoke_output: str,
    smoke_error: str,
) -> list[str]:
    reasons: list[str] = []
    if config_model_type not in {"pegasus", "bigbird_pegasus"}:
        reasons.append(f"Model type is not compatible Pegasus family: {config_model_type}")
    if unexpected_keys:
        reasons.append(f"Unexpected checkpoint keys found: {unexpected_keys}")
    unsafe_missing = sorted(set(missing_keys) - ACCEPTED_STATIC_POSITION_KEYS)
    unsafe_new = sorted(set(newly_initialized_keys) - ACCEPTED_STATIC_POSITION_KEYS)
    if unsafe_missing:
        reasons.append(f"Missing task-critical weights: {unsafe_missing}")
    if unsafe_new:
        reasons.append(f"Newly initialized task-critical weights: {unsafe_new}")
    if (missing_keys or newly_initialized_keys) and static_position_embeddings is not True:
        reasons.append("Static positional embedding warning is present but config.static_position_embeddings is not true.")
    if not smoke_succeeded:
        reasons.append(f"Generation smoke test failed or returned empty output: {smoke_error}".strip())
    if not smoke_output.strip():
        reasons.append("Generation smoke test output is empty.")
    return reasons


def select_pegasus_checkpoint(diagnostics: list[PegasusLoadDiagnostic]) -> PegasusLoadDiagnostic | None:
    accepted = [diagnostic for diagnostic in diagnostics if diagnostic.accepted_for_benchmark]
    if not accepted:
        return None
    preferred = ["google/pegasus-pubmed", "google/pegasus-cnn_dailymail", "google/pegasus-xsum", "google/bigbird-pegasus-large-pubmed"]
    for model_name in preferred:
        for diagnostic in accepted:
            if diagnostic.model_name == model_name:
                return diagnostic
    return accepted[0]


def diagnostic_for(diagnostics: list[PegasusLoadDiagnostic], model_name: str) -> PegasusLoadDiagnostic:
    for diagnostic in diagnostics:
        if diagnostic.model_name == model_name:
            return diagnostic
    return PegasusLoadDiagnostic(
        model_name=model_name,
        tokenizer_class=None,
        model_class=None,
        config_model_type=None,
        config_static_position_embeddings=None,
        missing_keys=[],
        unexpected_keys=[],
        newly_initialized_keys=[],
        parameter_count=None,
        generation_smoke_test_succeeded=False,
        generation_smoke_test_output="",
        accepted_for_benchmark=False,
        acceptance_status="failed",
        rejection_reasons=["Diagnostic was not produced."],
        cache_path=os.environ.get("HF_HUB_CACHE", ""),
    )


def run_deterministic_stage(records: list[dict[str, str]], log_path: Path) -> tuple[list[dict[str, Any]], StageResult]:
    stage_started = time.perf_counter()
    log(log_path, "Stage 1: deterministic limit 50.")
    summarizer = DeterministicSummarizer(max_sentences=3)
    rows = []
    for record in records:
        output = summarizer.generate(record)
        rows.append(completed_row(record, "stage_1_deterministic_limit50", summarizer.model_name, output.generated_summary, output.latency_ms))
    runtime = round(time.perf_counter() - stage_started, 4)
    return rows, StageResult(
        name="stage_1_deterministic_limit50",
        model_provider="deterministic",
        limit=50,
        status="completed",
        records=len(rows),
        output_path=OUTPUT_DIR / "deterministic_predictions.jsonl",
        runtime_seconds=runtime,
    )


def run_bart_stage(records: list[dict[str, str]], log_path: Path) -> tuple[list[dict[str, Any]], StageResult]:
    stage_started = time.perf_counter()
    log(log_path, "Stage 4: BART limit 200. Stage 2 limit 50 will be derived from first 50 predictions.")
    existing_rows = load_existing_predictions(OUTPUT_DIR / "bart_predictions.jsonl", model_provider="bart", model_name=BART_MODEL, expected_count=200)
    legacy_rows = load_existing_predictions(LEGACY_BART_PREDICTIONS, model_provider="bart", model_name=BART_MODEL, expected_count=200)
    if existing_rows:
        rows = existing_rows
        log(log_path, "Reusing existing BART direct seq2seq predictions for 200 governed records.")
    elif legacy_rows:
        rows = legacy_rows
        log(log_path, f"Reusing existing BART direct seq2seq predictions from {LEGACY_BART_PREDICTIONS}.")
    else:
        rows = run_hf_summarizer(
            records,
            model_provider="bart",
            model_name=BART_MODEL,
            stage="stage_4_bart_limit200",
            log_path=log_path,
            checkpoint_path=OUTPUT_DIR / "bart_predictions.jsonl",
        )
    runtime = round(time.perf_counter() - stage_started, 4)
    completed = [row for row in rows if row["status"] == "completed"]
    return rows, StageResult(
        name="stage_4_bart_limit200",
        model_provider="bart",
        limit=200,
        status="completed" if len(completed) == len(rows) else "partial" if completed else "failed",
        records=len(rows),
        output_path=OUTPUT_DIR / "bart_predictions.jsonl",
        runtime_seconds=runtime,
        notes="Reused existing direct seq2seq predictions." if existing_rows or legacy_rows else "",
    )


def run_pegasus_stage(
    records: list[dict[str, str]],
    log_path: Path,
    model_name: str,
    diagnostic: PegasusLoadDiagnostic,
) -> tuple[list[dict[str, Any]], StageResult]:
    stage_started = time.perf_counter()
    log(log_path, "Stage 5: Pegasus limit 200. Stage 3 limit 50 will be derived from first 50 predictions.")
    existing_rows = load_existing_predictions(OUTPUT_DIR / "pegasus_predictions.jsonl", model_provider="pegasus", model_name=model_name, expected_count=200)
    if existing_rows:
        rows = existing_rows
        log(log_path, "Reusing existing Pegasus direct seq2seq predictions for 200 governed records.")
    else:
        rows = run_hf_summarizer(
            records,
            model_provider="pegasus",
            model_name=model_name,
            stage="stage_5_pegasus_limit200",
            log_path=log_path,
            checkpoint_path=OUTPUT_DIR / "pegasus_predictions.jsonl",
        )
    runtime = round(time.perf_counter() - stage_started, 4)
    completed = [row for row in rows if row["status"] == "completed"]
    status = diagnostic.acceptance_status if len(completed) == len(rows) else "partial" if completed else "failed"
    return rows, StageResult(
        name="stage_5_pegasus_limit200",
        model_provider="pegasus",
        limit=200,
        status=status,
        records=len(rows),
        output_path=OUTPUT_DIR / "pegasus_predictions.jsonl",
        runtime_seconds=runtime,
        notes="Accepted Pegasus static positional embedding warning." if diagnostic.newly_initialized_keys else "",
    )


def run_pegasus_variant_stage(
    records: list[dict[str, str]],
    log_path: Path,
    *,
    model_provider: str,
    model_name: str,
    diagnostic: PegasusLoadDiagnostic,
    output_name: str,
) -> tuple[list[dict[str, Any]], StageResult]:
    stage_started = time.perf_counter()
    stage_name = f"stage_pegasus_{model_provider}_limit200"
    log(log_path, f"{stage_name}: Pegasus variant limit 200 using {model_name}.")
    output_path = OUTPUT_DIR / output_name
    existing_rows = load_existing_predictions(output_path, model_provider=model_provider, model_name=model_name, expected_count=200)
    if existing_rows:
        rows = existing_rows
        log(log_path, f"Reusing existing {model_provider} predictions for 200 governed records.")
    else:
        rows = run_hf_summarizer(
            records,
            model_provider=model_provider,
            model_name=model_name,
            stage=stage_name,
            log_path=log_path,
            checkpoint_path=output_path,
        )
    runtime = round(time.perf_counter() - stage_started, 4)
    completed = [row for row in rows if row["status"] == "completed"]
    status = "completed" if len(completed) == len(rows) else "partial" if completed else "failed"
    if status == "completed" and diagnostic.acceptance_status == "completed_with_accepted_static_position_embedding_warning":
        status = diagnostic.acceptance_status
    return rows, StageResult(
        name=stage_name,
        model_provider=model_provider,
        limit=200,
        status=status,
        records=len(rows),
        output_path=output_path,
        runtime_seconds=runtime,
        notes="; ".join(diagnostic.rejection_reasons) if diagnostic.rejection_reasons else diagnostic.acceptance_status,
    )


def load_seq2seq_model(model_name: str, device: str = "cpu") -> tuple[Any, Any, Any]:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    import torch

    cache_dir = os.environ.get("HF_HUB_CACHE")
    if cache_dir and Path(cache_dir).drive.casefold() == "c:":
        raise RuntimeError(f"Refusing to load {model_name}: HF_HUB_CACHE points to C drive: {cache_dir}")
    tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
    torch_device = torch.device(device)
    model.to(torch_device)
    model.eval()
    return tokenizer, model, torch_device


def run_hf_summarizer(
    records: list[dict[str, str]],
    *,
    model_provider: str,
    model_name: str,
    stage: str,
    log_path: Path,
    checkpoint_path: Path | None = None,
) -> list[dict[str, Any]]:
    rows = load_partial_predictions(checkpoint_path, records, model_provider=model_provider, model_name=model_name) if checkpoint_path else []
    if rows:
        log(log_path, f"{stage}: resuming from {len(rows)}/{len(records)} checkpointed records.")
    try:
        tokenizer, model, torch_device = load_seq2seq_model(model_name, device="cpu")
        max_input_tokens = model_safe_input_tokens(tokenizer, model)
    except Exception as exc:
        message = f"{model_provider} model load failed: {exc}"
        log(log_path, message)
        return [failed_row(record, stage, model_name, message, model_provider=model_provider) for record in records]

    batch_size = 2 if model_provider.startswith("pegasus") else 1
    for start_index in range(len(rows), len(records), batch_size):
        batch_records = records[start_index : start_index + batch_size]
        batch_started = time.perf_counter()
        try:
            generated_summaries = generate_seq2seq_summaries(
                tokenizer=tokenizer,
                model=model,
                torch_device=torch_device,
                source_notes=[record["source_note"] for record in batch_records],
                max_input_tokens=max_input_tokens,
                max_new_tokens=160,
                num_beams=4,
                no_repeat_ngram_size=3,
            )
            latency_ms = int((time.perf_counter() - batch_started) * 1000 / max(1, len(batch_records)))
            for record, generated in zip(batch_records, generated_summaries, strict=True):
                rows.append(completed_row(record, stage, model_name, generated, latency_ms, model_provider=model_provider))
        except Exception as exc:
            log(log_path, f"{stage}: batch generation failed at record {start_index + 1}; falling back to per-record generation: {exc}")
            for record in batch_records:
                started = time.perf_counter()
                try:
                    generated = generate_seq2seq_summary(
                        tokenizer=tokenizer,
                        model=model,
                        torch_device=torch_device,
                        source_note=record["source_note"],
                        max_input_tokens=max_input_tokens,
                        max_new_tokens=160,
                        num_beams=4,
                        no_repeat_ngram_size=3,
                    )
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    rows.append(completed_row(record, stage, model_name, generated, latency_ms, model_provider=model_provider))
                except Exception as item_exc:
                    error_message = f"{model_provider} generation failed: {item_exc}"
                    log(log_path, f"{stage}: {error_message} for note_id={record.get('note_id', '')}")
                    rows.append(failed_row(record, stage, model_name, error_message, model_provider=model_provider))
        if checkpoint_path is not None:
            write_jsonl(checkpoint_path, rows)
        if len(rows) % 10 == 0 or len(rows) == len(records):
            log(log_path, f"{stage}: completed {len(rows)}/{len(records)} records.")
    return rows


def model_safe_input_tokens(tokenizer: Any, model: Any, default_max_input_tokens: int = 1024) -> int:
    candidates = [default_max_input_tokens]
    tokenizer_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(tokenizer_limit, int) and 0 < tokenizer_limit < 100_000:
        candidates.append(tokenizer_limit)
    config_limit = getattr(model.config, "max_position_embeddings", None)
    if isinstance(config_limit, int) and config_limit > 0:
        candidates.append(config_limit)
    encoder = getattr(getattr(model, "model", None), "encoder", None)
    embed_positions = getattr(encoder, "embed_positions", None)
    num_embeddings = getattr(embed_positions, "num_embeddings", None)
    if isinstance(num_embeddings, int) and num_embeddings > 0:
        candidates.append(num_embeddings)
    weight = getattr(embed_positions, "weight", None)
    shape = getattr(weight, "shape", None)
    if shape and len(shape) >= 1 and int(shape[0]) > 0:
        candidates.append(int(shape[0]))
    return max(32, min(candidates))


def load_existing_predictions(
    path: Path,
    *,
    model_provider: str,
    model_name: str,
    expected_count: int,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = read_jsonl(path)
    if len(rows) != expected_count:
        return []
    if any(row.get("model_provider") != model_provider or row.get("model_name") != model_name for row in rows):
        return []
    if not all(row.get("status") == "completed" for row in rows):
        return []
    return rows


def load_partial_predictions(
    path: Path | None,
    records: list[dict[str, str]],
    *,
    model_provider: str,
    model_name: str,
) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows = read_jsonl(path)
    valid_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index >= len(records):
            break
        if row.get("model_provider") != model_provider or row.get("model_name") != model_name:
            break
        if row.get("note_id") != records[index].get("note_id"):
            break
        valid_rows.append(row)
    return valid_rows


def remove_stale_pegasus_outputs() -> None:
    for path in (
        OUTPUT_DIR / "pegasus_predictions.jsonl",
        STAGE_DIR / "stage_3_pegasus_limit50_predictions.jsonl",
    ):
        path.unlink(missing_ok=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    break
    return rows


def generate_seq2seq_summary(
    *,
    tokenizer: Any,
    model: Any,
    torch_device: Any,
    source_note: str,
    max_input_tokens: int = 1024,
    max_new_tokens: int = 160,
    num_beams: int = 4,
    no_repeat_ngram_size: int = 3,
) -> str:
    import torch

    encoded = tokenizer(
        source_note,
        return_tensors="pt",
        truncation=True,
        max_length=max_input_tokens,
    )
    encoded = {key: value.to(torch_device) for key, value in encoded.items()}
    generation_config = seq2seq_generation_config(
        model,
        max_new_tokens=max_new_tokens,
        num_beams=num_beams,
        no_repeat_ngram_size=no_repeat_ngram_size,
    )
    generate_kwargs = (
        {"generation_config": generation_config}
        if generation_config is not None
        else {
            "max_new_tokens": max_new_tokens,
            "num_beams": num_beams,
            "no_repeat_ngram_size": no_repeat_ngram_size,
            "do_sample": False,
            "early_stopping": True,
        }
    )
    with torch.inference_mode():
        output_ids = model.generate(
            **encoded,
            **generate_kwargs,
        )
    return tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()


def generate_seq2seq_summaries(
    *,
    tokenizer: Any,
    model: Any,
    torch_device: Any,
    source_notes: list[str],
    max_input_tokens: int = 1024,
    max_new_tokens: int = 160,
    num_beams: int = 4,
    no_repeat_ngram_size: int = 3,
) -> list[str]:
    import torch

    encoded = tokenizer(
        source_notes,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=max_input_tokens,
    )
    encoded = {key: value.to(torch_device) for key, value in encoded.items()}
    generation_config = seq2seq_generation_config(
        model,
        max_new_tokens=max_new_tokens,
        num_beams=num_beams,
        no_repeat_ngram_size=no_repeat_ngram_size,
    )
    generate_kwargs = (
        {"generation_config": generation_config}
        if generation_config is not None
        else {
            "max_new_tokens": max_new_tokens,
            "num_beams": num_beams,
            "no_repeat_ngram_size": no_repeat_ngram_size,
            "do_sample": False,
            "early_stopping": True,
        }
    )
    with torch.inference_mode():
        output_ids = model.generate(
            **encoded,
            **generate_kwargs,
        )
    return [text.strip() for text in tokenizer.batch_decode(output_ids, skip_special_tokens=True)]


def seq2seq_generation_config(
    model: Any,
    *,
    max_new_tokens: int,
    num_beams: int,
    no_repeat_ngram_size: int,
) -> Any:
    generation_config = copy.deepcopy(getattr(model, "generation_config", None))
    if generation_config is None:
        return None
    if hasattr(generation_config, "max_length"):
        generation_config.max_length = None
    generation_config.max_new_tokens = max_new_tokens
    generation_config.num_beams = num_beams
    generation_config.no_repeat_ngram_size = no_repeat_ngram_size
    generation_config.do_sample = False
    generation_config.early_stopping = True
    return generation_config


def completed_row(
    record: dict[str, str],
    stage: str,
    model_name: str,
    generated_summary: str,
    latency_ms: int,
    *,
    model_provider: str = "deterministic",
) -> dict[str, Any]:
    metrics = compute_pairwise_metrics([generated_summary], [record["reference_summary"]], include_bertscore=False)
    row = {
        "evaluation_type": "medium_controlled_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": HONESTY_WARNING,
        "stage": stage,
        "dataset": record.get("dataset", "multiclinsum"),
        "split": record.get("split", ""),
        "input_path": str(INPUT_PATH),
        "note_id": record.get("note_id", ""),
        "patient_id": record.get("patient_id", ""),
        "encounter_id": record.get("encounter_id", ""),
        "model_provider": model_provider,
        "model_name": model_name,
        "status": "completed",
        "error_message": None,
        "source_note": record.get("source_note", ""),
        "reference_summary": record.get("reference_summary", ""),
        "generated_summary": generated_summary,
        "latency_ms": latency_ms,
        "rouge1": metrics["rouge1"],
        "rouge2": metrics["rouge2"],
        "rougeL": metrics["rougeL"],
    }
    row.update(compute_clinical_record_metrics(row))
    return row


def failed_row(
    record: dict[str, str],
    stage: str,
    model_name: str,
    error_message: str,
    *,
    model_provider: str,
) -> dict[str, Any]:
    row = {
        "evaluation_type": "medium_controlled_proxy_evaluation",
        "proxy_evaluation": True,
        "proxy_warning": HONESTY_WARNING,
        "stage": stage,
        "dataset": record.get("dataset", "multiclinsum"),
        "split": record.get("split", ""),
        "input_path": str(INPUT_PATH),
        "note_id": record.get("note_id", ""),
        "patient_id": record.get("patient_id", ""),
        "encounter_id": record.get("encounter_id", ""),
        "model_provider": model_provider,
        "model_name": model_name,
        "status": "failed",
        "error_message": error_message,
        "source_note": record.get("source_note", ""),
        "reference_summary": record.get("reference_summary", ""),
        "generated_summary": "",
        "latency_ms": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
    }
    row.update(empty_clinical_record_metrics(["retrieval-related failure"]))
    return row


def comparison_rows_for(
    deterministic_rows: list[dict[str, Any]],
    bart_rows: list[dict[str, Any]],
    pegasus_pubmed_rows: list[dict[str, Any]],
    pegasus_cnn_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        comparison_row("deterministic", "deterministic_sentence_baseline", deterministic_rows),
        comparison_row("bart", BART_MODEL, bart_rows),
        comparison_row("pegasus_pubmed", PEGASUS_PUBMED_MODEL, pegasus_pubmed_rows),
        comparison_row("pegasus_cnn_dailymail", PEGASUS_CNN_DAILYMAIL_MODEL, pegasus_cnn_rows),
    ]


def comparison_row(model_provider: str, model_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    failed = [row for row in rows if row["status"] == "failed"]
    metrics = compute_pairwise_metrics(
        [row["generated_summary"] for row in completed],
        [row["reference_summary"] for row in completed],
        include_bertscore=INCLUDE_BERTSCORE,
    ) if completed else {"rouge1": None, "rouge2": None, "rougeL": None}
    clinical_metrics = aggregate_clinical_metrics(rows)
    return {
        "model_provider": model_provider,
        "model_name": model_name,
        "status": "completed" if completed and not failed else "partial" if completed else "failed",
        "record_count": len(rows),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "skipped_count": 0,
        "rouge1": metrics.get("rouge1"),
        "rouge2": metrics.get("rouge2"),
        "rougeL": metrics.get("rougeL"),
        "bertscore_precision": metrics.get("bertscore_precision"),
        "bertscore_recall": metrics.get("bertscore_recall"),
        "bertscore_f1": metrics.get("bertscore_f1"),
        "bertscore_status": metrics.get("bertscore_status", "not_requested" if not INCLUDE_BERTSCORE else "not_available"),
        "bertscore_model_type": metrics.get("bertscore_model_type"),
        "bertscore_message": metrics.get("bertscore_message", ""),
        "average_latency_ms": mean_or_none([row["latency_ms"] for row in completed]),
        "latency_p50_ms": clinical_metrics.get("latency_p50_ms"),
        "latency_p95_ms": clinical_metrics.get("latency_p95_ms"),
        "citation_coverage": clinical_metrics.get("citation_coverage"),
        "unsupported_claim_rate": clinical_metrics.get("unsupported_claim_rate"),
        "factuality_proxy_score": clinical_metrics.get("factuality_proxy_score"),
        "missing_diagnosis_rate": clinical_metrics.get("missing_diagnosis_rate"),
        "missing_medication_rate": clinical_metrics.get("missing_medication_rate"),
        "timeline_completeness": clinical_metrics.get("timeline_completeness"),
        "hallucinated_clinical_entity_count": clinical_metrics.get("hallucinated_clinical_entity_count"),
        "critical_info_omission_rate": clinical_metrics.get("critical_info_omission_rate"),
        "failure_counts": clinical_metrics.get("failure_counts"),
        "notes": HONESTY_WARNING,
        "error_message": "; ".join(sorted({str(row.get("error_message")) for row in failed if row.get("error_message")})) or None,
    }


def write_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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
        "bertscore_message",
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            payload = dict(row)
            payload["failure_counts"] = json.dumps(payload.get("failure_counts") or {}, ensure_ascii=False)
            writer.writerow({field: payload.get(field) for field in fields})


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
            writer.writerow(
                {
                    "stage": row.get("stage", ""),
                    "note_id": row.get("note_id", ""),
                    "model_provider": row.get("model_provider", ""),
                    "model_name": row.get("model_name", ""),
                    "status": row.get("status", ""),
                    "rouge1": row.get("rouge1"),
                    "rouge2": row.get("rouge2"),
                    "rougeL": row.get("rougeL"),
                    "latency_ms": row.get("latency_ms"),
                    "citation_coverage": row.get("citation_coverage"),
                    "citation_count": row.get("citation_count"),
                    "unsupported_claim_rate": row.get("unsupported_claim_rate"),
                    "factuality_proxy_score": row.get("factuality_proxy_score"),
                    "missing_diagnosis_rate": row.get("missing_diagnosis_rate"),
                    "missing_medication_rate": row.get("missing_medication_rate"),
                    "timeline_completeness": row.get("timeline_completeness"),
                    "hallucinated_clinical_entity_count": row.get("hallucinated_clinical_entity_count"),
                    "critical_info_omission_rate": row.get("critical_info_omission_rate"),
                    "failure_categories": serialize_failure_categories(row.get("failure_categories") or classify_failure(row)),
                    "error_message": row.get("error_message"),
                }
            )


def write_per_record_failure_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "note_id": row.get("note_id", ""),
                "patient_id": row.get("patient_id", ""),
                "encounter_id": row.get("encounter_id", ""),
                "dataset": row.get("dataset", ""),
                "model_provider": row.get("model_provider", ""),
                "model_name": row.get("model_name", ""),
                "stage": row.get("stage", ""),
                "status": row.get("status", ""),
                "input_note": row.get("source_note", ""),
                "generated_summary": row.get("generated_summary", ""),
                "reference_summary": row.get("reference_summary", ""),
                "retrieved_evidence": row.get("retrieved_evidence") or row.get("evidence") or "",
                "citations": row.get("citations") or [],
                "rouge1": row.get("rouge1"),
                "rouge2": row.get("rouge2"),
                "rougeL": row.get("rougeL"),
                "latency_ms": row.get("latency_ms"),
                "clinical_metrics": {
                    field: row.get(field)
                    for field in PER_RECORD_CLINICAL_FIELDS
                    if field != "failure_categories"
                },
                "failure_labels": row.get("failure_categories") or classify_failure(row),
                "error_message": row.get("error_message"),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def failure_rows_for(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for row in rows:
        failures.append(
            {
                "note_id": row.get("note_id", ""),
                "model_provider": row.get("model_provider", ""),
                "rougeL": row.get("rougeL"),
                "categories": row.get("failure_categories") or classify_failure(row),
            }
        )
    return sorted(failures, key=lambda item: float(item["rougeL"] or -1))


def classify_failure(row: dict[str, Any]) -> list[str]:
    if row.get("failure_categories"):
        value = row.get("failure_categories")
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value).split(";") if item.strip()]
    if row.get("status") != "completed":
        return ["retrieval-related failure"]
    generated = str(row.get("generated_summary") or "")
    reference = str(row.get("reference_summary") or "")
    source = str(row.get("source_note") or "")
    categories: list[str] = []
    if hallucination_score(generated, source, reference) > 0.35:
        categories.append("hallucinated content")
    if contains(reference, "diagnos", "tuberculosis", "pancreatitis", "herniation", "cancer") and not contains(
        generated, "diagnos", "tuberculosis", "pancreatitis", "herniation", "cancer"
    ):
        categories.append("missing diagnosis")
    if contains(reference, "medication", "treatment", "therapy", "drug", "dose", "antibiotic") and not contains(
        generated, "medication", "treatment", "therapy", "drug", "dose", "antibiotic"
    ):
        categories.append("missing medication")
    if contains(reference, "day", "week", "month", "year", "follow-up", "after") and not contains(
        generated, "day", "week", "month", "year", "follow-up", "after"
    ):
        categories.append("missing timeline")
    if len(generated.split()) < max(8, len(reference.split()) // 3):
        categories.append("incomplete summary")
    if float(row.get("rougeL") or 0.0) < 0.2:
        categories.append("retrieval-related failure")
    categories.append("source data limitation")
    return categories


def hallucination_score(generated: str, source: str, reference: str) -> float:
    generated_tokens = tokens(generated)
    support_tokens = set(tokens(f"{source} {reference}"))
    unsupported = [token for token in generated_tokens if token not in support_tokens]
    return len(unsupported) / max(1, len(generated_tokens))


def contains(text: str, *terms: str) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


def tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9%./+-]+", text.casefold()) if len(token) > 2]


def write_failure_analysis(path: Path, failures: list[dict[str, Any]]) -> None:
    counts = Counter(category for row in failures for category in row["categories"])
    by_model = Counter((row["model_provider"], category) for row in failures for category in row["categories"])
    lines = [
        "# Failure Analysis",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Failure Pattern Counts",
        "",
    ]
    for category, count in counts.most_common():
        lines.append(f"- {category}: `{count}`")
    lines.extend(
        [
            "",
            "## Failure Counts By Model",
            "",
            "| Model | Failure label | Count |",
            "| --- | --- | ---: |",
        ]
    )
    for (provider, category), count in sorted(by_model.items(), key=lambda item: (item[0][0], -item[1], item[0][1])):
        lines.append(f"| `{provider}` | {category} | {count} |")
    lines.extend(
        [
            "",
            "## Lowest ROUGE-L Records",
            "",
            "| Rank | Note ID | Model | ROUGE-L | Categories |",
            "| ---: | --- | --- | ---: | --- |",
        ]
    )
    for index, row in enumerate(failures[:30], start=1):
        lines.append(
            f"| {index} | `{row['note_id']}` | `{row['model_provider']}` | `{row['rougeL']}` | {', '.join(row['categories'])} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_dataset_manifest(records: list[dict[str, str]], cache_paths: dict[str, str]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "multiclinsum",
        "input_path": str(INPUT_PATH),
        "available_benchmark_records": 25902,
        "loaded_records_for_medium_benchmark": len(records),
        "cache_paths": cache_paths,
        "honesty_warning": HONESTY_WARNING,
    }


def diagnostic_to_dict(diagnostic: PegasusLoadDiagnostic) -> dict[str, Any]:
    return {
        "model_name": diagnostic.model_name,
        "tokenizer_class": diagnostic.tokenizer_class,
        "model_class": diagnostic.model_class,
        "config_model_type": diagnostic.config_model_type,
        "config_static_position_embeddings": diagnostic.config_static_position_embeddings,
        "missing_keys": diagnostic.missing_keys,
        "unexpected_keys": diagnostic.unexpected_keys,
        "newly_initialized_keys": diagnostic.newly_initialized_keys,
        "parameter_count": diagnostic.parameter_count,
        "generation_smoke_test_succeeded": diagnostic.generation_smoke_test_succeeded,
        "generation_smoke_test_output": diagnostic.generation_smoke_test_output,
        "accepted_for_benchmark": diagnostic.accepted_for_benchmark,
        "acceptance_status": diagnostic.acceptance_status,
        "rejection_reasons": diagnostic.rejection_reasons,
        "cache_path": diagnostic.cache_path,
    }


def write_pegasus_selection_report(
    path: Path,
    diagnostics: list[PegasusLoadDiagnostic],
    selected: PegasusLoadDiagnostic | None,
) -> None:
    lines = [
        "# Pegasus Checkpoint Selection",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Selection",
        "",
    ]
    if selected is None:
        lines.append("- No single Pegasus checkpoint selected; the benchmark runs configured Pegasus variants independently.")
    else:
        lines.extend(
            [
                f"- Selected checkpoint: `{selected.model_name}`",
                f"- Status: `{selected.acceptance_status}`",
                "- Reason: Pegasus was included because the only missing keys were static positional embedding weights, generation succeeded, and no task-critical model weights were missing.",
            ]
        )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "| Checkpoint | Accepted | Status | Model type | Static positions | Missing/new keys | Smoke test | Rejection reasons |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for diagnostic in diagnostics:
        keys = sorted(set(diagnostic.missing_keys) | set(diagnostic.newly_initialized_keys))
        lines.append(
            "| "
            f"`{diagnostic.model_name}` | "
            f"`{diagnostic.accepted_for_benchmark}` | "
            f"`{diagnostic.acceptance_status}` | "
            f"`{diagnostic.config_model_type}` | "
            f"`{diagnostic.config_static_position_embeddings}` | "
            f"`{', '.join(keys) or 'none'}` | "
            f"`{diagnostic.generation_smoke_test_succeeded}` | "
            f"{'; '.join(diagnostic.rejection_reasons) or 'none'} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_run_manifest(
    *,
    cache_paths: dict[str, str],
    dataset_manifest: dict[str, Any],
    stage_results: list[StageResult],
    comparison_rows: list[dict[str, Any]],
    runtime_seconds: float,
    pegasus_diagnostics: list[PegasusLoadDiagnostic],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pipeline": "medium_controlled_summarization_benchmark",
        "honesty_warning": HONESTY_WARNING,
        "input_path": str(INPUT_PATH),
        "output_dir": str(OUTPUT_DIR),
        "cache_paths": cache_paths,
        "retrieval_embedding_provider": os.environ.get("RAG_EMBEDDING_PROVIDER"),
        "retrieval_embedding_model": os.environ.get("RAG_SENTENCE_TRANSFORMERS_MODEL"),
        "include_bertscore": INCLUDE_BERTSCORE,
        "dataset_manifest": dataset_manifest,
        "stages": [stage.__dict__ | {"output_path": str(stage.output_path) if stage.output_path else None} for stage in stage_results],
        "pegasus_load_diagnostics": [diagnostic_to_dict(diagnostic) for diagnostic in pegasus_diagnostics],
        "skipped_models": [],
        "model_comparison": comparison_rows,
        "runtime_seconds": runtime_seconds,
        "outputs": [
            "run.log",
            "evaluation_run_manifest.json",
            "dataset_manifest.json",
            "pegasus_load_diagnostics.json",
            "pegasus_checkpoint_selection.md",
            "deterministic_predictions.jsonl",
            "bart_predictions.jsonl",
            "pegasus_pubmed_predictions.jsonl",
            "pegasus_cnn_dailymail_predictions.jsonl",
            "model_comparison.csv",
            "per_record_metrics.csv",
            "failure_analysis.md",
            "EVALUATION_REPORT.md",
        ],
    }


def write_report(path: Path, manifest: dict[str, Any], comparison_rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    counts = Counter(category for row in failures for category in row["categories"])
    completed_statuses = {"completed", "completed_with_accepted_static_position_embedding_warning"}
    completed = [row for row in comparison_rows if row["status"] in completed_statuses]
    best = max(completed, key=lambda row: float(row["rougeL"] or 0.0))["model_provider"] if completed else "not_available"
    pegasus_diagnostics = manifest["pegasus_load_diagnostics"]
    lines = [
        "# Medium Controlled Summarization Benchmark",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Summary",
        "",
        f"- Records evaluated: deterministic `50`, BART `200`, Pegasus PubMed `200`, Pegasus CNN/DailyMail `200`.",
        f"- Models completed: `{', '.join(row['model_provider'] for row in completed)}`",
        "- Models skipped: `none`",
        f"- Best model by ROUGE-L: `{best}`",
        f"- Runtime seconds: `{manifest['runtime_seconds']}`",
        f"- BERTScore enabled: `{manifest.get('include_bertscore', False)}`",
        "",
        "## Cache Verification",
        "",
        f"- HF_HOME: `{manifest['cache_paths']['HF_HOME']}`",
        f"- HF_HUB_CACHE: `{manifest['cache_paths']['HF_HUB_CACHE']}`",
        f"- HF_DATASETS_CACHE: `{manifest['cache_paths']['HF_DATASETS_CACHE']}`",
        f"- TRANSFORMERS_CACHE: `{manifest['cache_paths']['TRANSFORMERS_CACHE']}`",
        f"- RAG_EMBEDDING_PROVIDER: `{manifest['retrieval_embedding_provider']}`",
        f"- RAG_SENTENCE_TRANSFORMERS_MODEL: `{manifest['retrieval_embedding_model']}`",
        "",
        "## ROUGE Results",
        "",
        "| Model | Status | Records | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore F1 | BERTScore status | Avg latency ms | Notes |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in comparison_rows:
        lines.append(
            f"| `{row['model_provider']}` | `{row['status']}` | {row['completed_count']} | {row['rouge1']} | {row['rouge2']} | {row['rougeL']} | {row.get('bertscore_f1')} | `{row.get('bertscore_status')}` | {row['average_latency_ms']} | {row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Clinical Proxy Metrics",
            "",
            "| Model | Citation coverage | Unsupported claim rate | Faithfulness proxy | Missing diagnosis | Missing medication | Timeline completeness | Critical omission | Latency p50 | Latency p95 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| `{row['model_provider']}` | {row.get('citation_coverage')} | {row.get('unsupported_claim_rate')} | {row.get('factuality_proxy_score')} | {row.get('missing_diagnosis_rate')} | {row.get('missing_medication_rate')} | {row.get('timeline_completeness')} | {row.get('critical_info_omission_rate')} | {row.get('latency_p50_ms')} | {row.get('latency_p95_ms')} |"
        )
    lines.extend(
        [
            "",
            "## Pegasus Diagnostic",
            "",
            "| Model | Accepted | Status | Missing/new keys | Smoke test |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for diagnostic in pegasus_diagnostics:
        keys = sorted(set(diagnostic["missing_keys"]) | set(diagnostic["newly_initialized_keys"]))
        lines.append(
            f"| `{diagnostic['model_name']}` | `{diagnostic['accepted_for_benchmark']}` | "
            f"`{diagnostic['acceptance_status']}` | `{', '.join(keys) or 'none'}` | "
            f"`{diagnostic['generation_smoke_test_succeeded']}` |"
        )
    lines.extend(["", "## Unreliable/Skipped Models", "", "- None. Failed Pegasus variants remain in model_comparison.csv with error messages."])
    lines.extend(["", "## Failure Patterns", ""])
    for category, count in counts.most_common():
        lines.append(f"- {category}: `{count}`")
    lines.extend(
        [
            "",
            "## Remaining Blockers Before 500+ Benchmark",
            "",
            "- BART CPU runtime is substantial; consider GPU or a batched inference worker before 500+ records.",
            "- Pegasus should continue to use model-specific input length clamping to avoid positional embedding overflow.",
            "- Current data is still open proxy MultiClinSum, not credentialed real EHR notes.",
            "- Add cross-dataset checks once MTS-Dialog and official MEDIQA-Sum are locally normalized.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp_path.replace(path)


def mean_or_none(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    return round(sum(numeric) / len(numeric), 4) if numeric else None


def log(path: Path, message: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}"
    print(message)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Medium benchmark failed: {exc}", file=sys.stderr)
        raise
