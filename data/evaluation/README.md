# Evaluation Dataset Layer

This directory contains small de-identified fixtures for local development and
evaluation smoke tests. Do not place real identifiable clinical data here.

## Committed Fixture

`sample_ehr_notes.jsonl` is a tiny mock/de-identified dataset using the final
MVP evaluation schema:

```json
{
  "note_id": "note_001",
  "patient_id": "patient_001",
  "encounter_id": "enc_001",
  "source_note": "...",
  "reference_summary": "...",
  "dataset": "mock",
  "split": "train"
}
```

## Credentialed MIMIC Data

MIMIC-IV-Note and MIMIC-IV-Ext-BHC require credentialed access and data-use
compliance. Obtain access through the official PhysioNet process. Do not commit
raw MIMIC files or derived files that may contain clinical text.

Recommended local-only folder structure:

```text
data/
  mimic_iv_note/              # ignored by git
    discharge.csv.gz
  mimic_iv_ext_bhc/           # ignored by git
    mimic_iv_ext_bhc.csv
  evaluation/
    sample_ehr_notes.jsonl    # committed mock fixture only
```

These folders are ignored by `.gitignore`.

## Loader Mapping

The Phase 7A dataset loader supports:

- Existing local JSONL sample format.
- Legacy JSONL records with `inputs` and `target` fields.
- MIMIC-IV-Note-style discharge summary files with columns such as
  `note_id`, `subject_id`, `hadm_id`, and `text`.
- MIMIC-IV-Ext-BHC-style files with source discharge summary and target Brief
  Hospital Course columns.

The normalized internal schema is used by future BART/Pegasus/Gemini
evaluation:

```text
source_note -> model input
reference_summary -> evaluation reference
note_id/patient_id/encounter_id -> provenance and split keys
dataset/split -> experiment metadata
```

## How This Feeds Evaluation

1. Load and normalize dataset rows with `src.data.dataset_loader`.
2. Build provider inputs for deterministic, BART, Pegasus, or Gemini.
3. Generate draft summaries.
4. Run claim extraction and citation verification.
5. Compare model output against `reference_summary`.
6. Store `model_runs`, citation coverage, safety flags, and human evaluation
   results.

The committed mock fixture is only for tests and demos. Real evaluation should
use credentialed, de-identified, access-controlled datasets.
