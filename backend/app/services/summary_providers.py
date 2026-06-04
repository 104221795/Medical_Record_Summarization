from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderSectionOutput:
    section_title: str
    section_text: str
    section_type: str = "generated_summary"
    claims: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderOutput:
    provider: str
    model_name: str
    summary_text: str
    sections: list[ProviderSectionOutput] = field(default_factory=list)
    latency_ms: int = 0
    raw_output: dict[str, Any] = field(default_factory=dict)
    model_version: str | None = None
    prompt_template_name: str | None = None
    prompt_template_version: str | None = None


class ProviderExecutionError(RuntimeError):
    pass


class SummaryProvider(ABC):
    provider_name: str
    model_name: str
    model_version: str | None = None
    supports_streaming: bool = False

    @abstractmethod
    def generate_summary(
        self,
        *,
        patient: Any,
        encounter: Any | None,
        context: dict[str, list],
        evidence_pack: dict[str, Any],
        summary_type: str,
        language: str,
        options: Mapping[str, Any],
    ) -> ProviderOutput:
        raise NotImplementedError


class DeterministicProvider(SummaryProvider):
    """Small text baseline adapter; the persisted app still uses its richer local service."""

    provider_name = "deterministic"
    model_name = "deterministic_sentence_baseline"
    model_version = "phase7b-1.0.0"

    def generate_summary(
        self,
        *,
        patient: Any,
        encounter: Any | None,
        context: dict[str, list],
        evidence_pack: dict[str, Any],
        summary_type: str,
        language: str,
        options: Mapping[str, Any],
    ) -> ProviderOutput:
        from src.models import DeterministicSummarizer

        output = DeterministicSummarizer().generate(
            {
                "note_id": _note_id(patient, encounter),
                "source_note": _source_note_from_context(context, evidence_pack),
                "reference_summary": "",
            }
        )
        return ProviderOutput(
            provider=self.provider_name,
            model_name=self.model_name,
            model_version=self.model_version,
            summary_text=output.generated_summary,
            sections=[
                ProviderSectionOutput(
                    section_title="Generated Summary",
                    section_type="generated_summary",
                    section_text=output.generated_summary,
                )
            ],
            latency_ms=output.latency_ms,
            raw_output={"summary_type": summary_type, "language": language, "llm_used": False},
        )


class GeminiProvider(SummaryProvider):
    """Marker for the governed Gemini persisted path implemented in deterministic_summary_service."""

    provider_name = "gemini"
    model_name = "gemini"
    model_version = "configured"

    def generate_summary(
        self,
        *,
        patient: Any,
        encounter: Any | None,
        context: dict[str, list],
        evidence_pack: dict[str, Any],
        summary_type: str,
        language: str,
        options: Mapping[str, Any],
    ) -> ProviderOutput:
        raise ProviderExecutionError(
            "Gemini uses the structured persisted Gemini path so JSON validation and citation IDs "
            "are enforced before persistence."
        )


class HuggingFaceTextProvider(SummaryProvider):
    provider_name: str
    default_model_name: str

    def __init__(
        self,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        summarizer: Any | None = None,
        device: int = -1,
        real_enabled: bool | None = None,
    ):
        self.model_name = model_name or self.default_model_name
        self.model_version = model_version or self.model_name
        self._summarizer = summarizer
        self.device = device
        self.real_enabled = _real_baselines_enabled() if real_enabled is None else real_enabled

    def generate_summary(
        self,
        *,
        patient: Any,
        encounter: Any | None,
        context: dict[str, list],
        evidence_pack: dict[str, Any],
        summary_type: str,
        language: str,
        options: Mapping[str, Any],
    ) -> ProviderOutput:
        if self._summarizer is None and not self.real_enabled:
            raise ProviderExecutionError(
                f"{self.provider_name.upper()} provider is disabled by default. "
                "Set RUN_REAL_BASELINES=1 and configure the model name to run Hugging Face "
                "summarization in the persisted workflow."
            )
        summarizer = self._summarizer or self._build_summarizer()
        output = summarizer.generate(
            {
                "note_id": _note_id(patient, encounter),
                "patient_id": str(patient.patient_id),
                "encounter_id": str(encounter.encounter_id) if encounter else "",
                "source_note": _source_note_from_context(context, evidence_pack),
                "reference_summary": "",
                "dataset": "persisted_clinical_context",
                "split": "inference",
            }
        )
        generated = output.generated_summary.strip()
        if not generated:
            raise ProviderExecutionError(f"{self.provider_name.upper()} provider returned empty output.")
        return ProviderOutput(
            provider=self.provider_name,
            model_name=getattr(summarizer, "model_name", self.model_name),
            model_version=getattr(summarizer, "model_version", self.model_version),
            summary_text=generated,
            sections=[
                ProviderSectionOutput(
                    section_title="Generated Summary",
                    section_type="generated_summary",
                    section_text=generated,
                )
            ],
            latency_ms=output.latency_ms,
            raw_output={
                "summary_type": summary_type,
                "language": language,
                "real_model_enabled": self.real_enabled,
                "source": "huggingface_baseline_provider",
            },
            prompt_template_name=f"{self.provider_name}_text_normalizer",
            prompt_template_version="1.0.0",
        )

    def _build_summarizer(self) -> Any:
        raise NotImplementedError


