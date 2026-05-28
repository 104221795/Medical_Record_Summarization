import pytest

from backend.app.config import Settings
from backend.app.services.medical_guardrail import (
    ContradictionDetector,
    MedicalGuardrail,
    NliContradiction,
)


RAW_TEXT = (
    "THUOC:\nDung metformin 500 mg moi ngay.\n\n"
    "SINH HIEU:\nHA: 145/92 mmHg. HbA1c: 7.2%."
)


class ContradictingNliDetector(ContradictionDetector):
    name = "test-nli"

    def find_contradictions(self, premise: str, hypotheses: list[str]) -> list[NliContradiction]:
        del premise
        return [NliContradiction(claim=hypotheses[0], confidence=0.97)]


def test_passes_supported_medication_dose_and_measurement() -> None:
    report = MedicalGuardrail(
        RAW_TEXT,
        {"claims": [{"text": "Dung metformin 500 mg. HA: 145/92 mmHg."}]},
    ).validate()

    assert report.status == "passed"
    assert report.allow_emr_writeback is True
    assert report.issues == []


def test_blocks_new_medication_and_modified_dose() -> None:
    report = MedicalGuardrail(
        RAW_TEXT,
        {"claims": [{"text": "Dung metformin 1000 mg va amlodipine 5 mg moi ngay."}]},
    ).validate()

    codes = {issue.code for issue in report.issues}
    assert report.status == "failed"
    assert "UNSUPPORTED_MEDICATION_DOSAGE" in codes
    assert "UNSUPPORTED_MEDICATION" in codes


def test_blocks_new_or_modified_clinical_measurement() -> None:
    report = MedicalGuardrail(
        RAW_TEXT,
        {"claims": [{"text": "HA: 180/110 mmHg. SpO2: 89%."}]},
    ).validate()

    assert report.status == "failed"
    assert {issue.code for issue in report.issues} == {"UNSUPPORTED_CLINICAL_MEASUREMENT"}


def test_blocks_nli_contradiction_from_injected_detector() -> None:
    report = MedicalGuardrail(
        "No pulmonary edema.",
        {"claims": [{"text": "Pulmonary edema is present."}]},
        nli_detector=ContradictingNliDetector(),
        require_nli=True,
    ).validate()

    assert report.status == "failed"
    assert report.issues[0].code == "NLI_CONTRADICTION"
    assert report.issues[0].confidence == 0.97


def test_blocks_writeback_when_nli_is_required_but_not_configured() -> None:
    report = MedicalGuardrail(
        "No pulmonary edema.",
        {"claims": [{"text": "No pulmonary edema."}]},
        require_nli=True,
    ).validate()

    assert report.status == "failed"
    assert report.issues[0].code == "NLI_VALIDATION_UNAVAILABLE"


def test_production_configuration_requires_nli_writeback_gate() -> None:
    with pytest.raises(ValueError, match="requires medical NLI"):
        Settings(
            environment="production",
            embedding_provider="fastembed",
            qdrant_url="http://qdrant.internal:6333",
            medical_nli_required_for_writeback=False,
        )
