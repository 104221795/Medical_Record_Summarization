from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.evaluation.artifact_paths import configured_evaluation_artifact_root
from backend.app.evaluation.dataset_diversity import profile_records


PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, "
    "clinical effectiveness, or real-world healthcare performance. Real EHR "
    "evaluation requires credentialed data and approved governance."
)
PROVIDERS = ("deterministic", "bart", "pegasus", "qwen2.5", "llama3.2")
METRICS = (
    "rougeL",
    "citation_coverage",
    "unsupported_claim_rate",
    "factuality_proxy_score",
    "timeline_completeness",
    "hallucinated_clinical_entity_count",
    "critical_info_omission_rate",
    "latency_ms",
)
PORTABLE_FLOW_FILES = {
    "flow_1_raw": "flow_1_raw_per_record_metrics.csv",
    "flow_1_5_context": "flow_1_5_context_per_record_metrics.csv",
    "flow_2_rag": "flow_2_rag_per_record_metrics.csv",
}
LEGACY_FLOW_PATHS = {
    "flow_1_raw": Path(
        "D:/clin_summ_outputs/medium_benchmark_bart_pegasus/per_record_metrics.csv"
    ),
    "flow_1_5_context": Path(
        "D:/clin_summ_outputs/clinical_context_benchmark/per_record_metrics.csv"
    ),
    "flow_2_rag": Path(
        "D:/clin_summ_outputs/rag_grounded_benchmark/per_record_metrics.csv"
    ),
}


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    no_gate_root = Path(args.no_gate_root)
    gated_root = Path(args.gated_root)
    per_record = _read_csv(no_gate_root / "per_record_metrics.csv")
    retrieval = _read_csv(no_gate_root / "retrieval_metrics.csv")
    model_comparison = _read_csv(no_gate_root / "model_comparison.csv")
    gated_retrieval = _read_csv(gated_root / "retrieval_metrics.csv")
    gated_metrics = _read_csv(gated_root / "per_record_metrics.csv")
    prediction_records = _read_jsonl(no_gate_root / "all_predictions.jsonl")

    note_ids = set(per_record["note_id"].astype(str))
    dataset_records = _read_selected_dataset(Path(args.dataset), note_ids)
    record_strata = build_record_strata(dataset_records, retrieval)
    diversity = aggregate_diversity(per_record, record_strata)
    failures = aggregate_failures(per_record)
    correlations = metric_correlations(per_record, model_comparison)
    reference_edit_proxy = build_reference_edit_proxy(prediction_records)
    gate_cases = gate_case_analysis(
        gated_retrieval=gated_retrieval,
        gated_metrics=gated_metrics,
        no_gate_metrics=per_record,
    )
    threshold_sensitivity = retrieval_threshold_sensitivity(retrieval, per_record)
    flow_comparison, flow_deltas = controlled_flow_comparison(
        no_gate_metrics=per_record,
        flow_paths={
            "flow_1_raw": Path(args.flow_1_metrics),
            "flow_1_5_context": Path(args.flow_1_5_metrics),
            "flow_2_rag": Path(args.flow_2_metrics),
        },
    )
    human_manifest = build_human_review_pack(
        output_dir=output_dir,
        prediction_records=prediction_records,
        per_record=per_record,
        blocked_ids=set(gate_cases["note_id"].astype(str)),
        sample_size=args.human_sample_size,
    )

    _write_csv(record_strata, output_dir / "record_strata.csv")
    _write_csv(diversity, output_dir / "diversity_strata_metrics.csv")
    _write_csv(failures, output_dir / "provider_failure_matrix.csv")
    _write_csv(correlations, output_dir / "metric_correlations.csv")
    _write_csv(reference_edit_proxy, output_dir / "reference_edit_proxy.csv")
    _write_csv(gate_cases, output_dir / "retrieval_gate_case_analysis.csv")
    _write_csv(threshold_sensitivity, output_dir / "retrieval_threshold_sensitivity.csv")
    _write_csv(flow_comparison, output_dir / "controlled_flow_comparison.csv")
    _write_csv(flow_deltas, output_dir / "controlled_flow_deltas.csv")

    report = build_report(
        record_strata=record_strata,
        diversity=diversity,
        failures=failures,
        correlations=correlations,
        gate_cases=gate_cases,
        threshold_sensitivity=threshold_sensitivity,
        flow_comparison=flow_comparison,
        flow_deltas=flow_deltas,
        human_manifest=human_manifest,
    )
    report_path = output_dir / "WEEK5_P1_P2_ANALYSIS.md"
    report_path.write_text(report, encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "proxy_warning": PROXY_WARNING,
        "analysis_type": "post_hoc_week5_p1_p2",
        "generation_models_rerun": False,
        "no_gate_root": str(no_gate_root),
        "gated_root": str(gated_root),
        "dataset": str(args.dataset),
        "historical_flow_sources": {
            "flow_1_raw": str(args.flow_1_metrics),
            "flow_1_5_context": str(args.flow_1_5_metrics),
            "flow_2_rag": str(args.flow_2_metrics),
        },
        "record_count": len(note_ids),
        "provider_count": int(per_record["model_provider"].nunique()),
        "outputs": {
            "report": report_path.name,
            "record_strata": "record_strata.csv",
            "diversity": "diversity_strata_metrics.csv",
            "failures": "provider_failure_matrix.csv",
            "correlations": "metric_correlations.csv",
            "reference_edit_proxy": "reference_edit_proxy.csv",
            "gate_cases": "retrieval_gate_case_analysis.csv",
            "threshold_sensitivity": "retrieval_threshold_sensitivity.csv",
            "flow_comparison": "controlled_flow_comparison.csv",
            "flow_deltas": "controlled_flow_deltas.csv",
            "human_review_cases": human_manifest["cases_path"],
            "human_review_scores": human_manifest["scores_path"],
            "human_review_blinding_key": human_manifest["blinding_key_path"],
        },
        "limitations": [
            "All automated findings are post-hoc proxy analysis.",
            "BERTScore correlation uses five provider-level observations and is exploratory only.",
            "Threshold sensitivity reclassifies saved retrieval outputs; it does not rerun retrieval or generation.",
            "Human-evaluation files contain blank scores until real reviewers complete them.",
            "Flow comparisons use common note/provider rows but come from historical runs with configuration differences.",
        ],
    }
    (output_dir / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Week 5 P1/P2 analysis written to {output_dir}")


def parse_args() -> argparse.Namespace:
    artifact_root = configured_evaluation_artifact_root()
    historical_root = artifact_root / "historical_flow_metrics"
    parser = argparse.ArgumentParser(
        description="Run post-hoc Week 5 P1/P2 analysis without rerunning models."
    )
    parser.add_argument(
        "--no-gate-root",
        default=str(artifact_root / "rag_best_models_benchmark_50_no_gate"),
    )
    parser.add_argument(
        "--gated-root",
        default=str(artifact_root / "rag_best_models_benchmark_50_gated"),
    )
    parser.add_argument(
        "--dataset",
        default="data/processed/governance/benchmark_set.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default=str(artifact_root / "week5_analysis"),
    )
    parser.add_argument(
        "--flow-1-metrics",
        default=str(
            _portable_or_legacy(
                historical_root / PORTABLE_FLOW_FILES["flow_1_raw"],
                LEGACY_FLOW_PATHS["flow_1_raw"],
            )
        ),
    )
    parser.add_argument(
        "--flow-1-5-metrics",
        default=str(
            _portable_or_legacy(
                historical_root / PORTABLE_FLOW_FILES["flow_1_5_context"],
                LEGACY_FLOW_PATHS["flow_1_5_context"],
            )
        ),
    )
    parser.add_argument(
        "--flow-2-metrics",
        default=str(
            _portable_or_legacy(
                historical_root / PORTABLE_FLOW_FILES["flow_2_rag"],
                LEGACY_FLOW_PATHS["flow_2_rag"],
            )
        ),
    )
    parser.add_argument("--human-sample-size", type=int, default=12)
    return parser.parse_args()


def build_record_strata(
    records: list[dict[str, Any]],
    retrieval: pd.DataFrame,
) -> pd.DataFrame:
    profiles = profile_records(records)
    rows = []
    retrieval_by_note = retrieval.set_index("note_id", drop=False).to_dict("index")
    for profile in profiles:
        retrieval_row = retrieval_by_note.get(profile.note_id, {})
        rows.append(
            {
                "note_id": profile.note_id,
                "token_count": profile.token_count,
                "length_bucket": profile.length_bucket,
                "diagnosis_density": profile.diagnosis_density,
                "medication_density": profile.medication_density,
                "timeline_complexity": profile.timeline_complexity,
                "retrieval_quality_status": retrieval_row.get("retrieval_quality_status"),
                "retrieval_gate_decision": retrieval_row.get("retrieval_gate_decision"),
                "recall_at_5": _number(retrieval_row.get("recall_at_5")),
                "diagnosis_evidence_present": _bool(retrieval_row.get("diagnosis_evidence_present")),
                "medication_evidence_present": _bool(retrieval_row.get("medication_evidence_present")),
                "timeline_evidence_present": _bool(retrieval_row.get("timeline_evidence_present")),
            }
        )
    frame = pd.DataFrame(rows)
    for column, label in (
        ("diagnosis_density", "diagnosis"),
        ("medication_density", "medication"),
        ("timeline_complexity", "timeline"),
    ):
        frame[f"{label}_bucket"] = _quantile_labels(frame[column], label)
    challenge_score = (
        frame["token_count"].rank(pct=True)
        + frame["diagnosis_density"].rank(pct=True)
        + frame["medication_density"].rank(pct=True)
        + frame["timeline_complexity"].rank(pct=True)
        + frame["retrieval_quality_status"].isin(["warning", "failed"]).astype(float)
    )
    frame["difficulty_score"] = challenge_score.round(4)
    frame["difficulty_bucket"] = pd.qcut(
        challenge_score.rank(method="first"),
        3,
        labels=["easy", "medium", "hard"],
    )
    return frame


def aggregate_diversity(
    per_record: pd.DataFrame,
    record_strata: pd.DataFrame,
) -> pd.DataFrame:
    joined = per_record.drop(
        columns=[
            "retrieval_quality_status",
            "retrieval_gate_decision",
            "recall_at_5",
        ],
        errors="ignore",
    ).merge(record_strata, on="note_id", how="left")
    definitions = {
        "length": "length_bucket",
        "diagnosis_density": "diagnosis_bucket",
        "medication_density": "medication_bucket",
        "timeline_complexity": "timeline_bucket",
        "retrieval_quality": "retrieval_quality_status",
        "difficulty": "difficulty_bucket",
    }
    rows: list[dict[str, Any]] = []
    for dimension, column in definitions.items():
        for (provider, stratum), group in joined.groupby(
            ["model_provider", column],
            dropna=False,
            observed=True,
        ):
            row = {
                "dimension": dimension,
                "stratum": str(stratum),
                "model_provider": provider,
                "record_count": int(group["note_id"].nunique()),
            }
            for metric in METRICS:
                if metric in group:
                    row[f"mean_{metric}"] = _round(group[metric].mean())
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["dimension", "stratum", "model_provider"])


