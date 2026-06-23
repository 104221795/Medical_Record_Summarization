# Evaluation Snapshot

The final local demo package should include the completed proxy benchmark
snapshot. Do not run heavy benchmark jobs in CI, Docker image builds, or demo
startup.

## Recommended Snapshot

- Pipeline: Flow 2.1 RAG Best Models
- Dataset: governed benchmark set or selected de-identified proxy subset
- Limit: 50 records preferred, 20 records acceptable for time-limited demo
- Providers:
  - `deterministic`
  - `bart`
  - `pegasus`
  - `qwen2.5`
  - `llama3.2`
  - `gemini2.5_flash_lite` optional only when API is stable and governance allows it

## Manual Command

New outputs default to the portable repository-relative
`artifacts/evaluation` root. Override it with
`RAG_EVALUATION_ARTIFACT_ROOT`.

PowerShell example for an intentional 20-record no-Gemini run:

```powershell
Set-Location "D:\MyNewDesktop\clin-summ"
$env:HF_HOME="D:\hf_cache"
$env:HF_HUB_CACHE="D:\hf_cache\hub"
$env:HF_DATASETS_CACHE="D:\hf_cache\datasets"
$env:TRANSFORMERS_CACHE="D:\hf_cache\hub"
$env:OLLAMA_MODELS="D:\ollama_models"
$env:OLLAMA_API_BASE="http://127.0.0.1:11434"
$env:LLM_GATEWAY_MODE="litellm"
$env:RAG_EMBEDDING_PROVIDER="sentence_transformers"
$env:RAG_SENTENCE_TRANSFORMERS_MODEL="sentence-transformers/all-MiniLM-L6-v2"
$env:RAG_EVALUATION_ARTIFACT_ROOT="artifacts/evaluation"

.\.venv\Scripts\python.exe -m scripts.run_rag_grounded_benchmark `
  --dataset data/processed/governance/benchmark_set.jsonl `
  --limit 20 `
  --models deterministic,bart,pegasus,qwen2.5,llama3.2 `
  --output-dir artifacts/evaluation/rag_best_models_snapshot_20
```

For 50 records, change `--limit 50`.

Do not use this command during final-demo preparation when the completed
50-record snapshot is already available. Copy and verify the approved snapshot
instead.

## Expected Artifacts

- `model_comparison.csv`
- `per_record_metrics.csv`
- `per_record_failure_analysis.jsonl`
- `all_predictions.jsonl`
- provider prediction JSONL files
- `EVALUATION_REPORT.md`
- `run_summary.json`
- `artifact_manifest.json`
- reproducibility/run manifest when available

## Required Disclaimer

Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes.

## Admin Dashboard

Set `RAG_EVALUATION_ARTIFACT_ROOT` or use the repository-relative
`artifacts/evaluation` fallback so Admin Evaluation can load the latest
snapshot. Existing `D:/clin_summ_outputs` folders remain optional legacy
discovery only. Missing artifacts must show a graceful empty state.
