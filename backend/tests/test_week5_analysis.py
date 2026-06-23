from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.analyze_week5_evaluation import (
    PROVIDERS,
    build_human_review_pack,
    gate_case_analysis,
    retrieval_threshold_sensitivity,
)


def test_gate_case_analysis_preserves_section_aware_block_reason() -> None:
    note_id = "blocked-note"
    gated_retrieval = pd.DataFrame(
        [
            {
                "note_id": note_id,
                "retrieval_gate_decision": "review_retrieval_first",
                "retrieval_gate_reasons": "missing_diagnosis_evidence",
                "recall_at_5": 1.0,
                "mrr": 1.0,
                "diagnosis_evidence_present": False,
                "timeline_evidence_present": True,
            }
        ]
    )
    gated_metrics = pd.DataFrame(
        [
            {
                "note_id": note_id,
                "model_provider": provider,
                "status": "failed",
                "error_message": "missing_diagnosis_evidence",
            }
            for provider in PROVIDERS
        ]
    )
    no_gate_metrics = pd.DataFrame(
        [
            {
                "note_id": note_id,
                "model_provider": provider,
                "status": "completed",
                "rougeL": 0.2,
                "citation_coverage": 0.8,
                "unsupported_claim_rate": 0.0,
                "factuality_proxy_score": 0.9,
                "critical_info_omission_rate": 0.1,
            }
            for provider in PROVIDERS
        ]
    )

    result = gate_case_analysis(
        gated_retrieval=gated_retrieval,
        gated_metrics=gated_metrics,
        no_gate_metrics=no_gate_metrics,
    )

    assert len(result) == len(PROVIDERS)
    assert set(result["gate_reason"]) == {"missing_diagnosis_evidence"}
    assert result["diagnosis_evidence_present"].eq(False).all()
    assert result["gated_status"].eq("failed").all()
    assert result["no_gate_status"].eq("completed").all()


def test_threshold_sensitivity_reclassifies_saved_records_only() -> None:
    retrieval = pd.DataFrame(
        [
            {
                "note_id": "a",
                "diagnosis_evidence_present": True,
                "timeline_evidence_present": True,
                "recall_at_5": 1.0,
            },
            {
                "note_id": "b",
                "diagnosis_evidence_present": True,
                "timeline_evidence_present": False,
                "recall_at_5": 0.8,
            },
            {
                "note_id": "c",
                "diagnosis_evidence_present": True,
                "timeline_evidence_present": True,
                "recall_at_5": 0.4,
            },
        ]
    )
    per_record = pd.DataFrame(
        [
            {
                "note_id": note_id,
                "model_provider": "qwen2.5",
                "rougeL": 0.2,
                "citation_coverage": 0.8,
                "factuality_proxy_score": 0.9,
                "critical_info_omission_rate": 0.2,
            }
            for note_id in ("a", "b", "c")
        ]
    )

    result = retrieval_threshold_sensitivity(retrieval, per_record)
    row = result[
        (result["model_provider"] == "qwen2.5")
        & (result["recall_at_5_threshold"] == 0.5)
    ].iloc[0]

    assert row["eligible_record_count"] == 1
    assert row["blocked_record_count"] == 2
    assert row["observed_record_count"] == 1
    assert row["boundary"] == "post_hoc_reclassification_no_retrieval_or_generation_rerun"


def test_human_review_pack_is_blinded_and_scores_remain_blank(tmp_path: Path) -> None:
    predictions = []
    metric_rows = []
    for note_id in ("note-1", "note-2"):
        for index, provider in enumerate(PROVIDERS):
            predictions.append(
                {
                    "note_id": note_id,
                    "model_provider": provider,
                    "model_name": f"model-{provider}",
                    "source_note": f"source {note_id}",
                    "reference_summary": f"reference {note_id}",
                    "generated_summary": f"summary {provider}",
                    "generated_summary_cited": f"summary {provider} [1]",
                }
            )
            metric_rows.append(
                {
                    "note_id": note_id,
                    "model_provider": provider,
                    "rougeL": 0.1 + index / 100,
                    "unsupported_claim_rate": 0.0,
                    "critical_info_omission_rate": 0.0,
                    "hallucinated_clinical_entity_count": 0.0,
                }
            )

    manifest = build_human_review_pack(
        output_dir=tmp_path,
        prediction_records=predictions,
        per_record=pd.DataFrame(metric_rows),
        blocked_ids={"note-1"},
        sample_size=2,
    )
    scores = pd.read_csv(tmp_path / "human_review_scores.csv")
    cases = [
        line
        for line in (tmp_path / "human_review_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]

    assert manifest["scores_completed"] is False
    assert manifest["blocked_cases_included"] == ["note-1"]
    assert len(cases) == 2
    assert len(scores) == 2 * len(PROVIDERS)
    assert scores["reviewer_id"].isna().all()
    assert scores["factual_correctness_1_to_5"].isna().all()
