from __future__ import annotations

import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVALUATION_ARTIFACT_ROOT = REPOSITORY_ROOT / "artifacts" / "evaluation"
LEGACY_EVALUATION_ARTIFACT_ROOT = Path("D:/clin_summ_outputs")

ARTIFACT_ROOT_ENV_VARS = (
    "RAG_EVALUATION_ARTIFACT_ROOT",
    "EVALUATION_ARTIFACT_ROOT",
    "BENCHMARK_SNAPSHOT_DIR",
)

KNOWN_BENCHMARK_FOLDERS = (
    "rag_best_models_benchmark_no_gemini_ui",
    "rag_best_models_benchmark",
    "rag_best_models_ollama_50",
    "rag_best_models_ollama_smoke",
    "rag_grounded_benchmark",
    "clinical_context_benchmark",
    "summarization_only_benchmark",
    "medium_benchmark",
    "medium_benchmark_bart_pegasus",
    "performance_benchmark",
)


def normalize_artifact_root(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return REPOSITORY_ROOT / candidate


def configured_evaluation_artifact_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return normalize_artifact_root(explicit)
    for variable in ARTIFACT_ROOT_ENV_VARS:
        value = os.environ.get(variable, "").strip()
        if value:
            return normalize_artifact_root(value)
    return DEFAULT_EVALUATION_ARTIFACT_ROOT


def evaluation_artifact_roots(
    explicit: str | Path | None = None,
    *,
    include_legacy: bool = True,
) -> list[Path]:
    roots = [configured_evaluation_artifact_root(explicit)]
    legacy_available = os.name == "nt" or LEGACY_EVALUATION_ARTIFACT_ROOT.exists()
    if (
        include_legacy
        and legacy_available
        and LEGACY_EVALUATION_ARTIFACT_ROOT not in roots
    ):
        roots.append(LEGACY_EVALUATION_ARTIFACT_ROOT)
    return roots


def benchmark_discovery_dirs(explicit: str | Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    for root in evaluation_artifact_roots(explicit):
        _append_unique(candidates, root)
        for folder in KNOWN_BENCHMARK_FOLDERS:
            _append_unique(candidates, root / folder)
        if root.exists():
            try:
                for child in sorted(root.iterdir()):
                    if child.is_dir() and _looks_like_benchmark_folder(child):
                        _append_unique(candidates, child)
            except OSError:
                continue
    return candidates


def latest_rag_pointer_paths(explicit: str | Path | None = None) -> list[Path]:
    return [
        root / "latest_rag_best_models.json"
        for root in evaluation_artifact_roots(explicit)
    ]


def default_benchmark_output(folder: str) -> Path:
    return configured_evaluation_artifact_root() / folder


def _looks_like_benchmark_folder(path: Path) -> bool:
    return path.name.startswith(
        (
            "rag_best_models",
            "rag_grounded",
            "clinical_context",
            "summarization",
            "medium_benchmark",
            "performance_benchmark",
        )
    )


def _append_unique(paths: list[Path], candidate: Path) -> None:
    if candidate not in paths:
        paths.append(candidate)
