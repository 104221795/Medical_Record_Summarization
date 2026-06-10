from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from backend.app.schemas import EvidenceChunk


ABSENCE_WARNING = (
    "information was not present in retrieved evidence; do not infer that the patient did not have "
    "this finding, medication, event, assessment, or plan."
)
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
    critical_fact_counts: dict[str, int] = field(default_factory=dict)


def build_clinical_context(
    evidence: list[EvidenceChunk],
    *,
    max_chunks: int = 10,
    max_chars_per_chunk: int = 700,
    max_facts_per_section: int = 2,
    max_chars_per_fact: int = 280,
) -> ClinicalContext:
    selected = deduplicate_evidence(evidence)[:max_chunks]
    sectioned: dict[str, list[EvidenceChunk]] = {name: [] for name in SECTION_QUERIES}
    for chunk in selected:
        label = classify_evidence_section(chunk)
        sectioned[label].append(chunk)
    critical_facts = extract_citation_first_facts(
        selected,
        max_facts_per_section=max_facts_per_section,
        max_chars_per_fact=max_chars_per_fact,
    )
    lines = [
        "Build the summary from the cited clinical facts first. Use only the evidence below. "
        "Preserve diagnoses, medications, timeline, assessment, and plan. "
        "Do not add clinical facts that are not supported by a cited chunk id. "
        "Important: 'not present in retrieved evidence' means unknown, not absent.",
        "",
        "[CITATION_FIRST_CLINICAL_FACTS]",
        "",
    ]
    for section in SECTION_QUERIES:
        lines.append(f"[{section}_FACTS]")
        facts = critical_facts.get(section, [])
        if not facts:
            lines.append(f"- {section.lower()} {ABSENCE_WARNING}")
        for chunk_id, fact in facts:
            lines.append(f"- ({chunk_id}) {fact}")
        lines.append("")
    lines.extend(["[RETRIEVED_EVIDENCE_BY_SECTION]", ""])
    for section, chunks in sectioned.items():
        lines.append(f"[{section}]")
        if not chunks:
            lines.append(f"- {section.lower()} {ABSENCE_WARNING}")
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
        critical_fact_counts={section: len(facts) for section, facts in critical_facts.items()},
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


def extract_citation_first_facts(
    evidence: Iterable[EvidenceChunk],
    *,
    max_facts_per_section: int = 2,
    max_chars_per_fact: int = 280,
) -> dict[str, list[tuple[str, str]]]:
    """Extract compact cited facts before raw evidence.

    Seq2seq summarizers often drop low-frequency clinical details when given
    long chunks. This lightweight pre-pass gives the model a short, cited
    checklist for each clinical section while still preserving the original
    evidence below it.
    """

    chunks = list(evidence)
    facts: dict[str, list[tuple[str, str]]] = {name: [] for name in SECTION_QUERIES}
    for section in SECTION_QUERIES:
        ranked = sorted(chunks, key=lambda chunk: clinical_salience_score(chunk, section), reverse=True)
        seen: set[str] = set()
        for chunk in ranked:
            for sentence in _section_candidate_sentences(chunk, section):
                fact = normalize_whitespace(sentence)[:max_chars_per_fact].strip(" ,;:-")
                key = fact.casefold()
                if len(fact.split()) < 5 or key in seen:
                    continue
                facts[section].append((chunk.chunk_id, fact))
                seen.add(key)
                if len(facts[section]) >= max_facts_per_section:
                    break
            if len(facts[section]) >= max_facts_per_section:
                break
    return facts


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


def _section_candidate_sentences(chunk: EvidenceChunk, section: str) -> list[str]:
    sentences = [
        normalize_whitespace(sentence)
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", chunk.text or "")
        if normalize_whitespace(sentence)
    ]
    pattern = SECTION_PATTERNS.get(section)
    if pattern:
        matching = [sentence for sentence in sentences if pattern.search(sentence)]
        if matching:
            return matching
    return sentences[:2]
