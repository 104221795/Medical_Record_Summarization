from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from backend.app.schemas import EvidenceChunk


SECTION_QUERIES = {
    "DIAGNOSIS": "diagnosis assessment impression condition disease",
    "MEDICATIONS": "medications treatments drugs dose therapy antibiotics insulin",
    "TIMELINE": "timeline hospital course admission discharge follow-up duration after before",
    "ASSESSMENT": "assessment clinical impression findings diagnosis severity",
    "PLAN": "plan follow-up discharge instructions treatment monitoring referral",
    "DIAGNOSTICS": "labs imaging diagnostic report MRI CT X-ray blood test pathology",
}

SECTION_PATTERNS = {
    "DIAGNOSIS": re.compile(r"\b(diagnos\w*|dx|impression|condition|disease|syndrome)\b", re.I),
    "MEDICATIONS": re.compile(r"\b(medication|drug|dose|mg|mcg|tablet|treatment|therapy|antibiotic|insulin)\b", re.I),
    "TIMELINE": re.compile(r"\b(day|week|month|year|follow[- ]?up|admission|discharg\w*|after|before|course)\b", re.I),
    "ASSESSMENT": re.compile(r"\b(assessment|impression|finding|exam|symptom|clinical)\b", re.I),
    "PLAN": re.compile(r"\b(plan|follow[- ]?up|continue|monitor|refer|discharg\w*|return)\b", re.I),
    "DIAGNOSTICS": re.compile(r"\b(lab|image|mri|ct|x-?ray|ultrasound|patholog\w*|test|report|blood)\b", re.I),
}


@dataclass(frozen=True)
class ClinicalContext:
    text: str
    evidence: list[EvidenceChunk]
    section_counts: dict[str, int]
    token_count: int


def build_clinical_context(
    evidence: list[EvidenceChunk],
    *,
    max_chunks: int = 10,
    max_chars_per_chunk: int = 700,
) -> ClinicalContext:
    selected = deduplicate_evidence(evidence)[:max_chunks]
    sectioned: dict[str, list[EvidenceChunk]] = {name: [] for name in SECTION_QUERIES}
    for chunk in selected:
        label = classify_evidence_section(chunk)
        sectioned[label].append(chunk)
    lines = [
        "Use only the evidence below. Preserve diagnoses, medications, timeline, assessment, and plan. "
        "Do not add clinical facts that are not supported by evidence.",
        "",
    ]
    for section, chunks in sectioned.items():
        lines.append(f"[{section}]")
        if not chunks:
            lines.append("- not available in retrieved evidence")
        for chunk in chunks:
            preview = normalize_whitespace(chunk.text)[:max_chars_per_chunk]
            lines.append(f"- ({chunk.chunk_id}) {preview}")
        lines.append("")
    text = "\n".join(lines).strip()
    return ClinicalContext(
        text=text,
        evidence=selected,
        section_counts={section: len(chunks) for section, chunks in sectioned.items()},
        token_count=len(text.split()),
    )


def build_clinical_context_from_chunks(
    chunks: Iterable[EvidenceChunk],
    *,
    max_chunks: int = 12,
    max_chunks_per_section: int = 2,
    max_chars_per_chunk: int = 700,
) -> ClinicalContext:
    """Build a sectioned clinical context directly from source-note chunks.

    This is the Flow 1.5 path: no embedding model, no vector store, no retrieval.
    It ranks source chunks by lightweight clinical-section salience before using
    the same context format as the RAG benchmark.
    """

    scored_by_section: dict[str, list[EvidenceChunk]] = {name: [] for name in SECTION_QUERIES}
    for chunk in chunks:
        section = classify_evidence_section(chunk)
        scored = chunk.model_copy(
            update={
                "section": section,
                "score": clinical_salience_score(chunk, section),
            }
        )
        scored_by_section[section].append(scored)

    selected: list[EvidenceChunk] = []
    selected_ids: set[str] = set()
    for section in SECTION_QUERIES:
        ranked = sorted(scored_by_section[section], key=lambda item: float(item.score or 0.0), reverse=True)
        for chunk in ranked[:max_chunks_per_section]:
            if chunk.chunk_id in selected_ids:
                continue
            selected.append(chunk)
            selected_ids.add(chunk.chunk_id)

    if len(selected) < max_chunks:
        leftovers = [
            chunk
            for section_chunks in scored_by_section.values()
            for chunk in section_chunks
            if chunk.chunk_id not in selected_ids
        ]
        for chunk in sorted(leftovers, key=lambda item: float(item.score or 0.0), reverse=True):
            selected.append(chunk)
            selected_ids.add(chunk.chunk_id)
            if len(selected) >= max_chunks:
                break

    return build_clinical_context(selected, max_chunks=max_chunks, max_chars_per_chunk=max_chars_per_chunk)


def clinical_salience_score(chunk: EvidenceChunk, section: str | None = None) -> float:
    haystack = f"{chunk.section} {chunk.title or ''} {chunk.text}"
    pattern_hits = {
        name: len(pattern.findall(haystack))
        for name, pattern in SECTION_PATTERNS.items()
    }
    selected_section = section or classify_evidence_section(chunk)
    selected_hits = pattern_hits.get(selected_section, 0)
    total_hits = sum(pattern_hits.values())
    length_bonus = min(len(normalize_whitespace(chunk.text).split()) / 120, 1.0)
    heading_bonus = 0.35 if selected_section.casefold() in str(chunk.section or "").casefold() else 0.0
    return round(selected_hits + (0.15 * total_hits) + length_bonus + heading_bonus, 4)


def deduplicate_evidence(evidence: Iterable[EvidenceChunk]) -> list[EvidenceChunk]:
    seen: set[str] = set()
    result: list[EvidenceChunk] = []
    for chunk in sorted(evidence, key=lambda item: float(item.score or 0.0), reverse=True):
        key = chunk.chunk_id or normalize_whitespace(chunk.text)[:120]
        if key in seen:
            continue
        seen.add(key)
        result.append(chunk)
    return result


def classify_evidence_section(chunk: EvidenceChunk) -> str:
    haystack = f"{chunk.section} {chunk.title or ''} {chunk.text}"
    scores = {section: len(pattern.findall(haystack)) for section, pattern in SECTION_PATTERNS.items()}
    best = max(scores.items(), key=lambda item: (item[1], item[0]))
    return best[0] if best[1] > 0 else "ASSESSMENT"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
