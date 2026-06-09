from __future__ import annotations

import re
from collections import Counter
from statistics import median
from typing import Any


DIAGNOSIS_TERMS = {
    "diagnosis",
    "diagnoses",
    "dx",
    "condition",
    "disease",
    "syndrome",
    "infection",
    "cancer",
    "diabetes",
    "hypertension",
    "asthma",
    "copd",
    "pneumonia",
    "stroke",
    "sepsis",
    "fracture",
    "failure",
    "injury",
}
MEDICATION_TERMS = {
    "medication",
    "medications",
    "medicine",
    "drug",
    "dose",
    "dosage",
    "tablet",
    "capsule",
    "insulin",
    "aspirin",
    "metformin",
    "atorvastatin",
    "antibiotic",
    "mg",
    "mcg",
    "ml",
}
TIMELINE_TERMS = {
    "today",
    "yesterday",
    "tomorrow",
    "day",
    "week",
    "month",
    "year",
    "follow-up",
    "followup",
    "discharge",
    "admission",
    "after",
    "before",
    "prior",
    "since",
}
CLINICAL_ENTITY_HINTS = DIAGNOSIS_TERMS | MEDICATION_TERMS | TIMELINE_TERMS
CITATION_PATTERN = re.compile(r"\[(?:source|citation|doc|chunk|evidence)?\s*[\w:.-]+\]|\(\s*(?:source|citation|doc|chunk)\s*[\w:.-]+\s*\)", re.I)
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9%./+-]{2,}")


CLINICAL_METRIC_FIELDS = [
    "citation_coverage",
    "unsupported_claim_rate",
    "factuality_proxy_score",
    "missing_diagnosis_rate",
    "missing_medication_rate",
    "timeline_completeness",
    "hallucinated_clinical_entity_count",
    "critical_info_omission_rate",
    "latency_p50_ms",
    "latency_p95_ms",
]


PER_RECORD_CLINICAL_FIELDS = [
    "citation_coverage",
    "citation_count",
    "unsupported_claim_rate",
    "factuality_proxy_score",
    "missing_diagnosis_rate",
    "missing_medication_rate",
    "timeline_completeness",
    "hallucinated_clinical_entity_count",
    "critical_info_omission_rate",
    "failure_categories",
]


