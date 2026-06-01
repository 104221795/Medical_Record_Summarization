# 11 - Evaluation Smoke Test Results

## Latest Local Smoke Test

Command:

```powershell
python -m pytest backend/tests/test_multiclinsum_importer.py backend/tests/test_mtsamples_importer.py backend/tests/test_mts_dialog_importer.py backend/tests/test_summarization_baseline_runner.py backend/tests/test_semantic_metrics.py -q
```

Observed result:

```text
18 passed
```

One local pytest cache warning may appear on Windows if `.pytest_cache` cannot be written. That warning does not indicate a test failure.

## What Was Tested

| Area | Coverage |
| --- | --- |
| MultiClinSum importer | Tiny zip import, alternate filename, auto-detect, multiple-zip error, Layer C.1 label |
| MTS-Dialog importer | Required CSV columns, four split outputs, Layer C.2 label |
| mtsamples_clean importer | Rule-based default, optional fake LLM path, fallback when Gemini unavailable |
| Summarization baseline runner | Dry-run readiness, deterministic generation, real Pegasus blocked by default, Layer C labels, average length/latency fields |
| Semantic metrics | ROUGE and clear BERTScore skipped-dependency status |

## Dataset

The test suite uses temporary synthetic rows and does not require real clinical data or external model downloads.

For a real local MultiClinSum import, place one zip under:

```text
data/external/multiclinsum/
```

Supported filenames:

```text
multiclinsum_large_scale_train.zip
multiclinsum_large-scale_train_en.zip
```

Then run:

```powershell
python -m backend.app.evaluation.datasets.multiclinsum_importer --limit 20
```

## Model Runs

Deterministic real generation command:

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model deterministic `
  --limit 5 `
  --include-bertscore
```

Pegasus dry-run command:

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model pegasus `
  --limit 3 `
  --dry-run
```

Real Pegasus smoke test, only if model download is intentionally allowed:

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model pegasus `
  --limit 3 `
  --allow-model-downloads `
  --include-bertscore
```

## What Results Mean

These tests mean the local importer/evaluation plumbing is working for controlled smoke cases. They also confirm the code does not silently download BART/Pegasus models by default.

## What Results Do Not Mean

These tests do not mean:

- MultiClinSum is a real EHR benchmark;
- MTS-Dialog is a real EHR benchmark;
- mtsamples_clean is a main supervised summarization benchmark;
- mock/de-identified data validates clinical model performance;
- BART/Pegasus have been clinically validated.

## Next Scaling Step

After importing the real local MultiClinSum zip, scale the deterministic baseline from:

```text
limit 5 -> limit 20 -> limit 50
```

Only run real BART/Pegasus generation after intentionally enabling model downloads and confirming the machine has enough disk, memory, and time budget.
