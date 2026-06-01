from __future__ import annotations

import re
from dataclasses import dataclass, field

from .chunking import HEADING_RE


@dataclass(frozen=True)
class DocumentDifficultyResult:
    difficulty_score: float
    reasons: list[str] = field(default_factory=list)
    should_use_llm_normalization: bool = False


UNKNOWN_HEADING_RE = re.compile(r"(?m)^\s*([A-Z][A-Za-z /_-]{2,45})\s*:\s*$")
WORD_RE = re.compile(r"[\wÀ-ỹ]+", flags=re.UNICODE)


def detect_document_difficulty(text: str) -> DocumentDifficultyResult:
    """Conservative detector for messy clinical input normalization.

    The detector does not classify medical facts. It only estimates whether
    rule-based section detection is likely to be weak enough to justify optional
    LLM-assisted normalization.
    """

    cleaned = text.strip()
    if not cleaned:
        return DocumentDifficultyResult(
            difficulty_score=1.0,
            reasons=["empty_document"],
            should_use_llm_normalization=True,
        )

    reasons: list[str] = []
    score = 0.0
    words = WORD_RE.findall(cleaned)
    known_headings = list(HEADING_RE.finditer(cleaned))
    unknown_heading_count = _unknown_heading_count(cleaned)
    line_count = max(1, cleaned.count("\n") + 1)
    dense_line_count = sum(1 for line in cleaned.splitlines() if len(line.strip()) > 220)

    if not known_headings:
        reasons.append("no_recognized_clinical_headings")
        score += 0.32
    elif len(known_headings) == 1 and len(words) > 180:
        reasons.append("low_section_detection_confidence")
        score += 0.18

    narrative_ratio = _narrative_ratio(cleaned, known_headings)
    if narrative_ratio > 0.72 and len(words) > 120:
        reasons.append("too_much_text_classified_as_narrative")
        score += 0.22

    if unknown_heading_count >= 2:
        reasons.append("unknown_or_nonstandard_headings")
        score += min(0.18, unknown_heading_count * 0.04)

    punctuation_density = _punctuation_density(cleaned)
    if punctuation_density < 0.012 and len(words) > 160:
        reasons.append("long_dense_text")
        score += 0.16

    if dense_line_count / line_count > 0.35:
        reasons.append("irregular_formatting_or_dense_lines")
        score += 0.12

    if _mixed_language_or_abbreviation_signal(cleaned):
        reasons.append("mixed_language_or_abbreviation_heavy")
        score += 0.08

    score = min(1.0, round(score, 2))
    return DocumentDifficultyResult(
        difficulty_score=score,
        reasons=reasons,
        should_use_llm_normalization=score >= 0.45,
    )


def _unknown_heading_count(text: str) -> int:
    known_spans = [(match.start(), match.end()) for match in HEADING_RE.finditer(text)]
    count = 0
    for match in UNKNOWN_HEADING_RE.finditer(text):
        span = (match.start(), match.end())
        if not any(span[0] >= known[0] and span[1] <= known[1] for known in known_spans):
            count += 1
    return count


def _narrative_ratio(text: str, known_headings: list[re.Match[str]]) -> float:
    if not known_headings:
        return 1.0
    narrative_chars = known_headings[0].start()
    total = max(1, len(text))
    return narrative_chars / total


def _punctuation_density(text: str) -> float:
    punctuation = sum(1 for char in text if char in ".;:!?")
    return punctuation / max(1, len(text))


def _mixed_language_or_abbreviation_signal(text: str) -> bool:
    vietnamese = bool(re.search(r"[ăâêôơưđáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", text, re.IGNORECASE))
    english = bool(re.search(r"\b(?:history|assessment|medication|allergy|chief|labs?|imaging|plan)\b", text, re.IGNORECASE))
    abbreviation_count = len(re.findall(r"\b[A-Z]{2,6}\b", text))
    return (vietnamese and english) or abbreviation_count >= 8
