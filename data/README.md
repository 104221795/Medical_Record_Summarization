# Data Directory

Use mock or de-identified data by default. Do not commit raw clinical datasets, credentialed MIMIC files, provider exports, or identifiable patient data.

## Local Layout

```text
data/
  demo/
    final_demo_cases.json
  evaluation/
    sample_ehr_notes.jsonl
  external/
    multiclinsum/
      multiclinsum_large_scale_train.zip
      # or multiclinsum_large-scale_train_en.zip
    mts_dialog/
      MTS-Dialog/Main-Dataset/
    mtsamples_clean/
  processed/
    multiclinsum/
    mts_dialog/
    mtsamples_clean/
    ehr_benchmark/
```

`data/external/` and `data/processed/` are local working areas. Keep large or credentialed datasets out of git.

## Dataset Roles

| Path/source | Role | Claim boundary |
| --- | --- | --- |
| `data/evaluation/sample_ehr_notes.jsonl` | Tiny mock/de-identified smoke fixture | Workflow only |
| `data/demo/final_demo_cases.json` | Curated demo cases | Demo only |
| `data/external/multiclinsum/` | Layer C.1 primary open proxy summarization benchmark | Not real EHR |
| `data/external/mts_dialog/` | Layer C.2 auxiliary dialogue-to-note proxy evaluation | Not real EHR |
| `BIOMEDNLP/mtsamples_clean` | Messy transcription normalization stress test | Not main supervised summarization benchmark |
| `data/processed/ehr_benchmark/` | Reserved for future MIMIC-IV-Ext-BHC / MIMIC-IV-Note processing | Pending credentialed access |

## Dataset Resources

| Dataset/resource | Best use in this repo | Link |
| --- | --- | --- |
| MultiClinSum | Layer C.1 primary open proxy clinical summarization benchmark | https://zenodo.org/records/17341582 |
| BioASQ MultiClinSum task | Background for MultiClinSum task framing | https://participants-area.bioasq.org/general_information/MultiClinSum/ |
| MTS-Dialog | Layer C.2 auxiliary dialogue-to-note section evaluation | https://github.com/abachaa/MTS-Dialog |
| MEDIQA-Chat 2023 | Challenge context for MTS-Dialog and ACI-BENCH tasks | https://github.com/abachaa/MEDIQA-Chat-2023 |
| ACI-BENCH | Optional Layer C.3 full-visit dialogue-to-note proxy | https://github.com/wyim/aci-bench |
| MTSamples | Normalization stress-test source family | https://mtsamples.com/ |
| MIMIC-III demo | Structured EHR workflow validation | https://physionet.org/content/mimiciii-demo/1.4/ |
| MIMIC-IV-Ext-BHC | Future real EHR note-level benchmark | https://physionet.org/content/labelled-notes-hospital-course/ |
| MIMIC-IV-Note | Future governed clinical note corpus | https://physionet.org/content/mimic-iv-note/ |

## Setup

Install dependencies from the single root requirements file:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Import MultiClinSum

Place exactly one supported zip under `data/external/multiclinsum/`:

```text
multiclinsum_large_scale_train.zip
multiclinsum_large-scale_train_en.zip
```

Then run:

```powershell
python -m backend.app.evaluation.datasets.multiclinsum_importer --limit 20
```

The importer auto-detects a single zip. If multiple zip files exist, pass `--zip` explicitly.

## Import MTS-Dialog

Expected input directory:

```text
data/external/mts_dialog/MTS-Dialog/Main-Dataset/
```

Expected files:

```text
MTS-Dialog-TrainingSet.csv
MTS-Dialog-ValidationSet.csv
MTS-Dialog-TestSet-1-MEDIQA-Chat-2023.csv
MTS-Dialog-TestSet-2-MEDIQA-Sum-2023.csv
```

Run:

```powershell
python -m backend.app.evaluation.datasets.mts_dialog_importer
```

Outputs:

```text
data/processed/mts_dialog/mts_dialog_train.jsonl
data/processed/mts_dialog/mts_dialog_validation.jsonl
data/processed/mts_dialog/mts_dialog_test_1.jsonl
data/processed/mts_dialog/mts_dialog_test_2.jsonl
```

## Run A Proxy Baseline

```powershell
python -m backend.app.evaluation.summarization_baseline_runner `
  --dataset multiclinsum `
  --input data\processed\multiclinsum\multiclinsum_train.jsonl `
  --model deterministic `
  --limit 5 `
  --include-bertscore
```

Results are proxy evaluation artifacts under `outputs/evaluation/`. Do not present them as real EHR benchmark or clinical performance.
