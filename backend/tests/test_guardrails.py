from backend.app.schemas import CandidateSummary, EvidenceChunk, GeneratedClaim
from backend.app.services.embeddings import HashingEmbeddingProvider
from backend.app.services.guardrails import GroundingGuardrail


def _evidence() -> list[EvidenceChunk]:
    return [
        EvidenceChunk(
            chunk_id="evidence-1",
            patient_id="patient-a",
            document_id="report-1",
            document_type="diagnostic-report",
            section="Findings",
            text="No pulmonary edema. Heart size is normal.",
            char_start=0,
            char_end=42,
        )
    ]


def test_verbatim_supported_claim_is_approved() -> None:
    candidate = CandidateSummary(
        claims=[
            GeneratedClaim(
                text="No pulmonary edema. Heart size is normal.",
                evidence_ids=["evidence-1"],
            )
        ]
    )

    report = GroundingGuardrail(HashingEmbeddingProvider()).evaluate(candidate, _evidence())

    assert report.approved is True
    assert report.citation_coverage == 100.0


def test_contradictory_claim_is_blocked() -> None:
    candidate = CandidateSummary(
        claims=[GeneratedClaim(text="Pulmonary edema is present.", evidence_ids=["evidence-1"])]
    )

    report = GroundingGuardrail(HashingEmbeddingProvider()).evaluate(candidate, _evidence())

    assert report.approved is False
    assert report.issues[0].code == "POSSIBLE_CONTRADICTION"


def test_uncited_claim_is_blocked() -> None:
    candidate = CandidateSummary(
        claims=[GeneratedClaim(text="The patient requires admission.", evidence_ids=[])]
    )

    report = GroundingGuardrail(HashingEmbeddingProvider()).evaluate(candidate, _evidence())

    assert report.approved is False
    assert report.issues[0].code == "MISSING_CITATION"