def compute_clinical_record_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Compute lightweight clinical proxy metrics without external model dependencies."""
    if row.get("status") != "completed":
        return empty_clinical_record_metrics(["retrieval-related failure"])

    source = _text(row.get("source_note"))
    reference = _text(row.get("reference_summary"))
    generated = _text(row.get("generated_summary"))
    evidence = _text(row.get("retrieved_evidence") or row.get("evidence") or source)

    reference_diagnoses = _clinical_terms(reference, DIAGNOSIS_TERMS)
    generated_diagnoses = _clinical_terms(generated, DIAGNOSIS_TERMS)
    reference_medications = _clinical_terms(reference, MEDICATION_TERMS)
    generated_medications = _clinical_terms(generated, MEDICATION_TERMS)
    reference_timeline = _clinical_terms(reference, TIMELINE_TERMS)
    generated_timeline = _clinical_terms(generated, TIMELINE_TERMS)

    missing_diagnosis_rate = _missing_rate(reference_diagnoses, generated_diagnoses)
    missing_medication_rate = _missing_rate(reference_medications, generated_medications)
    timeline_completeness = _coverage_rate(reference_timeline, generated_timeline)
    hallucinated_entities = _hallucinated_clinical_entities(generated, source, reference)
    unsupported_claim_rate = _unsupported_claim_rate(generated, evidence, reference)
    citation_count = _citation_count(row, generated)
    citation_coverage = _citation_coverage(row, generated, citation_count)
    critical_info_omission_rate = _critical_omission_rate(
        diagnosis_rate=missing_diagnosis_rate,
        medication_rate=missing_medication_rate,
        timeline_completeness=timeline_completeness,
        has_diagnosis=bool(reference_diagnoses),
        has_medication=bool(reference_medications),
        has_timeline=bool(reference_timeline),
    )
    factuality_proxy_score = _factuality_proxy_score(
        unsupported_claim_rate=unsupported_claim_rate,
        critical_info_omission_rate=critical_info_omission_rate,
        hallucinated_count=hallucinated_entities,
        generated_token_count=len(_tokens(generated)),
    )
    failure_categories = classify_failure_labels(
        row=row,
        citation_coverage=citation_coverage,
        unsupported_claim_rate=unsupported_claim_rate,
        missing_diagnosis_rate=missing_diagnosis_rate,
        missing_medication_rate=missing_medication_rate,
        timeline_completeness=timeline_completeness,
        hallucinated_clinical_entity_count=hallucinated_entities,
        critical_info_omission_rate=critical_info_omission_rate,
    )

    return {
        "citation_coverage": citation_coverage,
        "citation_count": citation_count,
        "unsupported_claim_rate": unsupported_claim_rate,
        "factuality_proxy_score": factuality_proxy_score,
        "missing_diagnosis_rate": missing_diagnosis_rate,
        "missing_medication_rate": missing_medication_rate,
        "timeline_completeness": timeline_completeness,
        "hallucinated_clinical_entity_count": hallucinated_entities,
        "critical_info_omission_rate": critical_info_omission_rate,
        "failure_categories": failure_categories,
    }


def empty_clinical_record_metrics(failure_categories: list[str] | None = None) -> dict[str, Any]:
    return {
        "citation_coverage": None,
        "citation_count": 0,
        "unsupported_claim_rate": None,
        "factuality_proxy_score": None,
        "missing_diagnosis_rate": None,
        "missing_medication_rate": None,
        "timeline_completeness": None,
        "hallucinated_clinical_entity_count": None,
        "critical_info_omission_rate": None,
        "failure_categories": failure_categories or [],
    }


def aggregate_clinical_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row.get("status") == "completed"]
    latencies = [_float(row.get("latency_ms")) for row in completed]
    latency_values = [value for value in latencies if value is not None]
    failure_counts = Counter()
    for row in rows:
        for category in _split_categories(row.get("failure_categories")):
            failure_counts[category] += 1

    return {
        "citation_coverage": _mean(row.get("citation_coverage") for row in completed),
        "unsupported_claim_rate": _mean(row.get("unsupported_claim_rate") for row in completed),
        "factuality_proxy_score": _mean(row.get("factuality_proxy_score") for row in completed),
        "missing_diagnosis_rate": _mean(row.get("missing_diagnosis_rate") for row in completed),
        "missing_medication_rate": _mean(row.get("missing_medication_rate") for row in completed),
        "timeline_completeness": _mean(row.get("timeline_completeness") for row in completed),
        "hallucinated_clinical_entity_count": _mean(row.get("hallucinated_clinical_entity_count") for row in completed),
        "critical_info_omission_rate": _mean(row.get("critical_info_omission_rate") for row in completed),
        "latency_p50_ms": _percentile(latency_values, 50),
        "latency_p95_ms": _percentile(latency_values, 95),
        "failure_counts": dict(failure_counts),
    }


def classify_failure_labels(
    *,
    row: dict[str, Any],
    citation_coverage: float | None,
    unsupported_claim_rate: float | None,
    missing_diagnosis_rate: float | None,
    missing_medication_rate: float | None,
    timeline_completeness: float | None,
    hallucinated_clinical_entity_count: int | None,
    critical_info_omission_rate: float | None,
) -> list[str]:
    if row.get("status") != "completed":
        return ["retrieval-related failure"]

    labels: list[str] = []
    if (unsupported_claim_rate or 0.0) >= 0.35 or (hallucinated_clinical_entity_count or 0) > 0:
        labels.append("hallucinated content")
    if (missing_diagnosis_rate or 0.0) >= 0.5:
        labels.append("missing diagnosis")
    if (missing_medication_rate or 0.0) >= 0.5:
        labels.append("missing medication")
    if timeline_completeness is not None and timeline_completeness < 0.5:
        labels.append("missing timeline")
    generated_length = len(_tokens(row.get("generated_summary")))
    reference_length = len(_tokens(row.get("reference_summary")))
    if generated_length < max(8, reference_length // 3):
        labels.append("incomplete summary")
    if float(row.get("rougeL") or 0.0) < 0.2 and (critical_info_omission_rate or 0.0) >= 0.5:
        labels.append("retrieval-related failure")
    if citation_coverage == 0 and generated_length > 0:
        labels.append("source data limitation")
    return labels or ["no major proxy failure detected"]


def serialize_failure_categories(value: Any) -> str:
    return "; ".join(_split_categories(value))


def _citation_count(row: dict[str, Any], generated: str) -> int:
    citations = row.get("citations")
    if isinstance(citations, list):
        return len(citations)
    if isinstance(citations, str) and citations.strip():
        try:
            import json

            parsed = json.loads(citations)
            if isinstance(parsed, list):
                return len(parsed)
        except Exception:
            return max(1, citations.count(";") + 1)
    return len(CITATION_PATTERN.findall(generated))


def _citation_coverage(row: dict[str, Any], generated: str, citation_count: int) -> float | None:
    explicit = _float(row.get("citation_coverage"))
    if explicit is not None:
        return round(max(0.0, min(1.0, explicit)), 4)
    claims = _claim_like_sentence_count(generated)
    if claims == 0:
        return None
    return round(min(1.0, citation_count / claims), 4)


def _unsupported_claim_rate(generated: str, evidence: str, reference: str) -> float | None:
    generated_tokens = _tokens(generated)
    if not generated_tokens:
        return None
    support = set(_tokens(f"{evidence} {reference}"))
    unsupported = [token for token in generated_tokens if token not in support and token in CLINICAL_ENTITY_HINTS]
    clinical = [token for token in generated_tokens if token in CLINICAL_ENTITY_HINTS]
    denominator = max(1, len(clinical))
    return round(len(unsupported) / denominator, 4)


def _hallucinated_clinical_entities(generated: str, source: str, reference: str) -> int:
    generated_entities = _clinical_terms(generated, CLINICAL_ENTITY_HINTS)
    support_entities = _clinical_terms(f"{source} {reference}", CLINICAL_ENTITY_HINTS)
    return len(generated_entities.difference(support_entities))


def _critical_omission_rate(
    *,
    diagnosis_rate: float | None,
    medication_rate: float | None,
    timeline_completeness: float | None,
    has_diagnosis: bool,
    has_medication: bool,
    has_timeline: bool,
) -> float | None:
    values: list[float] = []
    if has_diagnosis and diagnosis_rate is not None:
        values.append(diagnosis_rate)
    if has_medication and medication_rate is not None:
        values.append(medication_rate)
    if has_timeline and timeline_completeness is not None:
        values.append(1.0 - timeline_completeness)
    return round(sum(values) / len(values), 4) if values else None


def _factuality_proxy_score(
    *,
    unsupported_claim_rate: float | None,
    critical_info_omission_rate: float | None,
    hallucinated_count: int,
    generated_token_count: int,
) -> float | None:
    if generated_token_count == 0:
        return None
    hallucination_penalty = min(1.0, hallucinated_count / max(1, generated_token_count))
    unsupported_penalty = unsupported_claim_rate or 0.0
    omission_penalty = critical_info_omission_rate or 0.0
    score = 1.0 - ((unsupported_penalty * 0.45) + (omission_penalty * 0.35) + (hallucination_penalty * 0.20))
    return round(max(0.0, min(1.0, score)), 4)


def _clinical_terms(text: str, vocabulary: set[str]) -> set[str]:
    tokens = set(_tokens(text))
    exact = tokens.intersection(vocabulary)
    phrase_matches = {term for term in vocabulary if " " in term and term in text.casefold()}
    return exact | phrase_matches


def _missing_rate(reference_terms: set[str], generated_terms: set[str]) -> float | None:
    if not reference_terms:
        return None
    return round(len(reference_terms.difference(generated_terms)) / len(reference_terms), 4)


def _coverage_rate(reference_terms: set[str], generated_terms: set[str]) -> float | None:
    if not reference_terms:
        return None
    return round(len(reference_terms.intersection(generated_terms)) / len(reference_terms), 4)


def _claim_like_sentence_count(text: str) -> int:
    sentences = [item.strip() for item in re.split(r"[.!?\n]+", text) if item.strip()]
    return len(sentences)


def _tokens(text: Any) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(_text(text))]


def _text(value: Any) -> str:
    return str(value or "")


def _mean(values: Any) -> float | None:
    numbers = [_float(value) for value in values]
    clean = [value for value in numbers if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 4)


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if percentile == 50:
        return round(float(median(ordered)), 4)
    rank = (len(ordered) - 1) * (percentile / 100)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round((ordered[lower] * (1 - weight)) + (ordered[upper] * weight), 4)


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_categories(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(";") if item.strip()]
