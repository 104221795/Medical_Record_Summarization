from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from ..evaluation.llmgateway import (
    GATEWAY_MODEL_ALIASES,
    LLMGatewayError,
    clean_gateway_output,
    gateway_model_name,
    generate_llm_summary,
)


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


class GatewayClinicalProvider(SummaryProvider):
    """Testing-only adapter for local/cloud chat models routed through the LLM gateway."""

    model_version = "gateway-structured-clinical-v2"

    def __init__(self, provider_name: str):
        if provider_name not in GATEWAY_MODEL_ALIASES:
            supported = ", ".join(sorted(GATEWAY_MODEL_ALIASES))
            raise ProviderExecutionError(f"Unsupported gateway provider '{provider_name}'. Supported: {supported}.")
        self.provider_name = provider_name
        self.model_name = gateway_model_name(provider_name)

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
        prompt = _gateway_prompt(
            self.provider_name,
            patient=patient,
            encounter=encounter,
            evidence_pack=evidence_pack,
            summary_type=summary_type,
            language=language,
        )
        started = perf_counter()
        try:
            generated = generate_llm_summary(prompt, self.provider_name)
        except LLMGatewayError as exc:
            raise ProviderExecutionError(str(exc)) from exc
        generated = clean_gateway_output(generated)
        generated = _normalize_structured_provider_text(generated)
        if not generated:
            raise ProviderExecutionError(f"{self.provider_name} returned empty output.")
        sections = _structured_sections_from_output(generated)
        return ProviderOutput(
            provider=self.provider_name,
            model_name=self.model_name,
            model_version=self.model_version,
            summary_text=generated,
            sections=sections,
            latency_ms=int((perf_counter() - started) * 1000),
            raw_output={
                "summary_type": summary_type,
                "language": language,
                "source": "llm_gateway_testing_provider",
                "testing_only": True,
                "clinical_context_schema": "v2",
                "options": dict(options),
            },
            prompt_template_name=f"{self.provider_name}_clinical_context_v2",
            prompt_template_version="2.0.0",
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
        source_note = _provider_input_text(self.provider_name, evidence_pack, context)
        output = summarizer.generate(
            {
                "note_id": _note_id(patient, encounter),
                "patient_id": str(patient.patient_id),
                "encounter_id": str(encounter.encounter_id) if encounter else "",
                "source_note": source_note,
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
                "clinical_context_schema": "v2_extract_short",
            },
            prompt_template_name=f"{self.provider_name}_extractive_context_v2",
            prompt_template_version="2.0.0",
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


GATEWAY_PROVIDER_NAMES = frozenset(GATEWAY_MODEL_ALIASES)


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


def _provider_input_text(provider_name: str, evidence_pack: dict[str, Any], context: dict[str, list]) -> str:
    if provider_name in {"bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail", "pegasus_xsum"}:
        return _extractive_context_for_seq2seq(evidence_pack)
    return _source_note_from_context(context, evidence_pack)


def _extractive_context_for_seq2seq(evidence_pack: dict[str, Any]) -> str:
    sections = build_structured_clinical_context_v2(evidence_pack, max_items_per_section=5)
    lines = [
        "Extractive clinical summarization context. Use only these evidence facts.",
        "Preserve diagnosis, medications, timeline, diagnostics, assessment, and plan.",
    ]
    for title in (
        "Patient Snapshot",
        "Diagnosis Evidence",
        "Medication Evidence",
        "Timeline Evidence",
        "Diagnostics Evidence",
        "Assessment Evidence",
        "Plan Evidence",
    ):
        items = sections.get(title, [])
        if not items:
            continue
        lines.append(f"[{title}]")
        lines.extend(f"- {item}" for item in items[:5])
    return "\n".join(lines)[:9000]


def _gateway_prompt(
    provider_name: str,
    *,
    patient: Any,
    encounter: Any | None,
    evidence_pack: dict[str, Any],
    summary_type: str,
    language: str,
) -> str:
    context_sections = build_structured_clinical_context_v2(evidence_pack, max_items_per_section=8)
    rendered_context = _render_context_sections(context_sections)
    if provider_name in {"qwen2.5", "llama3.2"}:
        style_rules = (
            "Use terse, structured clinical bullets. Keep every claim tied to visible evidence. "
            "Do not write recommendations, diagnoses, medication changes, or negative findings unless the evidence explicitly says so."
        )
    elif provider_name == "gemini2.5_flash_lite":
        style_rules = (
            "Use the same strict evidence-grounded style as the local Qwen/Llama RAG providers. "
            "Write the final draft in English only, even when the UI request language is not English. "
            "Do not translate section headings, source identifiers, medications, diagnoses, or evidence IDs. "
            "Prefer short, extractive clinical bullets over fluent paraphrases. If a fact cannot be tied "
            "to an exact source_id, omit it from clinical sections and list it under Unknown / Missing Evidence."
        )
    else:
        style_rules = "Use concise, evidence-grounded clinical language."

    patient_id = evidence_pack.get("patient_id") or getattr(patient, "patient_id", "")
    encounter_id = str(getattr(encounter, "encounter_id", "") or evidence_pack.get("encounter_id") or "all_encounters")
    return "\n\n".join(
        [
            "You are a strict, clinically precise RAG extraction and summarization engine.",
            f"Task: create a {summary_type} draft. Requested UI language={language}; final clinical summary language=English.",
            f"Patient scope: patient_id={patient_id}; encounter_scope={encounter_id}.",
            style_rules,
            "Critical rules:",
            "1. Use only the supplied [STRUCTURED_CLINICAL_CONTEXT_V2].",
            "2. Every clinical fact must include a source_id in square brackets, for example [condition:123].",
            "3. If diagnosis, medication, timeline, diagnostics, assessment, or plan evidence is missing, say Unknown / not retrieved.",
            "4. Keep timeline facts separate from future plan facts.",
            "5. Do not infer absence. Missing retrieved evidence means unknown, not negative.",
            "6. Put each section heading and each bullet on its own line. Do not return one long paragraph.",
            "7. Copy source_id values exactly as they appear, including prefixes such as chunk:, condition:, medication:, or observation:.",
            "8. This is a draft for clinician review, not clinical advice.",
            "9. Do not use Vietnamese wording unless it is an exact quote from the source evidence.",
            "10. Do not output standalone disclaimers as clinical claims; the application already marks all summaries as draft-only.",
            "11. If a context item starts with (chunk:abc), cite it as [chunk:abc], not [abc].",
            "[STRUCTURED_CLINICAL_CONTEXT_V2]",
            rendered_context,
            "Return exactly these sections:",
            "[Patient Snapshot]",
            "- ... [source_id]",
            "[Diagnosis Evidence]",
            "- ... [source_id]",
            "[Medication Evidence]",
            "- ... [source_id]",
            "[Timeline Evidence]",
            "- ... [source_id]",
            "[Diagnostics Evidence]",
            "- ... [source_id]",
            "[Assessment Evidence]",
            "- ... [source_id]",
            "[Plan Evidence]",
            "- ... [source_id]",
            "[Unknown / Missing Evidence]",
            "- Missing or weak evidence that the doctor should verify.",
        ]
    )


def build_structured_clinical_context_v2(
    evidence_pack: dict[str, Any],
    *,
    max_items_per_section: int = 8,
) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {
        "Patient Snapshot": [],
        "Diagnosis Evidence": [],
        "Medication Evidence": [],
        "Timeline Evidence": [],
        "Diagnostics Evidence": [],
        "Assessment Evidence": [],
        "Plan Evidence": [],
        "Unknown / Missing Evidence": [],
    }
    for item in evidence_pack.get("evidence", []):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        text = _compact_text(item.get("text"))
        if not source_id or not text:
            continue
        rendered = f"({source_id}) {text}"
        for section in _section_targets_for_item(item, text):
            if len(sections[section]) < max_items_per_section:
                sections[section].append(rendered)

    for required in ("Diagnosis Evidence", "Medication Evidence", "Timeline Evidence"):
        if not sections[required]:
            sections["Unknown / Missing Evidence"].append(
                f"- {required} information was not present in the retrieved evidence."
            )
    return sections


def _section_targets_for_item(item: dict[str, Any], text: str) -> list[str]:
    source_type = str(item.get("source_type") or "").casefold()
    lowered = text.casefold()
    targets: list[str] = []
    if source_type in {"patient", "encounter"}:
        targets.append("Patient Snapshot")
    if source_type == "condition" or _contains_any(lowered, ("diagnosis", "diagnosed", "condition", "problem", "tumor", "cancer")):
        targets.append("Diagnosis Evidence")
    if source_type == "medication" or _contains_any(lowered, ("medication", "medicine", "dose", "dosage", "mg", "tablet", "insulin", "antibiotic")):
        targets.append("Medication Evidence")
    if source_type in {"encounter", "document_chunk", "clinical_document"} or _contains_any(
        lowered,
        ("timeline", "history", "course", "presented", "reported", "underwent", "admitted", "followed"),
    ):
        targets.append("Timeline Evidence")
    if source_type in {"observation", "diagnostic_report"} or _contains_any(
        lowered,
        ("lab", "imaging", "ct", "mri", "x-ray", "ultrasound", "biopsy", "pathology", "creatinine", "hemoglobin"),
    ):
        targets.append("Diagnostics Evidence")
    if _contains_any(lowered, ("assessment", "impression", "summary impression", "clinical impression")):
        targets.append("Assessment Evidence")
    if _contains_any(lowered, ("plan", "follow-up", "follow up", "scheduled", "recommendation", "pending", "next")):
        targets.append("Plan Evidence")
    if not targets:
        targets.append("Timeline Evidence")
    return _dedupe(targets)


def _render_context_sections(sections: dict[str, list[str]]) -> str:
    blocks: list[str] = []
    for title, items in sections.items():
        blocks.append(f"[{title}]")
        if items:
            blocks.extend(f"- {item.lstrip('- ').strip()}" for item in items)
        else:
            blocks.append(f"- {title} information was not present in the retrieved evidence.")
    return "\n".join(blocks)


def _structured_sections_from_output(text: str) -> list[ProviderSectionOutput]:
    text = _normalize_structured_provider_text(text)
    matches = list(re.finditer(r"^\[(?P<title>[^\]]+)\]\s*$", text, flags=re.MULTILINE))
    if not matches:
        claims = [line.strip("- ").strip() for line in text.splitlines() if line.strip("- ").strip()]
        return [
            ProviderSectionOutput(
                section_title="Generated Summary",
                section_type="generated_summary",
                section_text=text,
                claims=claims[:24],
            )
        ]
    sections: list[ProviderSectionOutput] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group("title").strip()
        section_text = text[start:end].strip()
        claims = [
            line.strip().lstrip("-*").strip()
            for line in section_text.splitlines()
            if line.strip().lstrip("-*").strip()
        ]
        sections.append(
            ProviderSectionOutput(
                section_title=title,
                section_type=_section_type_from_title(title),
                section_text=section_text,
                claims=claims[:12],
            )
        )
    return sections


STRUCTURED_SECTION_TITLES = (
    "Patient Snapshot",
    "Diagnosis Evidence",
    "Medication Evidence",
    "Timeline Evidence",
    "Diagnostics Evidence",
    "Assessment Evidence",
    "Plan Evidence",
    "Unknown / Missing Evidence",
    "Active Problems",
    "Recent Clinical Course",
    "Medications",
    "Labs and Imaging Highlights",
    "Needs Clinician Review",
    "DIAGNOSIS_FACTS",
    "MEDICATIONS_FACTS",
    "TIMELINE_FACTS",
    "ASSESSMENT_FACTS",
    "PLAN_FACTS",
    "DIAGNOSTICS_FACTS",
)
STRUCTURED_SECTION_RE = re.compile(
    r"\[\s*(" + "|".join(re.escape(title) for title in STRUCTURED_SECTION_TITLES) + r")\s*\]",
    re.I,
)


def _normalize_structured_provider_text(text: str) -> str:
    compact = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not compact:
        return ""
    compact = STRUCTURED_SECTION_RE.sub(lambda match: f"\n[{_canonical_section_title(match.group(1))}]\n", compact)
    lines: list[str] = []
    for raw_line in compact.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            continue
        if STRUCTURED_SECTION_RE.fullmatch(line):
            lines.append(line)
            continue
        bullet_parts = [part.strip() for part in re.split(r"\s+-\s+", line) if part.strip()]
        if len(bullet_parts) > 1:
            for part in bullet_parts:
                lines.append(f"- {part.lstrip('- ').strip()}")
        elif line.startswith(("- ", "* ", "• ")):
            lines.append(f"- {line[2:].strip()}")
        else:
            lines.append(line)
    return "\n".join(_dedupe_adjacent_blank(lines)).strip()


def _canonical_section_title(title: str) -> str:
    normalized = title.strip()
    lookup = {item.casefold(): item for item in STRUCTURED_SECTION_TITLES}
    return lookup.get(normalized.casefold(), normalized)


def _dedupe_adjacent_blank(lines: list[str]) -> list[str]:
    result: list[str] = []
    for line in lines:
        if not line and (not result or not result[-1]):
            continue
        result.append(line)
    return result


def _section_type_from_title(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_")
    return normalized or "generated_summary"


def _compact_text(value: Any, *, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
