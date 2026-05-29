from __future__ import annotations

import argparse
import csv
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.services.generators import GeminiJsonClient, GenerationError
from scripts.run_baseline_summarization import (
    compute_rouge_scores,
    maybe_compute_bertscore,
)
from src.data.dataset_loader import load_jsonl_dataset
from src.models import (
    BartSummarizer,
    BaseSummarizer,
    DeterministicSummarizer,
    PegasusSummarizer,
    SummarizationOutput,
)


PROXY_EVALUATION_LABEL = "proxy_deidentified_demo_evaluation"
PROXY_WARNING = (
    "Proxy evaluation only: results are generated from mock/de-identified demo data. "
    "Do not claim real EHR benchmark or clinical performance from these outputs."
)


@dataclass(frozen=True)
class EvaluationProvider:
    name: str
    model_name: str
    summarizer: BaseSummarizer | None = None
    disabled_reason: str | None = None

    @property
    def enabled(self) -> bool:
        return self.summarizer is not None and self.disabled_reason is None


class GeminiEvaluationSummarizer(BaseSummarizer):
    """Small Gemini adapter for proxy evaluation JSON outputs.

    The production persisted workflow has its own Gemini path. This adapter is
    intentionally limited to de-identified/demo evaluation rows and requires
    explicit opt-in before any external request is made.
    """

    provider_name = "gemini"
    model_version = "configured"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "gemini-2.5-flash-lite",
        timeout_seconds: int = 30,
    ):
        self.model_name = model_name
        self.model_version = model_name
        self.client = GeminiJsonClient(api_key, model_name, timeout_seconds=timeout_seconds)

    def _generate_text(self, source_note: str) -> str:
        output_schema = {
            "type": "object",
            "properties": {
                "generated_summary": {"type": "string"},
                "safety_note": {"type": "string"},
            },
            "required": ["generated_summary", "safety_note"],
        }
        raw = self.client.generate_json(
            system_instruction=(
                "You are a citation-grounded clinical documentation assistant. "
                "Summarize only facts explicitly present in the supplied de-identified "
                "source note. Do not recommend diagnosis, treatment, prescriptions, "
                "discharge approval, or medical image interpretation. If information "
                "is missing, say it is not available in the provided data."
            ),
            user_text=(
                "Create a concise draft summary for proxy model evaluation only. "
                "Return JSON matching the requested schema.\n\n"
                f"DE-IDENTIFIED SOURCE NOTE:\n{source_note}"
            ),
            output_schema=output_schema,
            temperature=0.0,
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GenerationError("Gemini returned invalid JSON for proxy evaluation.") from exc
        summary = str(parsed.get("generated_summary") or "").strip()
        if not summary:
            raise GenerationError("Gemini returned an empty generated_summary.")
        return summary


def run_provider_evaluation(
    records: list[dict[str, str]],
    providers: Iterable[EvaluationProvider],
    *,
    output_dir: str | Path = "results/provider_evaluation",
    dataset_path: str | Path = "data/evaluation/sample_ehr_notes.jsonl",
    include_bertscore: bool = False,
    fail_on_provider_error: bool = False,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    per_provider: dict[str, list[dict[str, Any]]] = {}

    for provider in providers:
        rows = _evaluate_provider(
            records,
            provider,
            dataset_path=str(dataset_path),
            fail_on_provider_error=fail_on_provider_error,
        )
        per_provider[provider.name] = rows
        all_rows.extend(rows)
        _write_jsonl(output_path / f"{provider.name}_outputs.jsonl", rows)
        comparison_rows.append(
            _comparison_row(provider, rows, include_bertscore=include_bertscore)
        )

    _write_jsonl(output_path / "provider_outputs.jsonl", all_rows)
    _write_comparison_csv(output_path / "provider_model_comparison.csv", comparison_rows)
    _write_markdown_summary(
        output_path / "EVALUATION_SUMMARY.md",
        comparison_rows=comparison_rows,
        record_count=len(records),
        dataset_path=str(dataset_path),
    )

    return {
        "output_dir": str(output_path),
        "rows": all_rows,
        "comparison_rows": comparison_rows,
        "per_provider": per_provider,
    }


def build_evaluation_providers(args: argparse.Namespace) -> list[EvaluationProvider]:
    requested = _requested_providers(args.providers)
    real_baselines_enabled = (
        args.allow_model_downloads
        or os.environ.get("RUN_REAL_BASELINES") == "1"
        or os.environ.get("RAG_RUN_REAL_BASELINES") == "1"
    )
    providers: list[EvaluationProvider] = []

    for name in requested:
        if name == "deterministic":
            summarizer = DeterministicSummarizer(max_sentences=args.deterministic_sentences)
            providers.append(
                EvaluationProvider(
                    name="deterministic",
                    model_name=summarizer.model_name,
                    summarizer=summarizer,
                )
            )
        elif name == "bart":
            model_name = args.bart_model
            if not real_baselines_enabled:
                providers.append(
                    EvaluationProvider(
                        name="bart",
                        model_name=model_name,
                        disabled_reason=(
                            "BART is disabled by default. Set RUN_REAL_BASELINES=1 "
                            "or pass --allow-model-downloads to run Hugging Face models."
                        ),
                    )
                )
            else:
                providers.append(
                    EvaluationProvider(
                        name="bart",
                        model_name=model_name,
                        summarizer=BartSummarizer(model_name=model_name, device=args.device),
                    )
                )
        elif name == "pegasus":
            model_name = args.pegasus_model
            if not real_baselines_enabled:
                providers.append(
                    EvaluationProvider(
                        name="pegasus",
                        model_name=model_name,
                        disabled_reason=(
                            "Pegasus is disabled by default. Set RUN_REAL_BASELINES=1 "
                            "or pass --allow-model-downloads to run Hugging Face models."
                        ),
                    )
                )
            else:
                providers.append(
                    EvaluationProvider(
                        name="pegasus",
                        model_name=model_name,
                        summarizer=PegasusSummarizer(model_name=model_name, device=args.device),
                    )
                )
        elif name == "gemini":
            providers.append(_build_gemini_provider(args))
        else:
            raise ValueError(f"Unsupported provider '{name}'.")

    return providers


def main() -> None:
    args = _parse_args()
    records = load_jsonl_dataset(
        args.dataset_path,
        dataset=args.dataset,
        split=args.split,
        require_reference=True,
        max_records=args.max_records,
    )
    providers = build_evaluation_providers(args)
    result = run_provider_evaluation(
        records,
        providers,
        output_dir=args.output_dir,
        dataset_path=args.dataset_path,
        include_bertscore=args.include_bertscore,
        fail_on_provider_error=args.fail_on_provider_error,
    )
    print(PROXY_WARNING)
    print(f"Unified provider evaluation outputs written to {result['output_dir']}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run proxy evaluation across deterministic, BART, Pegasus, and Gemini "
            "using mock/de-identified demo datasets."
        )
    )
    parser.add_argument("--dataset-path", default="data/evaluation/sample_ehr_notes.jsonl")
    parser.add_argument("--dataset", default="mock")
    parser.add_argument("--split", default="test")
    parser.add_argument(
        "--providers",
        default="all",
        help="Comma-separated provider list or 'all'. Choices: deterministic,bart,pegasus,gemini.",
    )
    parser.add_argument("--output-dir", default="results/provider_evaluation")
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--deterministic-sentences", type=int, default=3)
    parser.add_argument("--bart-model", default=os.environ.get("BART_MODEL_NAME", "facebook/bart-large-cnn"))
    parser.add_argument("--pegasus-model", default=os.environ.get("PEGASUS_MODEL_NAME", "google/pegasus-xsum"))
    parser.add_argument("--gemini-model", default=os.environ.get("RAG_GEMINI_MODEL", "gemini-2.5-flash-lite"))
    parser.add_argument("--device", type=int, default=-1)
    parser.add_argument("--allow-model-downloads", action="store_true")
    parser.add_argument("--allow-gemini", action="store_true")
    parser.add_argument("--include-bertscore", action="store_true")
    parser.add_argument("--fail-on-provider-error", action="store_true")
    return parser.parse_args()


def _requested_providers(raw: str) -> list[str]:
    if raw.strip().lower() == "all":
        return ["deterministic", "bart", "pegasus", "gemini"]
    providers = [item.strip().lower() for item in raw.split(",") if item.strip()]
    supported = {"deterministic", "bart", "pegasus", "gemini"}
    unsupported = sorted(set(providers) - supported)
    if unsupported:
        raise ValueError(f"Unsupported providers: {', '.join(unsupported)}")
    if not providers:
        raise ValueError("At least one provider is required.")
    return providers


def _build_gemini_provider(args: argparse.Namespace) -> EvaluationProvider:
    model_name = args.gemini_model
    api_key = os.environ.get("RAG_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    explicitly_allowed = args.allow_gemini or os.environ.get("RUN_GEMINI_EVALUATION") == "1"
    gate_enabled = (
        os.environ.get("RAG_LLM_PROVIDER") == "gemini"
        and os.environ.get("RAG_LLM_EXTERNAL_ENABLED", "").lower() == "true"
        and os.environ.get("RAG_LLM_ALLOW_PHI_EXTERNAL", "").lower() == "true"
    )
    if not explicitly_allowed or not gate_enabled or not api_key:
        return EvaluationProvider(
            name="gemini",
            model_name=model_name,
            disabled_reason=(
                "Gemini proxy evaluation is disabled. It requires --allow-gemini "
                "or RUN_GEMINI_EVALUATION=1, plus RAG_LLM_PROVIDER=gemini, "
                "RAG_LLM_EXTERNAL_ENABLED=true, RAG_LLM_ALLOW_PHI_EXTERNAL=true, "
                "and RAG_GEMINI_API_KEY."
            ),
        )
    return EvaluationProvider(
        name="gemini",
        model_name=model_name,
        summarizer=GeminiEvaluationSummarizer(api_key=api_key, model_name=model_name),
    )


def _evaluate_provider(
    records: list[dict[str, str]],
    provider: EvaluationProvider,
    *,
    dataset_path: str,
    fail_on_provider_error: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not provider.enabled:
        for record in records:
            rows.append(_skipped_row(record, provider, dataset_path))
        return rows

    assert provider.summarizer is not None
    for record in records:
        try:
            output = provider.summarizer.generate(record)
            rows.append(_completed_row(record, provider, output, dataset_path))
        except Exception as exc:
            if fail_on_provider_error:
                raise
            rows.append(_failed_row(record, provider, dataset_path, str(exc)))
    return rows


def _completed_row(
    record: dict[str, str],
    provider: EvaluationProvider,
    output: SummarizationOutput,
    dataset_path: str,
) -> dict[str, Any]:
    scores = compute_rouge_scores(output.generated_summary, output.reference_summary)
    return {
        **_base_row(record, provider, dataset_path),
        "status": "completed",
        "error_message": None,
        "generated_summary": output.generated_summary,
        "latency_ms": output.latency_ms,
        "rouge1": scores["rouge1"],
        "rouge2": scores["rouge2"],
        "rougeL": scores["rougeL"],
    }


def _skipped_row(
    record: dict[str, str],
    provider: EvaluationProvider,
    dataset_path: str,
) -> dict[str, Any]:
    return {
        **_base_row(record, provider, dataset_path),
        "status": "skipped",
        "error_message": provider.disabled_reason,
        "generated_summary": "",
        "latency_ms": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
    }


def _failed_row(
    record: dict[str, str],
    provider: EvaluationProvider,
    dataset_path: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        **_base_row(record, provider, dataset_path),
        "status": "failed",
        "error_message": error_message,
        "generated_summary": "",
        "latency_ms": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
    }


def _base_row(
    record: dict[str, str],
    provider: EvaluationProvider,
    dataset_path: str,
) -> dict[str, Any]:
    return {
        "evaluation_type": PROXY_EVALUATION_LABEL,
        "proxy_evaluation": True,
        "proxy_warning": PROXY_WARNING,
        "dataset_path": dataset_path,
        "dataset": record.get("dataset", "mock"),
        "split": record.get("split", ""),
        "note_id": record.get("note_id", ""),
        "patient_id": record.get("patient_id", ""),
        "encounter_id": record.get("encounter_id", ""),
        "model_provider": provider.name,
        "model_name": provider.model_name,
        "source_note": record.get("source_note", ""),
        "reference_summary": record.get("reference_summary", ""),
        "deidentification_warnings": record.get("deidentification_warnings", ""),
    }


def _comparison_row(
    provider: EvaluationProvider,
    rows: list[dict[str, Any]],
    *,
    include_bertscore: bool,
) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    skipped = [row for row in rows if row["status"] == "skipped"]
    failed = [row for row in rows if row["status"] == "failed"]
    predictions = [row["generated_summary"] for row in completed]
    references = [row["reference_summary"] for row in completed]
    status = "completed" if completed and not failed and not skipped else "partial"
    if not completed and skipped and not failed:
        status = "skipped"
    if failed and not completed:
        status = "failed"
    return {
        "evaluation_type": PROXY_EVALUATION_LABEL,
        "model_provider": provider.name,
        "model_name": provider.model_name,
        "status": status,
        "record_count": len(rows),
        "completed_count": len(completed),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "rouge1": _mean_numeric([row["rouge1"] for row in completed]),
        "rouge2": _mean_numeric([row["rouge2"] for row in completed]),
        "rougeL": _mean_numeric([row["rougeL"] for row in completed]),
        "bertscore_f1": maybe_compute_bertscore(predictions, references) if include_bertscore else None,
        "average_latency_ms": _mean_numeric([row["latency_ms"] for row in completed]),
        "notes": _provider_notes(provider, failed),
    }


def _provider_notes(provider: EvaluationProvider, failed: list[dict[str, Any]]) -> str:
    if provider.disabled_reason:
        return provider.disabled_reason
    if failed:
        return "; ".join(sorted({str(row["error_message"]) for row in failed if row["error_message"]}))
    return PROXY_WARNING


def _mean_numeric(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "evaluation_type",
        "model_provider",
        "model_name",
        "status",
        "record_count",
        "completed_count",
        "skipped_count",
        "failed_count",
        "rouge1",
        "rouge2",
        "rougeL",
        "bertscore_f1",
        "average_latency_ms",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown_summary(
    path: Path,
    *,
    comparison_rows: list[dict[str, Any]],
    record_count: int,
    dataset_path: str,
) -> None:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# Unified Provider Proxy Evaluation Summary",
        "",
        f"> {PROXY_WARNING}",
        "",
        "## Scope",
        "",
        "- Evaluation layer: proxy functional/model comparison.",
        "- Dataset type: mock or de-identified demo data only.",
        f"- Dataset path: `{dataset_path}`.",
        f"- Record count: `{record_count}`.",
        "- Real EHR benchmark status: pending until credentialed data is available.",
        f"- Generated at: `{generated_at}`.",
        "",
        "## Provider Comparison",
        "",
        "| Provider | Model | Status | Completed | Skipped | Failed | ROUGE-1 | ROUGE-2 | ROUGE-L | Avg latency ms |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in comparison_rows:
        lines.append(
            "| {provider} | {model} | {status} | {completed} | {skipped} | {failed} | {r1} | {r2} | {rl} | {latency} |".format(
                provider=row["model_provider"],
                model=row["model_name"],
                status=row["status"],
                completed=row["completed_count"],
                skipped=row["skipped_count"],
                failed=row["failed_count"],
                r1=_display(row["rouge1"]),
                r2=_display(row["rouge2"]),
                rl=_display(row["rougeL"]),
                latency=_display(row["average_latency_ms"]),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation Rules",
            "",
            "- These numbers are smoke/proxy signals only.",
            "- Do not compare them as final clinical quality claims.",
            "- BART, Pegasus, and Gemini may be skipped unless explicitly enabled.",
            "- Real EHR benchmark results must be produced from credentialed, governed, de-identified datasets only.",
            "- Human review remains required before any generated summary is considered approved.",
            "",
            "## Output Files",
            "",
            "- `provider_outputs.jsonl`: all provider/record rows.",
            "- `<provider>_outputs.jsonl`: one JSONL file per provider.",
            "- `provider_model_comparison.csv`: aggregate proxy metrics.",
            "- `EVALUATION_SUMMARY.md`: this summary.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _display(value: Any) -> str:
    if value is None or value == "":
        return "not_available"
    return str(value)


if __name__ == "__main__":
    main()
