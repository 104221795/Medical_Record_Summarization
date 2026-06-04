from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import BaseSummarizer, parse_huggingface_summary
from .seq2seq import generate_seq2seq_summary, load_seq2seq_model


class PegasusSummarizer(BaseSummarizer):
    provider_name = "pegasus"

    def __init__(
        self,
        *,
        model_name: str = "google/pegasus-pubmed",
        model_version: str | None = None,
        generator: Callable[..., Any] | None = None,
        device: str | int = "cpu",
        min_length: int = 20,
        max_length: int = 180,
        max_input_tokens: int = 1024,
        max_new_tokens: int = 160,
        num_beams: int = 4,
        no_repeat_ngram_size: int = 3,
    ):
        self.model_name = model_name
        self.model_version = model_version or model_name
        self._generator = generator
        self.device = device
        self.min_length = min_length
        self.max_length = max_length
        self.max_input_tokens = max_input_tokens
        self.max_new_tokens = max_new_tokens
        self.num_beams = num_beams
        self.no_repeat_ngram_size = no_repeat_ngram_size
        self._model_bundle: tuple[Any, Any, Any] | None = None

    def _generate_text(self, source_note: str) -> str:
        if self._generator is not None:
            output = self._generator(
                source_note,
                min_length=self.min_length,
                max_length=self.max_length,
                do_sample=False,
                truncation=True,
            )
            summary = parse_huggingface_summary(output)
        else:
            tokenizer, model, torch_device = self._load_model_bundle()
            summary = generate_seq2seq_summary(
                tokenizer=tokenizer,
                model=model,
                torch_device=torch_device,
                source_note=source_note,
                max_input_tokens=self.max_input_tokens,
                max_new_tokens=self.max_new_tokens,
                num_beams=self.num_beams,
                no_repeat_ngram_size=self.no_repeat_ngram_size,
            )
        if not summary.strip():
            raise RuntimeError("Pegasus summarizer returned an empty summary.")
        return summary

    def _load_model_bundle(self) -> tuple[Any, Any, Any]:
        if self._model_bundle is None:
            self._model_bundle = load_seq2seq_model(self.model_name, self.device)
        return self._model_bundle
