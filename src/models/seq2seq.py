from __future__ import annotations

import os
from pathlib import Path
from typing import Any


DEFAULT_HF_HOME = Path("D:/hf_cache")
DEFAULT_HF_HUB_CACHE = DEFAULT_HF_HOME / "hub"
DEFAULT_HF_DATASETS_CACHE = DEFAULT_HF_HOME / "datasets"


def configure_hf_d_cache() -> dict[str, str]:
    defaults = {
        "HF_HOME": str(DEFAULT_HF_HOME),
        "HF_HUB_CACHE": str(DEFAULT_HF_HUB_CACHE),
        "HF_DATASETS_CACHE": str(DEFAULT_HF_DATASETS_CACHE),
        "TRANSFORMERS_CACHE": str(DEFAULT_HF_HUB_CACHE),
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    cache_paths = {key: os.environ[key] for key in defaults}
    c_drive = [f"{key}={value}" for key, value in cache_paths.items() if Path(value).drive.casefold() == "c:"]
    if c_drive:
        raise RuntimeError("Refusing to use Hugging Face cache on C drive: " + ", ".join(c_drive))
    DEFAULT_HF_HUB_CACHE.mkdir(parents=True, exist_ok=True)
    DEFAULT_HF_DATASETS_CACHE.mkdir(parents=True, exist_ok=True)
    return cache_paths


def load_seq2seq_model(model_name: str, device: str | int = "cpu", *, local_files_only: bool = True) -> tuple[Any, Any, Any]:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    import torch

    cache_paths = configure_hf_d_cache()
    print(
        f"[seq2seq] Loading {model_name} from {cache_paths['HF_HUB_CACHE']} "
        f"(local_files_only={local_files_only})"
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_paths["HF_HUB_CACHE"],
        local_files_only=local_files_only,
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_name,
        cache_dir=cache_paths["HF_HUB_CACHE"],
        local_files_only=local_files_only,
    )
    torch_device = _torch_device(device)
    model.to(torch_device)
    model.eval()
    return tokenizer, model, torch_device


def generate_seq2seq_summary(
    *,
    tokenizer: Any,
    model: Any,
    torch_device: Any,
    source_note: str,
    max_input_tokens: int = 1024,
    max_new_tokens: int = 160,
    num_beams: int = 4,
    no_repeat_ngram_size: int = 3,
) -> str:
    import torch

    encoded = tokenizer(
        source_note,
        return_tensors="pt",
        truncation=True,
        max_length=model_safe_input_tokens(tokenizer, model, max_input_tokens),
    )
    encoded = {key: value.to(torch_device) for key, value in encoded.items()}
    with torch.inference_mode():
        output_ids = model.generate(
            **encoded,
            max_new_tokens=max_new_tokens,
            num_beams=num_beams,
            no_repeat_ngram_size=no_repeat_ngram_size,
            do_sample=False,
            early_stopping=True,
        )
    return tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()


def model_safe_input_tokens(tokenizer: Any, model: Any, requested_max: int = 1024) -> int:
    candidates = [requested_max]
    tokenizer_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(tokenizer_limit, int) and 0 < tokenizer_limit < 100_000:
        candidates.append(tokenizer_limit)
    config_limit = getattr(model.config, "max_position_embeddings", None)
    if isinstance(config_limit, int) and config_limit > 0:
        candidates.append(config_limit)
    encoder = getattr(getattr(model, "model", None), "encoder", None)
    embed_positions = getattr(encoder, "embed_positions", None)
    num_embeddings = getattr(embed_positions, "num_embeddings", None)
    if isinstance(num_embeddings, int) and num_embeddings > 0:
        candidates.append(num_embeddings)
    weight = getattr(embed_positions, "weight", None)
    shape = getattr(weight, "shape", None)
    if shape and len(shape) >= 1 and int(shape[0]) > 0:
        candidates.append(int(shape[0]))
    return max(32, min(candidates))


def _torch_device(device: str | int) -> Any:
    import torch

    if isinstance(device, int):
        return torch.device("cpu" if device < 0 else f"cuda:{device}")
    normalized = str(device or "cpu")
    if normalized == "-1":
        return torch.device("cpu")
    return torch.device(normalized)
