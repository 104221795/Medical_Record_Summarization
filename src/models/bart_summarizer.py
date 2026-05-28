from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import BaseSummarizer, parse_huggingface_summary


class BartSummarizer(BaseSummarizer):
    provider_name = "bart"

    def __init__(
        self,
        *,
        model_name: str = "facebook/bart-large-cnn",
        model_version: str | None = None,
        generator: Callable[..., Any] | None = None,
        device: int = -1,
        min_length: int = 20,
        max_length: int = 180,
    ):
        self.model_name = model_name
        self.model_version = model_version or model_name
        self._generator = generator
        self.device = device
        self.min_length = min_length
        self.max_length = max_length

    def _generate_text(self, source_note: str) -> str:
        generator = self._generator or self._load_generator()
        output = generator(
            source_note,
            min_length=self.min_length,
            max_length=self.max_length,
            do_sample=False,
            truncation=True,
        )
        summary = parse_huggingface_summary(output)
        if not summary.strip():
            raise RuntimeError("BART summarizer returned an empty summary.")
        return summary

    def _load_generator(self):
        from transformers import pipeline

        self._generator = pipeline(
            "summarization",
            model=self.model_name,
            tokenizer=self.model_name,
            device=self.device,
        )
        return self._generator
