from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Mapping


@dataclass(frozen=True)
class SummarizationOutput:
    note_id: str
    model_provider: str
    source_note: str
    reference_summary: str
    generated_summary: str
    latency_ms: int

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseSummarizer(ABC):
    provider_name: str
    model_name: str
    model_version: str

    def generate(self, record: Mapping[str, Any]) -> SummarizationOutput:
        source_note = _required_text(record, "source_note")
        reference_summary = str(record.get("reference_summary") or "")
        started = perf_counter()
        generated_summary = self._generate_text(source_note)
        latency_ms = int((perf_counter() - started) * 1000)
        return SummarizationOutput(
            note_id=str(record.get("note_id") or ""),
            model_provider=self.provider_name,
            source_note=source_note,
            reference_summary=reference_summary,
            generated_summary=generated_summary.strip(),
            latency_ms=latency_ms,
        )

    @abstractmethod
    def _generate_text(self, source_note: str) -> str:
        raise NotImplementedError


class DeterministicSummarizer(BaseSummarizer):
    """Tiny local fallback baseline for tests and demos."""

    provider_name = "deterministic"
    model_name = "deterministic_sentence_baseline"
    model_version = "phase7b-1.0.0"

    def __init__(self, *, max_sentences: int = 3):
        self.max_sentences = max_sentences

    def _generate_text(self, source_note: str) -> str:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", source_note)
            if sentence.strip()
        ]
        if not sentences:
            return source_note.strip()
        return " ".join(sentences[: self.max_sentences])


def _required_text(record: Mapping[str, Any], key: str) -> str:
    value = str(record.get(key) or "").strip()
    if not value:
        raise ValueError(f"Record is missing non-empty {key}.")
    return value


def parse_huggingface_summary(output: Any) -> str:
    """Normalize common Hugging Face pipeline output shapes."""

    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, Mapping):
            return str(first.get("summary_text") or first.get("generated_text") or "")
        return str(first)
    if isinstance(output, Mapping):
        return str(output.get("summary_text") or output.get("generated_text") or "")
    return str(output or "")
