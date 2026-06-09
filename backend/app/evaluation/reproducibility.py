from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any


TRACKED_PACKAGES = [
    "bert-score",
    "fastapi",
    "numpy",
    "pandas",
    "qdrant-client",
    "rouge-score",
    "sentence-transformers",
    "torch",
    "transformers",
]


def build_reproducibility_manifest(
    *,
    run_name: str,
    dataset_path: Path,
    output_dir: Path,
    model_checkpoints: dict[str, str],
    generation_params: dict[str, Any],
    retrieval_config: dict[str, Any],
    prompt_template_version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dataset_stats = _dataset_stats(dataset_path)
    return {
        "schema_version": "reproducibility_manifest.v2",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "run_name": run_name,
        "dataset": {
            "path": str(dataset_path),
            "version": dataset_stats.get("dataset_version"),
            "record_count": dataset_stats.get("record_count"),
            "record_id_hash": dataset_stats.get("record_id_hash"),
            "first_record_ids": dataset_stats.get("first_record_ids"),
        },
        "output_dir": str(output_dir),
        "model_checkpoints": model_checkpoints,
        "prompt_template_version": prompt_template_version or "not_versioned",
        "retrieval_config": retrieval_config,
        "generation_params": generation_params,
        "cache_paths": _cache_paths(),
        "git": _git_state(),
        "runtime_environment": _runtime_environment(),
        "packages": _package_versions(TRACKED_PACKAGES),
        "extra": extra or {},
    }


def write_reproducibility_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _dataset_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"record_count": 0, "dataset_version": "missing", "record_id_hash": None, "first_record_ids": []}
    import hashlib

    record_ids: list[str] = []
    dataset_names: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            record_id = str(row.get("note_id") or row.get("id") or len(record_ids))
            record_ids.append(record_id)
            if row.get("dataset"):
                dataset_names.add(str(row["dataset"]))
    digest = hashlib.sha256("\n".join(record_ids).encode("utf-8")).hexdigest() if record_ids else None
    return {
        "record_count": len(record_ids),
        "dataset_version": "+".join(sorted(dataset_names)) or path.stem,
        "record_id_hash": digest,
        "first_record_ids": record_ids[:20],
    }


def _cache_paths() -> dict[str, str | None]:
    return {
        key: os.environ.get(key)
        for key in ("HF_HOME", "HF_HUB_CACHE", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE")
    }


def _git_state() -> dict[str, Any]:
    return {
        "commit": _run_git(["rev-parse", "HEAD"]),
        "branch": _run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "dirty_files": _run_git_lines(["status", "--short"]),
    }


def _runtime_environment() -> dict[str, Any]:
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": str(Path.cwd()),
    }


def _package_versions(package_names: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in package_names:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not_installed"
    return versions


def _run_git(args: list[str]) -> str | None:
    lines = _run_git_lines(args)
    return lines[0] if lines else None


def _run_git_lines(args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=Path(__file__).resolve().parents[3],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]
