from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..models import ClaimSupportStatus, DocumentChunk


CITATION_REQUIRED_CLAIM_TYPES = {
    "diagnosis",
    "medication",
    "allergy",
    "lab_result",
    "vital_sign",
    "procedure",
    "imaging_finding",
    "timeline_event",
    "follow_up",
    "encounter_context",
}


@dataclass(frozen=True)
class SafetyResult:
    citation_coverage: Decimal
    unsupported_claim_count: int
    conflict_count: int
    total_claim_count: int
    supported_claim_count: int


@dataclass(frozen=True)
class ConflictEvidence:
    topic: str
    message: str
    chunks: list[DocumentChunk]


class SafetyService:
    """Small deterministic safety calculator for Phase 3 summaries."""

    def calculate(self, claim_drafts: list) -> SafetyResult:
        citation_required = [
            claim
            for claim in claim_drafts
            if claim.claim_type in CITATION_REQUIRED_CLAIM_TYPES
        ]
        supported = [
            claim
            for claim in citation_required
            if claim.support_status == ClaimSupportStatus.SUPPORTED and claim.citations
        ]
        coverage = (
            Decimal(len(supported)) / Decimal(len(citation_required))
            if citation_required
            else Decimal("1")
        )
        unsupported = sum(
            1
            for claim in claim_drafts
            if claim.support_status
            in {
                ClaimSupportStatus.UNSUPPORTED,
                ClaimSupportStatus.INSUFFICIENT_EVIDENCE,
            }
        )
        conflicts = sum(
            1 for claim in claim_drafts if claim.support_status == ClaimSupportStatus.CONFLICTING
        )
        return SafetyResult(
            citation_coverage=coverage.quantize(Decimal("0.0001")),
            unsupported_claim_count=unsupported,
            conflict_count=conflicts,
            total_claim_count=len(claim_drafts),
            supported_claim_count=len(supported),
        )

    def detect_obvious_conflicts(self, chunks: list[DocumentChunk]) -> list[ConflictEvidence]:
        lower_chunks = [(chunk, chunk.chunk_text.casefold()) for chunk in chunks]
        no_allergy = [
            chunk
            for chunk, text in lower_chunks
            if "no known drug allergy" in text or "no known allergies" in text
        ]
        penicillin = [
            chunk
            for chunk, text in lower_chunks
            if "penicillin allergy" in text or "allergic to penicillin" in text
        ]
        if no_allergy and penicillin:
            return [
                ConflictEvidence(
                    topic="drug_allergy",
                    message=(
                        "Thông tin dị ứng thuốc có mâu thuẫn giữa các nguồn "
                        "và cần bác sĩ kiểm tra."
                    ),
                    chunks=[no_allergy[0], penicillin[0]],
                )
            ]
        return []
