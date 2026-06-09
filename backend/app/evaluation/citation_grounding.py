from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
TOKEN_RE = re.compile(r"[A-Za-z0-9%./+-]+")


@dataclass(frozen=True)
class CitationGroundingResult:
    note_id: str
    model_provider: str
    claim_count: int
    cited_claim_count: int
    unsupported_claim_count: int
    wrong_patient_citation_count: int
    wrong_encounter_citation_count: int
    conflicting_evidence_count: int
    citation_coverage: float
    unsupported_claim_rate: float
    evidence_patient_scope_valid: bool
    evidence_encounter_scope_valid: bool


def analyze_prediction_row(row: dict[str, Any]) -> CitationGroundingResult:
    generated = str(row.get("generated_summary") or "")
    source = str(row.get("source_note") or row.get("retrieved_evidence") or "")
    claims = split_claims(generated)
    citations = _citations(row)
    patient_id = str(row.get("patient_id") or "")
    encounter_id = str(row.get("encounter_id") or "")
    cited_claim_count = 0
    unsupported = 0
    wrong_patient = 0
    wrong_encounter = 0
    conflict_count = 0
    source_tokens = set(_tokens(source))
    for index, claim in enumerate(claims):
        claim_citations = _claim_citations(citations, index)
        if claim_citations:
            cited_claim_count += 1
        if _unsupported_claim(claim, source_tokens):
            unsupported += 1
        if _conflicting_evidence(claim, source):
            conflict_count += 1
        for citation in claim_citations:
            citation_patient = str(citation.get("patient_id") or patient_id)
            citation_encounter = str(citation.get("encounter_id") or encounter_id)
            if patient_id and citation_patient and citation_patient != patient_id:
                wrong_patient += 1
            if encounter_id and citation_encounter and citation_encounter != encounter_id:
                wrong_encounter += 1
    claim_count = len(claims)
    return CitationGroundingResult(
        note_id=str(row.get("note_id") or ""),
        model_provider=str(row.get("model_provider") or ""),
        claim_count=claim_count,
        cited_claim_count=cited_claim_count,
        unsupported_claim_count=unsupported,
        wrong_patient_citation_count=wrong_patient,
        wrong_encounter_citation_count=wrong_encounter,
        conflicting_evidence_count=conflict_count,
        citation_coverage=round(cited_claim_count / max(1, claim_count), 4),
        unsupported_claim_rate=round(unsupported / max(1, claim_count), 4),
        evidence_patient_scope_valid=wrong_patient == 0,
        evidence_encounter_scope_valid=wrong_encounter == 0,
    )


def split_claims(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_RE.split(text or "") if len(part.strip().split()) >= 3]


def write_grounding_outputs(output_dir: Path, results: list[CitationGroundingResult]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "citation_grounding_records.jsonl"
    csv_path = output_dir / "citation_grounding_metrics.csv"
    report_path = output_dir / "citation_grounding_report.md"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")
    fields = list(CitationGroundingResult.__dataclass_fields__.keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(result.__dict__)
    report_path.write_text(build_grounding_report(results), encoding="utf-8")
    return {"jsonl": str(jsonl_path), "csv": str(csv_path), "report": str(report_path)}


def build_grounding_report(results: list[CitationGroundingResult]) -> str:
    by_provider: dict[str, list[CitationGroundingResult]] = {}
    for result in results:
        by_provider.setdefault(result.model_provider or "unknown", []).append(result)
    lines = [
        "# Citation Grounding Validation",
        "",
        "This validation is a proxy artifact. Summarization-only benchmark rows may not contain real citations, so citation coverage can be zero even when ROUGE is available.",
        "",
        "| Provider | Records | Citation coverage | Unsupported claim rate | Wrong-patient citations | Wrong-encounter citations | Conflicts |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for provider, rows in sorted(by_provider.items()):
        lines.append(
            "| {provider} | {records} | {coverage} | {unsupported} | {wrong_patient} | {wrong_encounter} | {conflicts} |".format(
                provider=provider,
                records=len(rows),
                coverage=_mean(row.citation_coverage for row in rows),
                unsupported=_mean(row.unsupported_claim_rate for row in rows),
                wrong_patient=sum(row.wrong_patient_citation_count for row in rows),
                wrong_encounter=sum(row.wrong_encounter_citation_count for row in rows),
                conflicts=sum(row.conflicting_evidence_count for row in rows),
            )
        )
    counts = Counter(row.model_provider for row in results)
    lines.extend(["", "## Interpretation", ""])
    if not results:
        lines.append("- No prediction rows were available for citation-grounding validation.")
    elif any(row.cited_claim_count == 0 for row in results):
        lines.append("- Some or all rows have no explicit citations; treat citation metrics as a readiness gap, not a model failure alone.")
    lines.append(f"- Providers analyzed: `{dict(counts)}`")
    lines.append("- Next RAG-grounded benchmark should require citations on every clinical claim and same-patient evidence filters.")
    return "\n".join(lines)


def _citations(row: dict[str, Any]) -> list[dict[str, Any]]:
    citations = row.get("citations") or []
    if isinstance(citations, str):
        try:
            parsed = json.loads(citations)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return citations if isinstance(citations, list) else []


def _claim_citations(citations: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    if not citations:
        return []
    matched = []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        claim_index = citation.get("claim_index")
        if claim_index is None or int(claim_index) == index:
            matched.append(citation)
    return matched


def _unsupported_claim(claim: str, source_tokens: set[str]) -> bool:
    claim_tokens = [token for token in _tokens(claim) if len(token) > 3]
    if not claim_tokens:
        return False
    overlap = len(set(claim_tokens) & source_tokens) / max(1, len(set(claim_tokens)))
    return overlap < 0.35


def _conflicting_evidence(claim: str, source: str) -> bool:
    lowered_claim = claim.casefold()
    lowered_source = source.casefold()
    negated_terms = ["no ", "denies ", "without ", "negative for "]
    positive_terms = ["has ", "with ", "positive for ", "present"]
    return any(term in lowered_source for term in negated_terms) and any(term in lowered_claim for term in positive_terms)


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


def _mean(values: Any) -> float:
    items = [float(value) for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0
