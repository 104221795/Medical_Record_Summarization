# 11 - Evaluation Smoke Test Results And Reporting Plan

## Purpose

This document records the current smoke-test status and defines how evaluation outputs should be reported as the data work scales. It is intentionally conservative: small local results show pipeline readiness, not clinical performance.

## Current Verified Local Smoke Test

Command run locally:

```powershell
python -m pytest backend/tests/test_multiclinsum_importer.py backend/tests/test_mtsamples_importer.py backend/tests/test_mts_dialog_importer.py backend/tests/test_summarization_baseline_runner.py backend/tests/test_semantic_metrics.py -p no:cacheprovider -q
```

Observed result:

```text
18 passed in 0.33s
```

Interpretation:

- importer behavior is test-covered;
- deterministic evaluation path works;
- dry-run model readiness works;
- BART/Pegasus real model loading remains blocked by default;
- BERTScore skipped-dependency status is reported clearly when needed;
- tests use temporary synthetic rows and do not require raw clinical data.

## What Was Tested

| Area | Tests cover | Evidence produced |
| --- | --- | --- |
| MultiClinSum importer | Tiny zip import, alternate filename, auto-detect, multiple-zip error, Layer C.1 label | Processed JSONL shape is valid |
| MTS-Dialog importer | Required CSV columns, four split outputs, Layer C.2 label | Train/validation/test JSONL outputs are valid |
| mtsamples_clean importer | Rule-based default, fake LLM path, Gemini-unavailable fallback | Normalization metadata is preserved |
| Summarization baseline runner | Dry-run readiness, deterministic generation, Pegasus blocked by default, Layer C labels, average length/latency fields | Metrics and summary files are written |
| Semantic metrics | ROUGE and optional BERTScore status | Metrics do not silently omit unavailable BERTScore |

## Current Output Types

When runs are executed against real local proxy data, the expected output directory is:

```text
outputs/evaluation/
```

Expected files by run:

| Run | Output examples |
| --- | --- |
| Deterministic MultiClinSum | `multiclinsum_deterministic_predictions.jsonl`, `multiclinsum_deterministic_metrics.json`, `multiclinsum_deterministic_metrics.csv`, `multiclinsum_deterministic_summary.md` |
| Pegasus dry-run | `multiclinsum_pegasus_readiness.json`, `multiclinsum_pegasus_summary.md` |
| BART dry-run | `multiclinsum_bart_readiness.json`, `multiclinsum_bart_summary.md` |
| MTS-Dialog deterministic | `mts_dialog_deterministic_*` after running on processed MTS-Dialog input |

## Dataset Path Status

### MultiClinSum

Supported local paths:

```text
data/external/multiclinsum/multiclinsum_large_scale_train.zip
data/external/multiclinsum/multiclinsum_large-scale_train_en.zip
```

The importer auto-detects a single zip under `data/external/multiclinsum/`. If multiple zip files exist, it fails clearly and asks for `--zip`.

Import command:

```powershell
python -m backend.app.evaluation.datasets.multiclinsum_importer --limit 20
```

Expected output:

```text
data/processed/multiclinsum/multiclinsum_train.jsonl
```

### MTS-Dialog

Expected local input:

```text
data/external/mts_dialog/MTS-Dialog/Main-Dataset/
  MTS-Dialog-TrainingSet.csv
  MTS-Dialog-ValidationSet.csv
  MTS-Dialog-TestSet-1-MEDIQA-Chat-2023.csv
  MTS-Dialog-TestSet-2-MEDIQA-Sum-2023.csv
```

Import command:

```powershell
python -m backend.app.evaluation.datasets.mts_dialog_importer
```

Expected outputs:

```text
data/processed/mts_dialog/mts_dialog_train.jsonl
data/processed/mts_dialog/mts_dialog_validation.jsonl
data/processed/mts_dialog/mts_dialog_test_1.jsonl
data/processed/mts_dialog/mts_dialog_test_2.jsonl
```

### mtsamples_clean

Rule-based normalization:

```powershell
python -m backend.app.evaluation.datasets.mtsamples_importer `
  --split train `
  --limit 20 `
  --output data/processed/mtsamples_clean/mtsamples_clean_train.jsonl
```

Controlled LLM-assisted normalization:

```powershell
python -m backend.app.evaluation.datasets.mtsamples_importer `
  --split train `
  --limit 20 `
  --output data/processed/mtsamples_clean/mtsamples_clean_train.jsonl `
  --allow-llm-normalization `
  --max-llm-cases 5
```

Expected output:

```text
data/processed/mtsamples_clean/mtsamples_clean_train.jsonl
```

## Baseline Commands

### Deterministic MultiClinSum Baseline

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model deterministic `
  --limit 5 `
  --include-bertscore
