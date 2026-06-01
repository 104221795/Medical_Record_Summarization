from __future__ import annotations

import json
from pathlib import Path

from backend.app.evaluation.datasets.mtsamples_importer import import_mtsamples_clean


def test_mtsamples_importer_uses_fake_loader_without_huggingface(tmp_path: Path) -> None:
    def loader(split: str):
        assert split == "train"
        return [
            {
                "id": "sample_001",
                "sample_name": "discharge_summary",
                "medical_specialty": "Cardiology",
                "transcription": "HISTORY: Patient reports chest pain.\nPLAN: Follow up arranged.",
            }
        ]

    output_path = tmp_path / "mtsamples.jsonl"
    rows = import_mtsamples_clean(loader=loader, output_path=output_path, limit=10)

    assert output_path.exists()
    assert len(rows) == 1
    assert rows[0]["record_id"] == "sample_001"
    assert rows[0]["source_dataset"] == "BIOMEDNLP/mtsamples_clean"
    assert rows[0]["normalization"]["normalization_method"] == "rule_based"
    assert rows[0]["normalization_method"] == "rule_based"
    assert rows[0]["llm_attempted"] is False
    assert isinstance(rows[0]["needs_review_count"], int)
    persisted = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert persisted["specialty"] == "Cardiology"


def test_mtsamples_importer_can_use_fake_llm_for_difficult_cases(tmp_path: Path) -> None:
    raw_text = _difficult_transcription()
    fake_client = FakeGeminiClient(source_text=raw_text)

    def loader(split: str):
        return [
            {
                "id": "sample_002",
                "sample_name": "consult_note",
                "medical_specialty": "General Medicine",
                "transcription": raw_text,
            }
        ]

    rows = import_mtsamples_clean(
        loader=loader,
        output_path=tmp_path / "mtsamples.jsonl",
        limit=10,
        allow_llm_normalization=True,
        max_llm_cases=1,
        gemini_client=fake_client,
    )

    assert fake_client.calls == 1
    assert rows[0]["normalization_method"] == "llm"
    assert rows[0]["llm_attempted"] is True
    assert rows[0]["difficulty_score"] >= 0.45
    assert rows[0]["difficulty_reasons"]
    assert rows[0]["needs_review_count"] == 1
    assert rows[0]["llm_failed"] is None


def test_mtsamples_importer_falls_back_when_llm_unavailable(tmp_path: Path) -> None:
    raw_text = _difficult_transcription()

    def loader(split: str):
        return [
            {
                "id": "sample_003",
                "sample_name": "consult_note",
                "medical_specialty": "General Medicine",
                "transcription": raw_text,
            }
        ]

    rows = import_mtsamples_clean(
        loader=loader,
        output_path=tmp_path / "mtsamples.jsonl",
        limit=10,
        allow_llm_normalization=True,
        max_llm_cases=1,
    )

    assert rows[0]["normalization_method"] == "fallback"
    assert rows[0]["llm_attempted"] is True
    assert rows[0]["llm_failed"].startswith("llm_normalization_failed")
    assert rows[0]["normalization_warnings"]


class FakeGeminiClient:
    def __init__(self, *, source_text: str):
        self.source_text = source_text
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        return {
            "document_type": "medical_transcription",
            "language": "en",
            "normalization_method": "llm",
            "sections": [
                {
                    "raw_section_name": "Narrative",
                    "normalized_section_type": "narrative",
                    "source_text": self.source_text,
                    "confidence": 0.9,
                    "needs_review": True,
                }
            ],
        }


def _difficult_transcription() -> str:
    sentence = "Patient reports vague symptoms without clear section labels and needs source-backed review."
    return " ".join([sentence] * 30)
