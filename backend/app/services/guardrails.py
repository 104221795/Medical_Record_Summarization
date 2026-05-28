import math
import re

from ..schemas import CandidateSummary, EvidenceChunk, GuardrailIssue, GuardrailReport
from .embeddings import EmbeddingProvider, TOKEN_RE


NEGATION_TERMS = {
    "no", "not", "without", "denies", "denied", "negative", "absent",
    "khong", "chua", "phu", "kh\u00f4ng", "ch\u01b0a", "ph\u1ee7",
}
LOW_INFORMATION_TERMS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "is", "are", "was",
    "were", "patient", "benh", "nhan", "va", "co", "duoc",
}


class GroundingGuardrail:
    """Fail-closed claim checker for citation, support, and polarity conflicts."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        minimum_token_overlap: float = 0.16,
        minimum_semantic_support: float = 0.42,
    ):
        self.embedding_provider = embedding_provider
        self.minimum_token_overlap = minimum_token_overlap
        self.minimum_semantic_support = minimum_semantic_support

    def evaluate(
        self,
        candidate: CandidateSummary,
        evidence: list[EvidenceChunk],
    ) -> GuardrailReport:
        evidence_by_id = {item.chunk_id: item for item in evidence}
        issues: list[GuardrailIssue] = []
        supported_claims = 0
        for claim in candidate.claims:
            if not claim.evidence_ids:
                issues.append(
                    GuardrailIssue(
                        claim=claim.text,
                        code="MISSING_CITATION",
                        detail="Generated claim does not name any retrieved evidence.",
                    )
                )
                continue
            cited = [evidence_by_id[item] for item in claim.evidence_ids if item in evidence_by_id]
            missing_ids = [item for item in claim.evidence_ids if item not in evidence_by_id]
            if missing_ids:
                issues.append(
                    GuardrailIssue(
                        claim=claim.text,
                        code="INVALID_CITATION",
                        detail=f"Unknown evidence IDs: {', '.join(missing_ids)}.",
                    )
                )
                continue
            if self._has_polarity_conflict(claim.text, cited):
                issues.append(
                    GuardrailIssue(
                        claim=claim.text,
                        code="POSSIBLE_CONTRADICTION",
                        detail="Negation polarity differs from the cited clinical evidence.",
                    )
                )
                continue
            if not self._is_supported(claim.text, cited):
                issues.append(
                    GuardrailIssue(
                        claim=claim.text,
                        code="LOW_SUPPORT",
                        detail="Claim support is below the strict grounding threshold.",
                    )
                )
                continue
            supported_claims += 1

        claim_count = len(candidate.claims)
        coverage = round((supported_claims / claim_count) * 100, 1) if claim_count else 0.0
        approved = bool(candidate.claims) and not issues
        return GuardrailReport(
            approved=approved,
            checks_applied=[
                "citation_id_exists_in_retrieved_context",
                "lexical_or_embedding_support_threshold",
                "negation_polarity_conflict_check",
                "fail_closed_output_gate",
            ],
            citation_coverage=coverage,
            issues=issues,
            disposition=(
                "Approved as an AI draft; clinician review remains mandatory."
                if approved
                else "Blocked: unsupported or contradictory generated content must not be shown as a summary."
            ),
        )

    def _is_supported(self, claim: str, cited: list[EvidenceChunk]) -> bool:
        claim_normalized = self._normalize(claim)
        for source in cited:
            source_normalized = self._normalize(source.text)
            if claim_normalized in source_normalized:
                return True
            overlap = self._token_overlap(claim, source.text)
            semantic = self._cosine(
                self.embedding_provider.embed_query(claim),
                self.embedding_provider.embed_query(source.text),
            )
            if overlap >= self.minimum_token_overlap or semantic >= self.minimum_semantic_support:
                return True
        return False

    def _has_polarity_conflict(self, claim: str, cited: list[EvidenceChunk]) -> bool:
        claim_tokens = self._informative_tokens(claim)
        claim_negative = self._is_negative(claim)
        for source in cited:
            overlap = claim_tokens & self._informative_tokens(source.text)
            if overlap and claim_negative != self._is_negative(source.text):
                return True
        return False

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.casefold()).strip()

    def _token_overlap(self, first: str, second: str) -> float:
        first_tokens = self._informative_tokens(first)
        if not first_tokens:
            return 0.0
        return len(first_tokens & self._informative_tokens(second)) / len(first_tokens)

    @staticmethod
    def _informative_tokens(text: str) -> set[str]:
        return {
            item
            for item in TOKEN_RE.findall(text.casefold())
            if item not in LOW_INFORMATION_TERMS and item not in NEGATION_TERMS and len(item) > 1
        }

    @staticmethod
    def _is_negative(text: str) -> bool:
        return bool(set(TOKEN_RE.findall(text.casefold())) & NEGATION_TERMS)

    @staticmethod
    def _cosine(first: list[float], second: list[float]) -> float:
        dot = sum(left * right for left, right in zip(first, second, strict=True))
        first_norm = math.sqrt(sum(value * value for value in first))
        second_norm = math.sqrt(sum(value * value for value in second))
        if not first_norm or not second_norm:
            return 0.0
        return dot / (first_norm * second_norm)
