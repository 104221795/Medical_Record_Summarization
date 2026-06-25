from __future__ import annotations

import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
HTML = HERE / "index.html"
PDF = HERE / "Medical_Record_Summarization_Final_Enterprise_Deck.pdf"


def find_edge() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    return next((p for p in candidates if p.exists()), None)


def main() -> int:
    browser = find_edge()
    if not browser:
        print("No Edge/Chrome executable found. Open index.html and print to PDF manually.")
        return 1
    if PDF.exists():
        PDF.unlink()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--print-to-pdf=" + str(PDF),
        HTML.resolve().as_uri(),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=HERE, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if not PDF.exists():
        print("PDF was not created.")
        return result.returncode or 1
    print(f"Created {PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
