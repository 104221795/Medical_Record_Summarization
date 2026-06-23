from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, "
    "clinical effectiveness, or real-world healthcare performance."
)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    checks.append(capture_http("health", f"{args.base_url}/health", output_dir))
    checks.append(capture_http("ready", f"{args.base_url}/ready", output_dir))
    checks.append(
        capture_command(
            "git_status",
            ["git", "status", "--short"],
            output_dir,
            cwd=ROOT,
        )
    )
    checks.append(
        capture_command(
            "docker_compose_ps",
            ["docker", "compose", "ps"],
            output_dir,
            cwd=ROOT,
        )
    )
    checks.append(
        capture_command(
            "docker_compose_logs",
            ["docker", "compose", "logs", "--tail", "120", "app", "worker", "db", "redis"],
            output_dir,
            cwd=ROOT,
        )
    )
    checks.append(
        capture_command(
            "docker_image_size",
            ["docker", "image", "inspect", "clin-summ-app:latest", "--format", "{{.Size}}"],
            output_dir,
            cwd=ROOT,
        )
    )

    if args.run_verification:
        checks.append(
            capture_command(
                "backend_lightweight_tests",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "backend/tests/test_deployment_smoke.py",
                    "backend/tests/test_clinical_safety_layer.py",
                    "backend/tests/test_background_jobs.py",
                    "backend/tests/test_bart_pegasus_dashboard_integration.py",
                    "backend/tests/test_week5_analysis.py",
                    "-p",
                    "no:cacheprovider",
                    "-q",
                ],
                output_dir,
                cwd=ROOT,
                timeout=240,
            )
        )
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        checks.append(
            capture_command(
                "frontend_build",
                [npm or "npm", "run", "build"],
                output_dir,
                cwd=ROOT / "frontend",
                timeout=240,
            )
        )
    if args.run_full_tests:
        checks.append(
            capture_command(
                "backend_full_suite",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "backend/tests",
                    "-p",
                    "no:cacheprovider",
                    "-q",
                ],
                output_dir,
                cwd=ROOT,
                timeout=900,
            )
        )
    if args.run_docker_build:
        checks.append(
            capture_command(
                "docker_build",
                ["docker", "build", "-t", "clin-summ:demo-evidence", "."],
                output_dir,
                cwd=ROOT,
                timeout=900,
            )
        )

    benchmark = capture_benchmark_summary(
        ROOT / "artifacts/evaluation/rag_best_models_benchmark_50_no_gate",
        output_dir,
    )
    checks.append(benchmark)
    manifest = {
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repository": str(ROOT),
        "base_url": args.base_url,
        "proxy_warning": PROXY_WARNING,
        "checks": checks,
        "not_automatically_captured": [
            "UI screenshots",
            "final demo video",
            "SharePoint link and permission verification",
            "real human/clinician review scores",
        ],
    }
    (output_dir / "evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "EVIDENCE_SUMMARY.md").write_text(
        build_summary(manifest),
        encoding="utf-8",
    )
    print(f"Demo evidence captured at {output_dir}")


def parse_args() -> argparse.Namespace:
    date_folder = datetime.now().date().isoformat()
    parser = argparse.ArgumentParser(
        description="Capture reproducible local Docker Compose demo evidence."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--output-dir",
        default=f"artifacts/demo_evidence/{date_folder}",
    )
    parser.add_argument("--run-verification", action="store_true")
    parser.add_argument("--run-full-tests", action="store_true")
    parser.add_argument("--run-docker-build", action="store_true")
    return parser.parse_args()


def capture_http(name: str, url: str, output_dir: Path) -> dict[str, Any]:
    path = output_dir / f"{name}.json"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body)
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return {
                "name": name,
                "status": "passed" if response.status == 200 else "failed",
                "http_status": response.status,
                "artifact": path.name,
            }
    except Exception as exc:
        path.write_text(
            json.dumps({"error": f"{type(exc).__name__}: {exc}"}, indent=2),
            encoding="utf-8",
        )
        return {
            "name": name,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "artifact": path.name,
        }


def capture_command(
    name: str,
    command: list[str],
    output_dir: Path,
    *,
    cwd: Path,
    timeout: int = 120,
) -> dict[str, Any]:
    path = output_dir / f"{name}.txt"
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        content = (
            f"COMMAND: {' '.join(command)}\n"
            f"EXIT_CODE: {result.returncode}\n\n"
            f"STDOUT\n{result.stdout}\n\n"
            f"STDERR\n{result.stderr}\n"
        )
        path.write_text(content, encoding="utf-8")
        return {
            "name": name,
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "artifact": path.name,
        }
    except Exception as exc:
        path.write_text(
            f"COMMAND: {' '.join(command)}\nERROR: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )
        return {
            "name": name,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "artifact": path.name,
        }


def capture_benchmark_summary(root: Path, output_dir: Path) -> dict[str, Any]:
    comparison_path = root / "model_comparison.csv"
    rows = []
    if comparison_path.exists():
        with comparison_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    summary = {
        "selected_output": str(root),
        "provider_count": len(rows),
        "completed_predictions": sum(int(row.get("completed_count") or 0) for row in rows),
        "bertscore_provider_count": sum(
            1 for row in rows if row.get("bertscore_status") == "computed"
        ),
        "best_rougeL_provider": max(
            rows,
            key=lambda row: float(row.get("rougeL") or 0.0),
            default={},
        ).get("model_provider"),
        "proxy_warning": PROXY_WARNING,
    }
    path = output_dir / "flow_2_1_summary.json"
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    passed = (
        summary["provider_count"] == 5
        and summary["completed_predictions"] == 250
        and summary["bertscore_provider_count"] == 5
    )
    return {
        "name": "flow_2_1_portable_snapshot",
        "status": "passed" if passed else "failed",
        "artifact": path.name,
        **summary,
    }


def build_summary(manifest: dict[str, Any]) -> str:
    lines = [
        "# Local Docker Compose Evidence Summary",
        "",
        f"Captured: `{manifest['captured_at']}`",
        "",
        f"> {manifest['proxy_warning']}",
        "",
        "| Check | Status | Artifact |",
        "| --- | --- | --- |",
    ]
    for check in manifest["checks"]:
        lines.append(
            f"| {check['name']} | {check['status']} | `{check.get('artifact', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Manual Evidence Still Required",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in manifest["not_automatically_captured"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