def aggregate_failures(per_record: pd.DataFrame) -> pd.DataFrame:
    categories = sorted(
        {
            category
            for value in per_record["failure_categories"].fillna("")
            for category in _categories(value)
        }
    )
    rows = []
    for provider, group in per_record.groupby("model_provider"):
        record_count = int(group["note_id"].nunique())
        for category in categories:
            count = int(
                group["failure_categories"]
                .fillna("")
                .map(lambda value: category in _categories(value))
                .sum()
            )
            rows.append(
                {
                    "model_provider": provider,
                    "failure_category": category,
                    "record_count": record_count,
                    "failure_count": count,
                    "failure_rate": _round(count / record_count if record_count else 0.0),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["model_provider", "failure_count"],
        ascending=[True, False],
    )


def metric_correlations(
    per_record: pd.DataFrame,
    model_comparison: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    targets = (
        "citation_coverage",
        "unsupported_claim_rate",
        "factuality_proxy_score",
        "timeline_completeness",
        "hallucinated_clinical_entity_count",
        "critical_info_omission_rate",
    )
    for provider, group in per_record.groupby("model_provider"):
        for target in targets:
            sample = group[["rougeL", target]].dropna()
            rows.append(
                {
                    "scope": "per_record",
                    "model_provider": provider,
                    "x_metric": "rougeL",
                    "y_metric": target,
                    "n": len(sample),
                    "pearson": _correlation(sample, "rougeL", target, "pearson"),
                    "spearman": _correlation(sample, "rougeL", target, "spearman"),
                    "interpretation_boundary": "association_only_not_causation",
                }
            )
    aggregate_targets = (
        "rougeL",
        "citation_coverage",
        "unsupported_claim_rate",
        "factuality_proxy_score",
        "critical_info_omission_rate",
    )
    for target in aggregate_targets:
        sample = model_comparison[["bertscore_f1", target]].dropna()
        rows.append(
            {
                "scope": "provider_aggregate_exploratory",
                "model_provider": "all_five_providers",
                "x_metric": "bertscore_f1",
                "y_metric": target,
                "n": len(sample),
                "pearson": _correlation(sample, "bertscore_f1", target, "pearson"),
                "spearman": _correlation(sample, "bertscore_f1", target, "spearman"),
                "interpretation_boundary": "n_equals_five_exploratory_only",
            }
        )
    return pd.DataFrame(rows)


def build_reference_edit_proxy(
    prediction_records: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for record in prediction_records:
        generated = str(record.get("generated_summary") or "")
        reference = str(record.get("reference_summary") or "")
        similarity = (
            SequenceMatcher(None, generated, reference).ratio()
            if generated and reference
            else None
        )
        rows.append(
            {
                "note_id": record.get("note_id"),
                "model_provider": record.get("model_provider"),
                "reference_similarity_ratio": _round(similarity),
                "reference_edit_proxy": _round(1.0 - similarity)
                if similarity is not None
                else None,
                "generated_character_count": len(generated),
                "reference_character_count": len(reference),
                "boundary": "textual_distance_to_reference_only_not_clinician_edit_effort",
            }
        )
    return pd.DataFrame(rows)


def gate_case_analysis(
    *,
    gated_retrieval: pd.DataFrame,
    gated_metrics: pd.DataFrame,
    no_gate_metrics: pd.DataFrame,
) -> pd.DataFrame:
    blocked = gated_retrieval[
        gated_retrieval["retrieval_gate_decision"].eq("review_retrieval_first")
    ].copy()
    rows = []
    for _, retrieval_row in blocked.iterrows():
        note_id = str(retrieval_row["note_id"])
        for provider in PROVIDERS:
            gated_row = gated_metrics[
                (gated_metrics["note_id"].eq(note_id))
                & (gated_metrics["model_provider"].eq(provider))
            ]
            no_gate_row = no_gate_metrics[
                (no_gate_metrics["note_id"].eq(note_id))
                & (no_gate_metrics["model_provider"].eq(provider))
            ]
            g = gated_row.iloc[0] if not gated_row.empty else {}
            n = no_gate_row.iloc[0] if not no_gate_row.empty else {}
            rows.append(
                {
                    "note_id": note_id,
                    "model_provider": provider,
                    "gate_reason": retrieval_row.get("retrieval_gate_reasons"),
                    "recall_at_5": _number(retrieval_row.get("recall_at_5")),
                    "mrr": _number(retrieval_row.get("mrr")),
                    "diagnosis_evidence_present": _bool(
                        retrieval_row.get("diagnosis_evidence_present")
                    ),
                    "timeline_evidence_present": _bool(
                        retrieval_row.get("timeline_evidence_present")
                    ),
                    "gated_status": g.get("status") if hasattr(g, "get") else None,
                    "gated_error": g.get("error_message") if hasattr(g, "get") else None,
                    "no_gate_status": n.get("status") if hasattr(n, "get") else None,
                    "no_gate_rougeL": _number(n.get("rougeL")) if hasattr(n, "get") else None,
                    "no_gate_citation_coverage": _number(
                        n.get("citation_coverage")
                    ) if hasattr(n, "get") else None,
                    "no_gate_unsupported_claim_rate": _number(
                        n.get("unsupported_claim_rate")
                    ) if hasattr(n, "get") else None,
                    "no_gate_factuality_proxy_score": _number(
                        n.get("factuality_proxy_score")
                    ) if hasattr(n, "get") else None,
                    "no_gate_critical_omission": _number(
                        n.get("critical_info_omission_rate")
                    ) if hasattr(n, "get") else None,
                    "interpretation": (
                        "The gate blocked because required diagnosis evidence was "
                        "not extracted, even though aggregate retrieval recall was high."
                    ),
                }
            )
    return pd.DataFrame(rows)


def retrieval_threshold_sensitivity(
    retrieval: pd.DataFrame,
    per_record: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for threshold in (0.50, 0.67, 0.80, 0.90, 1.00):
        required_evidence = (
            retrieval["diagnosis_evidence_present"].map(_bool)
            & retrieval["timeline_evidence_present"].map(_bool)
        )
        eligible = required_evidence & (pd.to_numeric(retrieval["recall_at_5"]) >= threshold)
        eligible_ids = set(retrieval.loc[eligible, "note_id"].astype(str))
        blocked_ids = set(retrieval["note_id"].astype(str)) - eligible_ids
        for provider, group in per_record.groupby("model_provider"):
            retained = group[group["note_id"].astype(str).isin(eligible_ids)]
            rows.append(
                {
                    "recall_at_5_threshold": threshold,
                    "policy": "required_diagnosis_and_timeline_plus_recall_cutoff",
                    "eligible_record_count": len(eligible_ids),
                    "blocked_record_count": len(blocked_ids),
                    "model_provider": provider,
                    "observed_record_count": int(retained["note_id"].nunique()),
                    "mean_rougeL": _round(retained["rougeL"].mean()),
                    "mean_citation_coverage": _round(retained["citation_coverage"].mean()),
                    "mean_factuality_proxy": _round(retained["factuality_proxy_score"].mean()),
                    "mean_critical_omission": _round(
                        retained["critical_info_omission_rate"].mean()
                    ),
                    "boundary": "post_hoc_reclassification_no_retrieval_or_generation_rerun",
                }
            )
    return pd.DataFrame(rows)


def controlled_flow_comparison(
    *,
    no_gate_metrics: pd.DataFrame,
    flow_paths: dict[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for flow, path in flow_paths.items():
        if path.exists():
            frames[flow] = _normalize_flow_provider(_read_csv(path), flow)
    frames["flow_2_1_best_models"] = _normalize_flow_provider(
        no_gate_metrics.copy(),
        "flow_2_1_best_models",
    )

    providers = ("deterministic", "bart", "pegasus_cnn_dailymail")
    metrics = (
        "rougeL",
        "citation_coverage",
        "unsupported_claim_rate",
        "factuality_proxy_score",
        "timeline_completeness",
        "hallucinated_clinical_entity_count",
        "critical_info_omission_rate",
    )
    rows = []
    for provider in providers:
        id_sets = []
        for frame in frames.values():
            provider_rows = frame[frame["normalized_provider"].eq(provider)]
            id_sets.append(set(provider_rows["note_id"].astype(str)))
        common_ids = set.intersection(*id_sets) if id_sets else set()
        for flow, frame in frames.items():
            subset = frame[
                frame["normalized_provider"].eq(provider)
                & frame["note_id"].astype(str).isin(common_ids)
            ]
            row = {
                "flow": flow,
                "normalized_provider": provider,
                "common_record_count": len(common_ids),
            }
            for metric in metrics:
                row[f"mean_{metric}"] = _round(subset[metric].mean())
            rows.append(row)
    comparison = pd.DataFrame(rows)
    deltas = []
    for provider in providers:
        provider_rows = comparison[comparison["normalized_provider"].eq(provider)]
        raw = provider_rows[provider_rows["flow"].eq("flow_1_raw")]
        target = provider_rows[provider_rows["flow"].eq("flow_2_1_best_models")]
        if raw.empty or target.empty:
            continue
        delta = {
            "normalized_provider": provider,
            "common_record_count": int(target.iloc[0]["common_record_count"]),
            "from_flow": "flow_1_raw",
            "to_flow": "flow_2_1_best_models",
        }
        for metric in metrics:
            delta[f"delta_{metric}"] = _round(
                target.iloc[0][f"mean_{metric}"] - raw.iloc[0][f"mean_{metric}"]
            )
        deltas.append(delta)
    return comparison, pd.DataFrame(deltas)


def build_human_review_pack(
    *,
    output_dir: Path,
    prediction_records: list[dict[str, Any]],
    per_record: pd.DataFrame,
    blocked_ids: set[str],
    sample_size: int,
) -> dict[str, Any]:
    record_by_id: dict[str, dict[str, Any]] = {}
    for prediction in prediction_records:
        note_id = str(prediction.get("note_id") or "")
        if not note_id:
            continue
        record = record_by_id.setdefault(
            note_id,
            {
                "note_id": note_id,
                "source_note": prediction.get("source_note"),
                "reference_summary": prediction.get("reference_summary"),
                "model_outputs": [],
            },
        )
        record["model_outputs"].append(
            {
                "model_provider": prediction.get("model_provider"),
                "model_name": prediction.get("model_name"),
                "generated_summary": prediction.get("generated_summary"),
                "generated_summary_cited": prediction.get("generated_summary_cited"),
            }
        )
    selected_ids = _select_human_review_ids(
        per_record=per_record,
        blocked_ids=blocked_ids,
        limit=sample_size,
    )
    case_path = output_dir / "human_review_cases.jsonl"
    score_path = output_dir / "human_review_scores.csv"
    key_path = output_dir / "human_review_blinding_key.csv"
    score_rows = []
    key_rows = []
    with case_path.open("w", encoding="utf-8") as handle:
        for case_index, note_id in enumerate(selected_ids, start=1):
            record = record_by_id.get(note_id)
            if not record:
                continue
            outputs = []
            model_outputs = [
                item
                for item in record.get("model_outputs", [])
                if item.get("model_provider") in PROVIDERS
            ]
            ordered = sorted(
                model_outputs,
                key=lambda item: hashlib.sha256(
                    f"{note_id}|{item.get('model_provider')}".encode()
                ).hexdigest(),
            )
            for output_index, item in enumerate(ordered, start=1):
                output_id = f"CASE-{case_index:02d}-OUT-{output_index}"
                provider = str(item.get("model_provider"))
                outputs.append(
                    {
                        "output_id": output_id,
                        "summary": item.get("generated_summary"),
                        "summary_with_citations": item.get("generated_summary_cited"),
                    }
                )
                key_rows.append(
                    {
                        "case_id": f"CASE-{case_index:02d}",
                        "note_id": note_id,
                        "output_id": output_id,
                        "model_provider": provider,
                        "model_name": item.get("model_name"),
                    }
                )
                score_rows.append(
                    {
                        "reviewer_id": "",
                        "reviewer_role": "",
                        "case_id": f"CASE-{case_index:02d}",
                        "output_id": output_id,
                        "factual_correctness_1_to_5": "",
                        "clinical_completeness_1_to_5": "",
                        "citation_usefulness_1_to_5": "",
                        "readability_1_to_5": "",
                        "conciseness_1_to_5": "",
                        "hallucination_risk_low_medium_high": "",
                        "decision_approve_edit_reject": "",
                        "estimated_edit_minutes": "",
                        "critical_error_present_yes_no": "",
                        "comments": "",
                    }
                )
            case = {
                "case_id": f"CASE-{case_index:02d}",
                "note_id": note_id,
                "selection_tags": _selection_tags(note_id, per_record, blocked_ids),
                "source_note": record.get("source_note"),
                "reference_summary": record.get("reference_summary"),
                "outputs": outputs,
                "proxy_warning": PROXY_WARNING,
            }
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    _write_csv(pd.DataFrame(score_rows), score_path)
    _write_csv(pd.DataFrame(key_rows), key_path)
    manifest = {
        "sample_size": len(selected_ids),
        "selected_note_ids": selected_ids,
        "blocked_cases_included": sorted(blocked_ids.intersection(selected_ids)),
        "cases_path": case_path.name,
        "scores_path": score_path.name,
        "blinding_key_path": key_path.name,
        "scores_completed": False,
        "warning": (
            "Do not populate scores with AI-generated judgments. Use qualified "
            "human reviewers and preserve role/consent/governance metadata."
        ),
    }
    (output_dir / "human_review_sample_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def build_report(
    *,
    record_strata: pd.DataFrame,
    diversity: pd.DataFrame,
    failures: pd.DataFrame,
    correlations: pd.DataFrame,
    gate_cases: pd.DataFrame,
    threshold_sensitivity: pd.DataFrame,
    flow_comparison: pd.DataFrame,
    flow_deltas: pd.DataFrame,
    human_manifest: dict[str, Any],
) -> str:
    lines = [
        "# Week 5 P1/P2 Post-hoc Evaluation Analysis",
        "",
        f"> {PROXY_WARNING}",
        "",
        "No model, embedding model, or heavy benchmark was rerun. This report "
        "analyzes saved artifacts from historical runs.",
        "",
        "## Executive Findings",
        "",
    ]
    qwen = diversity[diversity["model_provider"].eq("qwen2.5")]
    hard = qwen[
        qwen["dimension"].eq("difficulty") & qwen["stratum"].eq("hard")
    ]
    easy = qwen[
        qwen["dimension"].eq("difficulty") & qwen["stratum"].eq("easy")
    ]
    if not hard.empty and not easy.empty:
        lines.append(
            "- Qwen2.5 remains the strongest generative provider overall, but the "
            "heuristic source-difficulty bucket does not produce a monotonic omission "
            f"pattern (`{easy.iloc[0]['mean_critical_info_omission_rate']}` easy versus "
            f"`{hard.iloc[0]['mean_critical_info_omission_rate']}` hard). Source "
            "complexity and output risk should therefore be analyzed as separate dimensions."
        )
    lines.extend(
        [
            "- Retrieval gating is section-aware: the two blocked records had high "
            "aggregate retrieval recall but no extracted DIAGNOSIS evidence.",
            "- ROUGE-L and semantic similarity must not be treated as substitutes "
            "for citation coverage, omission, unsupported-claim, or hallucination proxies.",
            "- The historical flow comparison shows a strong provider-flow interaction: "
            "the latest evidence-first setup improves deterministic grounding, while "
            "BART/Pegasus degrade under the stricter citation-first prompt.",
            "- Human evaluation is prepared as a blinded package; no reviewer scores "
            "are fabricated in this report.",
            "",
            "## 1. Data Diversity",
            "",
            "Strata cover source length, diagnosis density, medication density, "
            "timeline complexity, retrieval quality, and a balanced heuristic "
            "difficulty bucket. `difficulty_score` sums percentile ranks for length "
            "and the three density measures, plus one point for retrieval warning/failure; "
            "the 50 records are then divided into three near-equal groups.",
            "",
            _markdown_table(
                record_strata.groupby("difficulty_bucket", observed=True)
                .agg(record_count=("note_id", "nunique"), mean_tokens=("token_count", "mean"))
                .reset_index()
            ),
            "",
            "Provider-by-stratum metrics are in `diversity_strata_metrics.csv`.",
            "",
            "## 2. Retrieval Gate Case Study",
            "",
            _markdown_table(
                gate_cases[
                    [
                        "note_id",
                        "model_provider",
                        "recall_at_5",
                        "diagnosis_evidence_present",
                        "gated_status",
                        "no_gate_status",
                        "no_gate_citation_coverage",
                        "no_gate_critical_omission",
                    ]
                ]
            ),
            "",
            "Interpretation: a high Recall@5 does not guarantee that the required "
            "clinical section was extracted correctly. The gate enforces an "
            "evidence-policy boundary; it does not prove that every no-gate output "
            "was clinically wrong.",
            "",
            "## 3. Controlled Flow Comparison",
            "",
            _markdown_table(flow_comparison),
            "",
            "Flow deltas are reported separately in `controlled_flow_deltas.csv`. "
            "Only common note/provider rows are used. Because these are historical "
            "runs with prompt/model/configuration differences, interpret them as "
            "comparative evidence, not a randomized ablation.",
            "",
            "## 4. Metric Correlation",
            "",
            _markdown_table(
                correlations[
                    correlations["scope"].eq("provider_aggregate_exploratory")
                ]
            ),
            "",
            "The BERTScore analysis has only five provider observations. Its purpose "
            "is to expose rank disagreement, not establish statistical significance.",
            "",
            "A separate `reference_edit_proxy.csv` contains text distance between each "
            "generated output and the reference. It is useful for sampling, but it is "
            "not clinician edit distance or review time.",
            "",
            "## 5. Provider Failure Taxonomy",
            "",
            _markdown_table(
                failures.sort_values(
                    ["model_provider", "failure_count"],
                    ascending=[True, False],
                ).groupby("model_provider").head(3)
            ),
            "",
            "## 6. Retrieval Policy Sensitivity",
            "",
            _markdown_table(
                threshold_sensitivity[
                    threshold_sensitivity["model_provider"].eq("qwen2.5")
                ]
            ),
            "",
            "This table reclassifies saved retrieval outputs. It estimates the "
            "coverage/quality trade-off of stricter cutoffs but does not rerun retrieval "
            "or generation.",
            "",
            "## 7. Human Evaluation Package",
            "",
            f"- Cases prepared: `{human_manifest['sample_size']}`",
            f"- Blocked cases included: `{', '.join(human_manifest['blocked_cases_included']) or 'none'}`",
            f"- Cases: `{human_manifest['cases_path']}`",
            f"- Blank score sheet: `{human_manifest['scores_path']}`",
            f"- Restricted blinding key: `{human_manifest['blinding_key_path']}`",
            "",
            "Scores remain intentionally blank until real reviewers complete the "
            "protocol. AI-generated reviewer scores must not be represented as human "
            "or clinical evaluation.",
            "",
            "## Recommended Decision",
            "",
            "Freeze model features. Use the current Docker Compose demo and focus the "
            "next mentor discussion on three evidence stories: provider trade-offs by "
            "stratum, section-aware refusal behavior, and why semantic similarity alone "
            "does not establish grounding.",
        ]
    )
    return "\n".join(lines) + "\n"


def _select_human_review_ids(
    *,
    per_record: pd.DataFrame,
    blocked_ids: set[str],
    limit: int,
) -> list[str]:
    qwen = per_record[per_record["model_provider"].eq("qwen2.5")].copy()
    qwen["risk_order"] = (
        pd.to_numeric(qwen["critical_info_omission_rate"], errors="coerce").fillna(0)
        + pd.to_numeric(qwen["unsupported_claim_rate"], errors="coerce").fillna(0)
        + pd.to_numeric(
            qwen["hallucinated_clinical_entity_count"], errors="coerce"
        ).fillna(0)
    )
    selected = list(sorted(blocked_ids))
    selected.extend(qwen.sort_values("risk_order", ascending=False)["note_id"].head(4))
    selected.extend(qwen.sort_values("risk_order", ascending=True)["note_id"].head(3))

    pivot = per_record.pivot_table(
        index="note_id",
        columns="model_provider",
        values="rougeL",
        aggfunc="first",
    )
    if {"qwen2.5", "llama3.2"} <= set(pivot.columns):
        disagreement = (pivot["qwen2.5"] - pivot["llama3.2"]).abs().sort_values(
            ascending=False
        )
        selected.extend(disagreement.head(3).index)
    if {"qwen2.5", "bart", "pegasus"} <= set(pivot.columns):
        challenge = (
            pivot[["bart", "pegasus"]].max(axis=1) - pivot["qwen2.5"]
        ).sort_values(ascending=False)
        selected.extend(challenge.head(3).index)
    deduped = []
    for note_id in selected:
        note_id = str(note_id)
        if note_id and note_id not in deduped:
            deduped.append(note_id)
        if len(deduped) >= limit:
            break
    return deduped


def _selection_tags(
    note_id: str,
    per_record: pd.DataFrame,
    blocked_ids: set[str],
) -> list[str]:
    tags = []
    if note_id in blocked_ids:
        tags.append("retrieval_gate_blocked_case")
    rows = per_record[per_record["note_id"].eq(note_id)]
    qwen = rows[rows["model_provider"].eq("qwen2.5")]
    if not qwen.empty:
        row = qwen.iloc[0]
        if _number(row.get("unsupported_claim_rate")) > 0:
            tags.append("qwen_unsupported_claim_signal")
        if _number(row.get("critical_info_omission_rate")) >= 0.5:
            tags.append("qwen_high_omission_signal")
        if _number(row.get("hallucinated_clinical_entity_count")) > 0:
            tags.append("qwen_hallucinated_entity_signal")
    return tags or ["balanced_comparison_case"]


def _normalize_flow_provider(frame: pd.DataFrame, flow: str) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["flow"] = flow
    normalized["normalized_provider"] = normalized["model_provider"].replace(
        {
            "pegasus": "pegasus_cnn_dailymail",
            "pegasus_cnn_dailymail": "pegasus_cnn_dailymail",
        }
    )
    for metric in METRICS:
        if metric not in normalized:
            normalized[metric] = pd.NA
        normalized[metric] = pd.to_numeric(normalized[metric], errors="coerce")
    return normalized


def _quantile_labels(series: pd.Series, prefix: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    try:
        buckets = pd.qcut(values.rank(method="first"), 3, labels=["low", "medium", "high"])
        return buckets.map(lambda value: f"{prefix}_{value}")
    except ValueError:
        return pd.Series([f"{prefix}_medium"] * len(values), index=values.index)


def _read_selected_dataset(path: Path, note_ids: set[str]) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if str(record.get("note_id")) in note_ids:
                records.append(record)
                if len(records) == len(note_ids):
                    break
    order = {note_id: index for index, note_id in enumerate(sorted(note_ids))}
    return sorted(records, key=lambda record: order.get(str(record.get("note_id")), 10**9))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    for metric in METRICS:
        if metric in frame:
            frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
    return frame


def _portable_or_legacy(portable: Path, legacy: Path) -> Path:
    return portable if portable.exists() else legacy


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _markdown_table(frame: pd.DataFrame, max_rows: int = 24) -> str:
    if frame.empty:
        return "_No rows available._"
    display = frame.head(max_rows).copy()
    columns = list(display.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in display.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if pd.isna(value):
                values.append("")
            elif isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _categories(value: Any) -> set[str]:
    return {
        item.strip()
        for item in str(value or "").replace("|", ";").split(";")
        if item.strip()
    }


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _number(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _round(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _correlation(
    frame: pd.DataFrame,
    x: str,
    y: str,
    method: str,
) -> float | None:
    if len(frame) < 3 or frame[x].nunique() < 2 or frame[y].nunique() < 2:
        return None
    return _round(frame[x].corr(frame[y], method=method))


if __name__ == "__main__":
    main()
