from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.models.seq2seq import configure_hf_d_cache, generate_seq2seq_summary, load_seq2seq_model


OUTPUT_DIR = Path("D:/clin_summ_outputs/model_prefetch")
MODELS = [
    "facebook/bart-large-cnn",
    "google/pegasus-pubmed",
    "google/pegasus-cnn_dailymail",
]
SMOKE_TEXT = (
    "Patient with diabetes and hypertension was admitted for chest pain. "
    "Troponin was negative. The discharge plan included cardiology follow-up "
    "and continuation of home medications."
)
PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, "
    "or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as "
    "MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes."
)


@dataclass(frozen=True)
class PrefetchResult:
    model_name: str
    status: str
    tokenizer_class: str | None
    model_class: str | None
    parameter_count: int | None
    latency_ms: int | None
    smoke_output: str
    error_message: str | None


def main() -> None:
    started = time.perf_counter()
    cache_paths = configure_hf_d_cache()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = [prefetch_model(model_name) for model_name in MODELS]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "runtime_seconds": round(time.perf_counter() - started, 4),
        "cache_paths": cache_paths,
        "proxy_warning": PROXY_WARNING,
        "results": [asdict(result) for result in results],
    }
    (OUTPUT_DIR / "model_prefetch_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown_report(OUTPUT_DIR / "model_prefetch_report.md", payload)
    failed = [result for result in results if result.status != "completed"]
    if failed:
        names = ", ".join(result.model_name for result in failed)
        raise RuntimeError(f"Model prefetch failed for: {names}. See {OUTPUT_DIR}")
    print(f"Model prefetch completed. Reports written to {OUTPUT_DIR}")


def prefetch_model(model_name: str) -> PrefetchResult:
    started = time.perf_counter()
    try:
        tokenizer, model, torch_device = load_seq2seq_model(model_name, device="cpu", local_files_only=False)
        output = generate_seq2seq_summary(
            tokenizer=tokenizer,
            model=model,
            torch_device=torch_device,
            source_note=SMOKE_TEXT,
            max_input_tokens=512,
            max_new_tokens=64,
            num_beams=2,
            no_repeat_ngram_size=3,
        )
        if not output.strip():
            raise RuntimeError("Generation smoke test returned empty output.")
        return PrefetchResult(
            model_name=model_name,
            status="completed",
            tokenizer_class=tokenizer.__class__.__name__,
            model_class=model.__class__.__name__,
            parameter_count=sum(parameter.numel() for parameter in model.parameters()),
            latency_ms=int((time.perf_counter() - started) * 1000),
            smoke_output=output,
            error_message=None,
        )
    except Exception as exc:
        return PrefetchResult(
            model_name=model_name,
            status="failed",
            tokenizer_class=None,
            model_class=None,
            parameter_count=None,
            latency_ms=None,
            smoke_output="",
            error_message=str(exc),
        )


def write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Hugging Face Summarization Model Prefetch",
        "",
        f"> {PROXY_WARNING}",
        "",
        "## Cache Verification",
        "",
    ]
    for key, value in payload["cache_paths"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Model | Status | Tokenizer | Model class | Params | Latency ms | Smoke output / error |",
            "| --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in payload["results"]:
        detail = row["smoke_output"] or row["error_message"] or ""
        lines.append(
            f"| `{row['model_name']}` | `{row['status']}` | `{row['tokenizer_class']}` | "
            f"`{row['model_class']}` | {row['parameter_count']} | {row['latency_ms']} | {detail[:220]} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