class BartProvider(HuggingFaceTextProvider):
    provider_name = "bart"
    default_model_name = "facebook/bart-large-cnn"

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("model_name", os.environ.get("BART_MODEL_NAME") or os.environ.get("RAG_BART_MODEL_NAME"))
        super().__init__(**kwargs)

    def _build_summarizer(self) -> Any:
        from src.models import BartSummarizer

        self._summarizer = BartSummarizer(model_name=self.model_name, device=self.device)
        return self._summarizer


class PegasusProvider(HuggingFaceTextProvider):
    provider_name = "pegasus"
    default_model_name = "google/pegasus-pubmed"

    def __init__(self, **kwargs: Any):
        kwargs.setdefault(
            "model_name",
            os.environ.get("PEGASUS_MODEL_NAME") or os.environ.get("RAG_PEGASUS_MODEL_NAME"),
        )
        super().__init__(**kwargs)

    def _build_summarizer(self) -> Any:
        from src.models import PegasusSummarizer

        self._summarizer = PegasusSummarizer(model_name=self.model_name, device=self.device)
        return self._summarizer


class PegasusPubMedProvider(PegasusProvider):
    provider_name = "pegasus_pubmed"
    default_model_name = "google/pegasus-pubmed"

    def __init__(self, **kwargs: Any):
        kwargs.setdefault(
            "model_name",
            os.environ.get("PEGASUS_PUBMED_MODEL_NAME") or "google/pegasus-pubmed",
        )
        super().__init__(**kwargs)


class PegasusCnnDailyMailProvider(PegasusProvider):
    provider_name = "pegasus_cnn_dailymail"
    default_model_name = "google/pegasus-cnn_dailymail"

    def __init__(self, **kwargs: Any):
        kwargs.setdefault(
            "model_name",
            os.environ.get("PEGASUS_CNN_DAILYMAIL_MODEL_NAME") or "google/pegasus-cnn_dailymail",
        )
        super().__init__(**kwargs)


class PegasusXSumProvider(PegasusProvider):
    provider_name = "pegasus_xsum"
    default_model_name = "google/pegasus-xsum"

    def __init__(self, **kwargs: Any):
        kwargs.setdefault(
            "model_name",
            os.environ.get("PEGASUS_XSUM_MODEL_NAME") or "google/pegasus-xsum",
        )
        super().__init__(**kwargs)


def _real_baselines_enabled() -> bool:
    return os.environ.get("RUN_REAL_BASELINES") == "1" or os.environ.get("RAG_RUN_REAL_BASELINES") == "1"


def _note_id(patient: Any, encounter: Any | None) -> str:
    suffix = str(encounter.encounter_id) if encounter else "all-encounters"
    return f"{patient.patient_id}:{suffix}"


def _source_note_from_context(context: dict[str, list], evidence_pack: dict[str, Any]) -> str:
    chunks = [getattr(chunk, "chunk_text", "") for chunk in context.get("chunks", []) if getattr(chunk, "chunk_text", "")]
    if chunks:
        return "\n\n".join(chunks)[:12000]
    documents = [getattr(document, "raw_text", "") for document in context.get("documents", []) if getattr(document, "raw_text", "")]
    if documents:
        return "\n\n".join(documents)[:12000]
    evidence_text = [
        str(item.get("text") or "")
        for item in evidence_pack.get("evidence", [])
        if str(item.get("text") or "").strip()
    ]
    if evidence_text:
        return "\n\n".join(evidence_text)[:12000]
    raise ProviderExecutionError("No text evidence is available for this provider.")