```

What it means:

- local deterministic baseline generated summaries;
- ROUGE metrics are computed;
- BERTScore is computed only if dependency/model is available;
- output is Layer C.1 proxy evidence.

What it does not mean:

- no real EHR benchmark claim;
- no clinical performance claim;
- no BART/Pegasus result.

### Pegasus Dry-Run

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model pegasus `
  --limit 3 `
  --dry-run
```

What it means:

- input records are loadable;
- Pegasus run configuration is ready;
- no model download or real generation occurred.

### Real Pegasus Smoke Test

Run this only when model download is intentionally allowed:

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data/processed/multiclinsum/multiclinsum_train.jsonl `
  --model pegasus `
  --limit 3 `
  --allow-model-downloads `
  --include-bertscore
```

What it means:

- real Pegasus generation ran locally;
- metrics can compare generated summaries to references;
- still proxy evidence only.

Safety condition:

- do not run this on credentialed or identifiable clinical text unless local governance and compute constraints are approved.

## Reporting Template

Every evaluation report should include:

```text
Dataset:
Validation layer:
Input path:
Output path:
Model:
Run type: deterministic | dry-run | real generation
Limit:
Metrics:
BERTScore status:
Average latency:
Average input length:
Average output length:
What this result means:
What this result does not mean:
Next scaling step:
```

Example:

```text
Dataset: MultiClinSum
Validation layer: Layer C.1 - Primary Open Clinical Summarization Benchmark
Model: deterministic
Run type: real local deterministic generation
Limit: 5
Metrics: ROUGE-1, ROUGE-2, ROUGE-L, optional BERTScore
Meaning: pipeline and baseline metrics work on open proxy data
Does not mean: real EHR benchmark performance
Next step: scale limit 5 -> 20 -> 50, then run Pegasus dry-run and optional real Pegasus
```

## What Current Results Mean

Current smoke tests mean:

- dataset importers are wired;
- schema normalization is stable for tested cases;
- deterministic baseline generation works;
- optional BERTScore behavior is visible;
- BART/Pegasus downloads are intentionally gated;
- outputs can be written for mentor review.

## What Current Results Do Not Mean

Current smoke tests do not mean:

- MultiClinSum is a real EHR benchmark;
- MTS-Dialog is a real EHR benchmark;
- mtsamples_clean is a main supervised summarization benchmark;
- mock/de-identified data validates clinical model performance;
- BART/Pegasus real generation has been run unless explicitly reported;
- the system is safe for production clinical use;
- EMR/FHIR writeback is ready.

## Scaling Plan

Scale in controlled steps:

| Step | Limit | Goal | Stop condition |
| --- | ---: | --- | --- |
| 1 | 5 | Verify input and output shape | Any schema or metric failure |
| 2 | 20 | Verify small mentor-facing run | Unexpected runtime or metric issue |
| 3 | 50 | Better signal for deterministic baseline | Latency or memory problems |
| 4 | 3 | Real Pegasus smoke, if allowed | Model download or memory issue |
| 5 | 20 | Real Pegasus/BART proxy run, if allowed | Compute budget exceeded |

Do not jump to large runs until the small runs are clean.

## Mentor-Ready Result Statement

Use this wording after the current smoke pass:

> The current evaluation smoke tests validate the data import and baseline evaluation plumbing. MultiClinSum and MTS-Dialog are treated as open proxy datasets, mtsamples_clean is treated as a normalization stress test, and real EHR note-level benchmarking remains pending until credentialed MIMIC-IV-Ext-BHC or MIMIC-IV-Note access is available. BART/Pegasus real generation is disabled by default and should only be run intentionally with model downloads allowed.

## Result Note For Outputs Directory

If `outputs/evaluation/README.md` is created, include:

```text
This directory stores proxy evaluation artifacts only unless explicitly labeled otherwise.
Do not interpret deterministic, BART, Pegasus, or Gemini outputs on mock/open proxy data as real EHR benchmark evidence.
Real EHR note-level benchmark results require credentialed MIMIC-IV-Ext-BHC or MIMIC-IV-Note data and a governed evaluation protocol.
```

## Next Data Work Checklist

- [ ] Confirm which MultiClinSum zip filename exists locally.
- [ ] Run MultiClinSum import with `--limit 20`.
- [ ] Run deterministic baseline with `--limit 5`.
- [ ] Record BERTScore status.
- [ ] Run Pegasus dry-run with `--limit 3`.
- [ ] Import MTS-Dialog if local CSVs exist.
- [ ] Run mtsamples normalization stress test.
- [ ] Create or update `outputs/evaluation/README.md`.
- [ ] Keep Layer D marked pending until credentialed EHR note data exists.
