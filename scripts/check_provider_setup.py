"""Local provider readiness diagnostics without external model/API calls."""

from __future__ import annotations

import importlib.util
import os


def installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def main() -> None:
    print("Provider readiness diagnostics")
    print("==============================")
    try:
        from backend.app.config import Settings

        settings = Settings()
        print(f"Gemini key loaded by backend settings: {bool(settings.gemini_api_key)}")
        print(f"RAG_LLM_PROVIDER: {settings.llm_provider}")
        print(f"RAG_LLM_EXTERNAL_ENABLED: {settings.llm_external_enabled}")
        print(f"RAG_LLM_ALLOW_PHI_EXTERNAL: {settings.llm_allow_phi_external}")
        print(f"RAG_GEMINI_MODEL: {settings.gemini_model}")
    except Exception as exc:
        print(f"Backend settings could not load safely: {exc}")

    print()
    print("Python package availability")
    for module_name in ("transformers", "torch", "sentencepiece", "accelerate"):
        print(f"- {module_name}: {installed(module_name)}")

    print()
    print("Baseline flags")
    print(f"RUN_REAL_BASELINES: {os.environ.get('RUN_REAL_BASELINES')}")
    print(f"RAG_RUN_REAL_BASELINES: {os.environ.get('RAG_RUN_REAL_BASELINES')}")
    print(f"BART_MODEL_NAME: {os.environ.get('BART_MODEL_NAME') or 'facebook/bart-large-cnn'}")
    print(f"PEGASUS_MODEL_NAME: {os.environ.get('PEGASUS_MODEL_NAME') or 'google/pegasus-xsum'}")

    print()
    print("Interpretation")
    print("- deterministic works by default and does not need external setup.")
    print("- Gemini only runs when RAG_LLM_PROVIDER=gemini, RAG_LLM_EXTERNAL_ENABLED=true,")
    print("  RAG_LLM_ALLOW_PHI_EXTERNAL=true, and a Gemini key is available.")
    print("- BART/Pegasus real model execution only runs when RUN_REAL_BASELINES=1.")
    print("- Pegasus usually needs sentencepiece installed for tokenizer loading.")


if __name__ == "__main__":
    main()
