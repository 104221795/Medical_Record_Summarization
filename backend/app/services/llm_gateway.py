from __future__ import annotations

import os
from dataclasses import dataclass

from ..config import Settings
from ..persistence_schemas import ProviderInfo, ProviderListResponse


@dataclass(frozen=True)
class ProviderMetadata:
    provider_name: str
    display_name: str
    model_name: str
    provider_type: str
    requires_api_key: bool
    local_model: bool
    domain_fit: str
    description: str
    default_status: str = "available"


PROVIDER_CATALOG: tuple[ProviderMetadata, ...] = (
    ProviderMetadata(
        provider_name="deterministic",
        display_name="Deterministic baseline",
        model_name="deterministic_sentence_baseline",
        provider_type="local_baseline",
        requires_api_key=False,
        local_model=True,
        domain_fit="Development baseline",
        description="Fast extractive baseline for smoke tests and workflow validation.",
    ),
    ProviderMetadata(
        provider_name="gemini",
        display_name="Gemini governed provider",
        model_name="gemini",
        provider_type="external_llm",
        requires_api_key=True,
        local_model=False,
        domain_fit="Configurable external provider",
        description="Structured JSON provider with citation validation when API governance is configured.",
    ),
    ProviderMetadata(
        provider_name="qwen2.5",
        display_name="Qwen2.5 3B via Ollama",
        model_name="ollama/qwen2.5:3b",
        provider_type="local_gateway_llm",
        requires_api_key=False,
        local_model=True,
        domain_fit="Testing-only local RAG summarizer",
        description="Local chat model routed through the LLM gateway with strict clinical context v2 prompts.",
        default_status="testing_only",
    ),
    ProviderMetadata(
        provider_name="llama3.2",
        display_name="Llama3.2 3B via Ollama",
        model_name="ollama/llama3.2:3b",
        provider_type="local_gateway_llm",
        requires_api_key=False,
        local_model=True,
        domain_fit="Testing-only local RAG summarizer",
        description="Local chat model routed through the LLM gateway with strict clinical context v2 prompts.",
        default_status="testing_only",
    ),
    ProviderMetadata(
        provider_name="gemini2.5_flash_lite",
        display_name="Gemini 2.5 Flash Lite",
        model_name="gemini/gemini-2.5-flash-lite",
        provider_type="gateway_external_llm",
        requires_api_key=True,
        local_model=False,
        domain_fit="Testing-only citation-aware cloud summarizer",
        description="Gateway-routed cloud model for de-identified testing; outputs remain draft-only.",
        default_status="testing_only",
    ),
    ProviderMetadata(
        provider_name="bart",
        display_name="BART CNN/DailyMail",
        model_name="facebook/bart-large-cnn",
        provider_type="local_huggingface_seq2seq",
        requires_api_key=False,
        local_model=True,
        domain_fit="General news summarization baseline",
        description="General abstractive baseline. Uses direct AutoTokenizer/AutoModelForSeq2SeqLM generation.",
    ),
    ProviderMetadata(
        provider_name="pegasus_pubmed",
        display_name="Pegasus PubMed",
        model_name="google/pegasus-pubmed",
        provider_type="local_huggingface_seq2seq",
        requires_api_key=False,
        local_model=True,
        domain_fit="Better medical/scientific fit",
        description="Preferred Pegasus baseline for medical/scientific proxy summarization when cached and runnable.",
    ),
    ProviderMetadata(
        provider_name="pegasus_cnn_dailymail",
        display_name="Pegasus CNN/DailyMail",
        model_name="google/pegasus-cnn_dailymail",
        provider_type="local_huggingface_seq2seq",
        requires_api_key=False,
        local_model=True,
        domain_fit="General news summarization baseline",
        description="General Pegasus baseline for comparison against PubMed and BART.",
    ),
    ProviderMetadata(
        provider_name="pegasus_xsum",
        display_name="Pegasus XSum",
        model_name="google/pegasus-xsum",
        provider_type="local_huggingface_seq2seq",
        requires_api_key=False,
        local_model=True,
        domain_fit="Low/general single-sentence news summarization",
        description="Optional general baseline. Not the default Pegasus model for medical record summarization.",
        default_status="optional",
    ),
)


class SummaryProviderGateway:
    """Read-only provider catalog and readiness checks for the UI."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def list_providers(self) -> ProviderListResponse:
        return ProviderListResponse(
            providers=[self._provider_info(metadata) for metadata in PROVIDER_CATALOG]
        )

    def _provider_info(self, metadata: ProviderMetadata) -> ProviderInfo:
        status = metadata.default_status
        if metadata.provider_name in {"gemini", "gemini2.5_flash_lite"} and not self.settings.gemini_api_key:
            status = "configuration_required"
        if metadata.provider_type == "local_huggingface_seq2seq":
            cache_error = _cache_status_error()
            if cache_error:
                status = cache_error
            elif not _real_baselines_enabled():
                status = "disabled_until_RUN_REAL_BASELINES_1"
        return ProviderInfo(
            provider_name=metadata.provider_name,
            display_name=metadata.display_name,
            model_name=metadata.model_name,
            provider_type=metadata.provider_type,
            status=status,
            requires_api_key=metadata.requires_api_key,
            local_model=metadata.local_model,
            domain_fit=metadata.domain_fit,
            description=metadata.description,
        )


def _real_baselines_enabled() -> bool:
    return os.environ.get("RUN_REAL_BASELINES") == "1" or os.environ.get("RAG_RUN_REAL_BASELINES") == "1"


def _cache_status_error() -> str | None:
    for name in ("HF_HOME", "HF_HUB_CACHE", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE"):
        value = os.environ.get(name)
        if value and value.lower().startswith("c:"):
            return f"cache_misconfigured_{name}_points_to_c_drive"
    return None
