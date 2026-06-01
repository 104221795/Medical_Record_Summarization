from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Settings
from .chunking import HEADING_RE
from .document_difficulty import DocumentDifficultyResult, detect_document_difficulty
from .generators import GeminiJsonClient, GenerationError


NormalizedSectionType = Literal[
    "chief_complaint",
    "history_of_present_illness",
    "past_medical_history",
    "medications",
    "allergies",
    "vitals",
    "labs",
    "imaging",
    "diagnosis",
    "assessment",
    "plan",
    "procedure",
    "narrative",
    "unknown",
]


@dataclass(frozen=True)
class NormalizedSection:
    raw_section_name: str
    normalized_section_type: str
    source_text: str
    confidence: float
    needs_review: bool


@dataclass(frozen=True)
class NormalizationResult:
    document_type: str
    language: str
    normalization_method: str
    sections: list[NormalizedSection]
    difficulty: DocumentDifficultyResult
    warnings: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["difficulty"] = asdict(self.difficulty)
        return data


class LLMNormalizedSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_section_name: str = Field(min_length=1)
    normalized_section_type: NormalizedSectionType
    source_text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool


class LLMNormalizationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: str = Field(min_length=1)
    language: str = Field(min_length=1)
    normalization_method: Literal["llm"]
    sections: list[LLMNormalizedSection] = Field(min_length=1)


def normalize_clinical_document(
    raw_text: str,
    *,
    document_type: str = "clinical_note",
    language: str = "unknown",
    settings: Settings | None = None,
    gemini_client: GeminiJsonClient | None = None,
    allow_llm: bool = False,
) -> NormalizationResult:
    cleaned = _basic_clean(raw_text)
    difficulty = detect_document_difficulty(cleaned)
    rule_sections = _rule_based_sections(cleaned)

    if not difficulty.should_use_llm_normalization or not allow_llm:
        return NormalizationResult(
            document_type=document_type,
            language=language,
            normalization_method="rule_based",
            sections=rule_sections,
            difficulty=difficulty,
        )

    try:
        result = _llm_normalize(
            cleaned,
            document_type=document_type,
            language=language,
            settings=settings,
            gemini_client=gemini_client,
        )
        return NormalizationResult(
            document_type=result.document_type,
            language=result.language,
            normalization_method="llm",
            sections=[
                NormalizedSection(
                    raw_section_name=section.raw_section_name,
                    normalized_section_type=section.normalized_section_type,
                    source_text=section.source_text,
                    confidence=section.confidence,
                    needs_review=section.needs_review,
                )
                for section in result.sections
            ],
            difficulty=difficulty,
        )
    except Exception as exc:
        return NormalizationResult(
            document_type=document_type,
            language=language,
            normalization_method="fallback",
            sections=rule_sections,
            difficulty=difficulty,
            warnings=[f"llm_normalization_failed: {exc}"],
        )


def validate_llm_normalization_payload(payload: str | dict[str, Any], source_text: str) -> LLMNormalizationPayload:
    data = json.loads(payload) if isinstance(payload, str) else payload
    parsed = LLMNormalizationPayload.model_validate(data)
    compact_source = _compact(source_text)
    for section in parsed.sections:
        if _compact(section.source_text) not in compact_source:
            raise ValueError("LLM normalization returned source_text not grounded in the original input.")
    return parsed


def _llm_normalize(
    raw_text: str,
    *,
    document_type: str,
    language: str,
    settings: Settings | None,
    gemini_client: GeminiJsonClient | None,
) -> LLMNormalizationPayload:
    client = gemini_client or _client_from_settings(settings)
    output_schema = {
        "type": "object",
        "required": ["document_type", "language", "normalization_method", "sections"],
        "properties": {
            "document_type": {"type": "string"},
            "language": {"type": "string"},
            "normalization_method": {"type": "string", "enum": ["llm"]},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "raw_section_name",
                        "normalized_section_type",
                        "source_text",
                        "confidence",
                        "needs_review",
                    ],
                    "properties": {
                        "raw_section_name": {"type": "string"},
                        "normalized_section_type": {
                            "type": "string",
                            "enum": list(NormalizedSectionType.__args__),
                        },
                        "source_text": {"type": "string"},
                        "confidence": {"type": "number"},
                        "needs_review": {"type": "boolean"},
                    },
                },
            },
        },
    }
    raw = client.generate_json(
        system_instruction=(
            "You normalize messy clinical documentation into source-backed sections only. "
            "Do not diagnose, recommend treatment, prescribe, infer missing facts, or rewrite "
            "clinical content as new facts. Every section.source_text must be copied from the "
            "provided raw note."
        ),
        user_text=(
            f"Document type: {document_type}\nLanguage hint: {language}\n\n"
            "Normalize this raw note into JSON sections. Raw text remains source of truth.\n\n"
            f"RAW NOTE:\n{raw_text}"
        ),
        output_schema=output_schema,
        temperature=0.0,
    )
    try:
        return validate_llm_normalization_payload(raw, raw_text)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise GenerationError("LLM normalization returned invalid or ungrounded JSON.") from exc


def _client_from_settings(settings: Settings | None) -> GeminiJsonClient:
    if settings is None or not settings.gemini_api_key:
        raise GenerationError("Gemini normalization requires configured settings and RAG_GEMINI_API_KEY.")
    if settings.llm_provider != "gemini" or not settings.llm_external_enabled or not settings.llm_allow_phi_external:
        raise GenerationError("Gemini normalization requires explicit external-provider governance flags.")
    return GeminiJsonClient(settings.gemini_api_key.get_secret_value(), settings.gemini_model)


def _basic_clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()


def _rule_based_sections(text: str) -> list[NormalizedSection]:
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [
            NormalizedSection(
                raw_section_name="Narrative",
                normalized_section_type="narrative",
                source_text=text,
                confidence=0.55,
                needs_review=True,
            )
        ]

    sections: list[NormalizedSection] = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        sections.append(
            NormalizedSection(
                raw_section_name="Narrative",
                normalized_section_type="narrative",
                source_text=text[: matches[0].start()].strip(),
                confidence=0.60,
                needs_review=True,
            )
        )
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        source = text[start:end].strip()
        if not source:
            continue
        raw_name = match.group("header").strip()
        sections.append(
            NormalizedSection(
                raw_section_name=raw_name,
                normalized_section_type=_normalize_heading(raw_name),
                source_text=source,
                confidence=0.86,
                needs_review=False,
            )
        )
    return sections or [
        NormalizedSection("Narrative", "narrative", text, 0.55, True)
    ]


def _normalize_heading(heading: str) -> str:
    value = heading.casefold()
    if "chief" in value or "triệu chứng" in value:
        return "chief_complaint"
    if "history" in value or value == "hpi" or "tiền sử" in value:
        return "history_of_present_illness"
    if "med" in value or "thuốc" in value:
        return "medications"
    if "allerg" in value or "dị ứng" in value:
        return "allergies"
    if "vital" in value:
        return "vitals"
    if "lab" in value or "xét nghiệm" in value:
        return "labs"
    if "finding" in value or "impression" in value or "kết luận" in value:
        return "imaging"
    if "diagnos" in value or "chẩn đoán" in value:
        return "diagnosis"
    if "assessment" in value or "đánh giá" in value:
        return "assessment"
    if "plan" in value or "kế hoạch" in value or "follow" in value:
        return "plan"
    if "procedure" in value:
        return "procedure"
    return "unknown"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
