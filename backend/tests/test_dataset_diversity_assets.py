from __future__ import annotations

import argparse
import json
from pathlib import Path

import scripts.build_dataset_diversity_assets as diversity_assets


def test_build_dataset_diversity_assets_combines_sources_and_strata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    primary_path = tmp_path / "benchmark_set.jsonl"
    _write_jsonl(
        primary_path,
        [
            {
                "note_id": "multi_heavy_001",
                "patient_id": "patient_a",
                "encounter_id": "encounter_a",
                "dataset": "multiclinsum",
                "source_note": (
                    "Diagnosis diabetes hypertension infection disease fracture stroke. "
                    "Medication aspirin metformin insulin vancomycin heparin warfarin dose 5 mg. "
                    "Timeline admission day 1 then follow-up week 2 after discharge month 3. "
                    "ASSESSMENT/PLAN::: patient requires structured review."
                ),
                "reference_summary": "Patient has diagnosis, medications, and follow-up timeline.",
            },
            {
                "note_id": "multi_short_002",
                "patient_id": "patient_b",
                "encounter_id": "encounter_b",
                "dataset": "multiclinsum",
                "source_note": "Brief condition note with outpatient follow-up.",
                "reference_summary": "Brief outpatient follow-up summary.",
            },
        ],
    )

    mts_processed = tmp_path / "mts_processed"
    _write_jsonl(
        mts_processed / "mts_dialog_train.jsonl",
        [
            {
                "id": "mts001",
                "dataset": "mts_dialog",
                "split": "train",
                "dialogue": "Doctor: Any pain? Patient: Chest pain for two days.",
                "section_text": "Patient reports chest pain for two days.",
            }
        ],
    )

    mediqa_dir = tmp_path / "mediqa_sum"
    _write_jsonl(
        mediqa_dir / "mediqa_sum_test.jsonl",
        [
            {
                "id": "mediqa001",
                "text": "Diagnosis of pneumonia. Medication azithromycin 250 mg. Follow-up in one week.",
                "target": "Pneumonia treated with azithromycin with one-week follow-up.",
            }
        ],
    )

    synthetic_path = tmp_path / "synthetic_cases.json"
    synthetic_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "demo_001",
                    "title": "Synthetic renal dosing case",
                    "gender": "female",
                    "encounter": {
                        "external_encounter_id": "enc_demo_001",
                        "reason_for_visit": "Medication review after admission",
                    },
                    "conditions": [{"name": "Acute kidney injury"}],
                    "medications": [
                        {
                            "name": "Vancomycin",
                            "dosage_text": "renally adjusted",
                            "route": "IV",
                            "frequency": "per levels",
                        }
                    ],
                    "observations": [{"name": "Creatinine", "value": "3.2", "unit": "mg/dL"}],
                    "reports": [{"conclusion": "Renal function remains impaired."}],
                    "documents": [{"text": "PLAN: monitor renal function and adjust medication dose."}],
                    "expected_behavior": ["Medication dosing should stay cited."],
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(diversity_assets, "DEFAULT_SYNTHETIC_SOURCES", (synthetic_path,))

    args = argparse.Namespace(
        primary=str(primary_path),
        primary_limit=None,
        output_dir=str(tmp_path / "diversity"),
        report_dir=str(tmp_path / "reports"),
        subset_size=10,
        mts_dialog_input_dir=str(tmp_path / "missing_mts_raw"),
        mts_dialog_output_dir=str(mts_processed),
        mts_dialog_limit=None,
        mediqa_sum_dir=str(mediqa_dir),
        messy_cases=2,
        synthetic_limit=None,
        skip_mts_dialog_import=True,
    )

    manifest = diversity_assets.build_dataset_diversity_assets(args)

    output_dir = Path(manifest["output_dir"])
    assert manifest["combined_record_count"] == 7
    assert (output_dir / "diversity_benchmark_set.jsonl").exists()
    assert (output_dir / "synthetic_structured_ehr.jsonl").exists()
    assert (output_dir / "messy_formatting_cases.jsonl").exists()
    assert (output_dir / "dataset_profiles.csv").exists()
    assert (Path(manifest["report_path"])).exists()
    assert manifest["source_inventory"]["MTS-Dialog"]["record_count"] == 1
    assert manifest["source_inventory"]["MEDIQA-Sum"]["record_count"] == 1
    assert manifest["source_inventory"]["Synthetic structured EHR cases"]["record_count"] == 1
    assert manifest["source_inventory"]["Messy formatting stress cases"]["record_count"] == 2

    subset_dir = output_dir / "stratified_subsets"
    assert (subset_dir / "dataset_multiclinsum.jsonl").exists()
    assert (subset_dir / "dataset_mts_dialog.jsonl").exists()
    assert (subset_dir / "dataset_mediqa_sum.jsonl").exists()
    assert (subset_dir / "dataset_synthetic_structured_ehr.jsonl").exists()
    assert (subset_dir / "dataset_messy_formatting.jsonl").exists()
    assert (subset_dir / "diagnosis_heavy.jsonl").exists()
    assert (subset_dir / "medication_heavy.jsonl").exists()
    assert (subset_dir / "timeline_heavy.jsonl").exists()

    report_text = Path(manifest["report_path"]).read_text(encoding="utf-8")
    assert "Dataset Diversity Expansion" in report_text
    assert "Proxy evaluation only" in report_text
    assert "messy formatting" in report_text.lower()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
