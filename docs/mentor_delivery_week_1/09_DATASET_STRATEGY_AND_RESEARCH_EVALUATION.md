# 09 - Dataset Strategy And Research Evaluation

## Purpose

This document is the data backbone for the Medical Record Summarization MVP. It explains which datasets are suitable, what each dataset can prove, how each dataset should be placed in the repo, and what claims are allowed.

The central principle is:

> The project evaluates what can be validly evaluated at the current access level, while explicitly reserving real EHR note-level claims for future credentialed datasets.

This matters because medical record summarization has several related but different tasks:

- product workflow validation;
- structured EHR ingestion and mapping;
- open clinical summarization proxy evaluation;
- dialogue-to-note proxy evaluation;
- messy input normalization;
- future real EHR note-level benchmarking;
- human safety and usefulness review.

These tasks need different datasets. A dataset that is excellent for one task can be weak or misleading for another.

## Recommended Dataset Stack

Use this stack in order. The first three layers are practical for Week 1. The real EHR benchmark layer is intentionally future work.

| Priority | Dataset/resource | Layer | Why it fits | Current action |
| --- | --- | --- | --- | --- |
| 1 | MultiClinSum | C.1 | Best current open proxy for clinical source-to-summary evaluation with source/reference pairs | Import and run deterministic plus optional BART/Pegasus baselines |
| 2 | MTS-Dialog | C.2 | Strong auxiliary doctor-patient dialogue to note-section dataset | Import after local dataset placement |
| 3 | BIOMEDNLP/mtsamples_clean or MTSamples-derived data | Normalization | Good stress test for messy medical transcription input | Use for section normalization and difficult-case routing |
| 4 | ACI-BENCH | C.3 | Optional full-visit dialogue-to-note benchmark | Add later if time allows |
| 5 | MIMIC-III demo | B | Structured EHR mapping and workflow validation | Use for patient/encounter/lab/diagnosis/medication mapping only |
| 6 | MIMIC-IV-Ext-BHC | D | Best future real EHR note-level hospital course summarization benchmark | Pending credentialed PhysioNet access |
| 7 | MIMIC-IV-Note | D | Future real clinical note source for fallback/derived note-level tasks | Pending credentialed PhysioNet access |
| 8 | Human evaluation set | E | Final usefulness, factuality, citation, and safety perception check | Build from generated outputs after proxy runs |

## Dataset Role Table

| Evidence layer | Dataset/source | Role | What it validates | What it must not be used to claim |
| --- | --- | --- | --- | --- |
| A | Mock/de-identified demo data | Functional workflow validation | UI/API flow, draft status, citation rendering, review state, audit events | Clinical model performance |
| B | MIMIC-III demo or structured EHR-style local data | Structured EHR validation | Patient, encounter, diagnosis, lab, medication, and structured citation mapping | Note-level summarization quality |
| C.1 | MultiClinSum | Primary open clinical summarization benchmark | Source/reference summarization metrics on clinical case-report style text | Real hospital EHR benchmark performance |
| C.2 | MTS-Dialog | Auxiliary dialogue-to-note section proxy | Doctor-patient dialogue to note-section generation behavior | Full medical record summarization performance |
| C.3 | ACI-BENCH | Optional full-visit dialogue-to-note proxy | Full conversation to visit note generation behavior | Real EHR discharge-note performance |
| Normalization | mtsamples_clean / MTSamples-derived transcription data | Messy input stress test | Section detection, chunking, difficulty scoring, controlled LLM normalization | Main supervised summarization benchmark |
| D | MIMIC-IV-Ext-BHC / MIMIC-IV-Note | Future real EHR note-level benchmark | Real EHR note summarization after governed access | Current Week 1 performance |
| E | Human evaluation | Safety/usefulness validation | Factuality, completeness, readability, citation usefulness, perceived hallucination risk | Fully automated clinical validation |

## Why These Datasets Are Separated

### Workflow validation is not model evaluation

Mock/demo data can prove that the MVP workflow works: ingestion, summary generation, citation display, review actions, and audit logs. It cannot prove that a summarizer performs well clinically.

### Structured EHR mapping is not note summarization

MIMIC-III demo or similar structured data can validate patient records, encounters, labs, medications, diagnoses, and structured evidence mapping. It does not provide the supervised note-to-summary benchmark needed for BART/Pegasus quality claims.

### Open proxy summarization is not real EHR benchmarking

MultiClinSum, MTS-Dialog, and ACI-BENCH are useful open proxy datasets, but they are not the same as credentialed hospital EHR notes. They let the project compare baselines honestly while avoiding false production claims.

### Messy input normalization is not summary quality

Medical transcription-style text is valuable because it stresses the normalizer. That tests whether the product can organize difficult input safely. It does not test whether generated summaries match clinical reference summaries.

### Real EHR claims need credentialed datasets

The correct future target for real EHR note-level claims is MIMIC-IV-Ext-BHC or MIMIC-IV-Note after approved access, local-only handling, and governance.

## Resource Inventory

### MultiClinSum

| Item | Detail |
| --- | --- |
| Resource | BioASQ MultiClinSum and Zenodo dataset release |
| Task | Summarization of long clinical case reports in multiple languages |
| Format | Full text and summary `.txt` files, paired by filename |
| Languages | English, Spanish, French, Portuguese |
| Metrics referenced by task | ROUGE-2 and BERTScore |
| License | CC BY 4.0 on Zenodo release |
| Repo role | Layer C.1 primary open clinical summarization benchmark |

Why suitable:

- It has source/reference summary pairs.
- It is clinical text rather than generic summarization.
- It supports ROUGE and BERTScore evaluation.
- It is open enough for Week 1 work.

Limitations:

- It is based on clinical case reports, not raw hospital EHR notes.
- It should not be described as a real EHR benchmark.
- It may differ from discharge summaries in style, structure, length, and source distribution.

Local placement:

```text
data/external/multiclinsum/
  multiclinsum_large_scale_train.zip
  # or
  multiclinsum_large-scale_train_en.zip
```

Importer:

```powershell
python -m backend.app.evaluation.datasets.multiclinsum_importer --limit 20
```

Output:

```text
data/processed/multiclinsum/multiclinsum_train.jsonl
```

Allowed claim:

> MultiClinSum is the primary Layer C.1 open proxy clinical summarization benchmark for BART/Pegasus/deterministic comparison.

Forbidden claim:

> MultiClinSum proves real EHR note-level summarization performance.

### MTS-Dialog

| Item | Detail |
| --- | --- |
| Resource | `abachaa/MTS-Dialog` GitHub repository |
| Task | Doctor-patient conversation to clinical note section |
| Size | 1.7k conversation/summary pairs; train 1,201, validation 100, two 200-row test sets |
| Output fields | `ID`, `section_header`, `section_text`, `dialogue` |
| License | CC BY 4.0 in repository |
| Repo role | Layer C.2 auxiliary dialogue-to-note proxy evaluation |

Why suitable:

- It is directly related to clinical documentation.
- It uses doctor-patient conversations and note sections.
- It supports the ambient/documentation side of the MVP.

Limitations:

- It is a dialogue-to-note-section task, not full EHR note summarization.
- It should not replace MultiClinSum as the main source-to-summary benchmark.
- It should not be called a real EHR benchmark.

Local placement:

```text
data/external/mts_dialog/MTS-Dialog/Main-Dataset/
  MTS-Dialog-TrainingSet.csv
  MTS-Dialog-ValidationSet.csv
  MTS-Dialog-TestSet-1-MEDIQA-Chat-2023.csv
  MTS-Dialog-TestSet-2-MEDIQA-Sum-2023.csv
```

Importer:

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

Allowed claim:

> MTS-Dialog supports Layer C.2 auxiliary dialogue-to-note proxy evaluation.

Forbidden claim:

> MTS-Dialog validates complete medical record summarization or real EHR performance.

### ACI-BENCH

| Item | Detail |
| --- | --- |
| Resource | `wyim/aci-bench` GitHub repository, Figshare dataset, Nature Scientific Data paper |
| Task | Full doctor-patient visit conversation to clinical note |
| Size in challenge splits | Train 67, validation 20, several 40-row test subsets |
| Repo role | Layer C.3 optional full-visit dialogue-to-note proxy |

Why suitable:

- It is closer to full-visit clinical note generation than MTS-Dialog sections.
- It captures ambient clinical intelligence use cases.
- It can broaden evaluation beyond source-document summarization.

Limitations:

- It is small.
- It is dialogue-to-note, not real EHR note-to-summary.
- It should be optional after MultiClinSum and MTS-Dialog are stable.

Recommended local placement if added:

```text
data/external/aci_bench/
```

Allowed claim:

> ACI-BENCH supports optional Layer C.3 full-visit dialogue-to-note proxy evaluation.

Forbidden claim:

> ACI-BENCH replaces credentialed EHR note benchmarking.

### mtsamples_clean / MTSamples-Derived Data

| Item | Detail |
| --- | --- |
| Resource | BIOMEDNLP/mtsamples_clean or MTSamples-derived medical transcription data |
| Task | Messy medical transcription input handling |
| Source family | MTSamples.com medical transcription samples across many specialties |
| Repo role | Normalization stress test |

Why suitable:

- It contains medical transcription-style text with varied sections and specialties.
- It is useful for testing rule-based heading detection.
- It is useful for testing difficult-case detection and controlled Gemini normalization.

Limitations:

- Public MTSamples-style data is sample transcription data, not governed EHR.
- It does not provide the main source/reference summarization benchmark.
- Accuracy and quality can vary; treat it as input robustness data.

Importer:

```powershell
python -m backend.app.evaluation.datasets.mtsamples_importer --limit 20
```

Optional controlled LLM normalization:

```powershell
python -m backend.app.evaluation.datasets.mtsamples_importer `
  --limit 20 `
  --allow-llm-normalization `
  --max-llm-cases 5
```

Allowed claim:

> mtsamples_clean is used to stress test messy input normalization and section extraction.

Forbidden claim:

> mtsamples_clean is the main supervised summarization benchmark.

### MIMIC-III Clinical Database Demo

| Item | Detail |
| --- | --- |
| Resource | PhysioNet MIMIC-III Clinical Database Demo v1.4 |
| Task | Structured EHR workflow validation |
| Repo role | Layer B structured EHR validation |

Why suitable:

- It gives a realistic structured EHR-style layout.
- It supports patient, encounter, lab, diagnosis, and medication mapping.
- It is good for FHIR/evidence mapping demos.

Limitations:

- It is demo data, not a full note-level summarization benchmark.
- It should not be used to claim BART/Pegasus clinical summarization performance.

Allowed claim:

> MIMIC-III demo validates structured EHR mapping and workflow behavior.

Forbidden claim:

> MIMIC-III demo proves note-level summarization performance.

### MIMIC-IV-Ext-BHC

| Item | Detail |
| --- | --- |
| Resource | PhysioNet MIMIC-IV-Ext-BHC v1.2.0 |
| Task | Hospital course summarization |
| Access | Credentialed PhysioNet access |
| Repo role | Future Layer D real EHR note-level benchmark |

Why suitable:

- It is specifically designed for hospital course summarization.
- It is the strongest future match for real clinical note summarization evaluation.
- It supports more defensible real EHR note-level claims once access and governance are in place.

Limitations:

- It is not available for unrestricted local demo.
- It must not be committed.
- It must not be sent to external LLMs without approved governance.

Allowed claim after access:

> MIMIC-IV-Ext-BHC supports Layer D real EHR note-level hospital course summarization evaluation under credentialed access.

Current Week 1 claim:

> MIMIC-IV-Ext-BHC is the preferred future real EHR note-level benchmark.

### MIMIC-IV-Note

| Item | Detail |
| --- | --- |
| Resource | PhysioNet MIMIC-IV-Note v2.2 |
| Task | Deidentified free-text clinical notes |
| Access | Credentialed PhysioNet access |
| Repo role | Future Layer D real note corpus and fallback benchmark source |

Why suitable:

- It contains deidentified clinical notes.
- It can support future note-level analysis and derived summarization tasks.
- It is closer to the production medical record setting than open proxy datasets.

Limitations:

- It requires credentialed access.
- Reference target extraction must be carefully designed if using section-derived summaries.
- It should remain local-only.

Allowed claim after access:

> MIMIC-IV-Note supports future governed real clinical note evaluation.

Current Week 1 claim:

> MIMIC-IV-Note remains future work pending credentialed access.

## Datasets To Deprioritize Or Use Only As Context

| Dataset family | Reason |
| --- | --- |
| Consumer health question summarization, such as MeQSum/CHQ | Useful for general medical summarization, but not medical record summarization |
| Radiology-only summarization | Useful for imaging report tasks, but outside current record-summary MVP |
| Biomedical literature summarization, such as MS2/PubMed paper summaries | Useful for evidence summarization, not patient record summarization |
| General news/dialogue summarization datasets | Useful for model debugging only, not clinical claims |

## Evaluation Metrics Mapping

| Output type | Metrics | Interpretation |
| --- | --- | --- |
| MultiClinSum generated summary | ROUGE-1, ROUGE-2, ROUGE-L, optional BERTScore, latency, input/output length | Proxy source-to-summary model comparison |
| MTS-Dialog generated section | ROUGE/BERTScore, section-header accuracy if implemented | Dialogue-to-note-section proxy comparison |
| ACI-BENCH generated note | ROUGE/BERTScore, section coverage if implemented | Full-visit dialogue-to-note proxy comparison |
| mtsamples normalization output | difficulty score, needs-review count, normalization method, fallback warnings | Input robustness and product safety |
| MIMIC-IV-Ext-BHC future output | ROUGE/BERTScore plus human evaluation and citation/factuality checks | Real EHR note-level benchmark after access |
| Human review | factual correctness, completeness, conciseness, readability, citation usefulness, hallucination risk | Safety/usefulness perception |

## Data Governance Rules

- Do not commit raw external datasets.
- Do not commit credentialed MIMIC files.
- Do not send credentialed or identifiable clinical text to Gemini or any external provider without explicit governance.
- Keep generated outputs under `outputs/evaluation/` and label them as proxy unless they are from governed Layer D data.
- Every report must say what the result means and what it does not mean.

## Practical Week 1 Plan

1. Import MultiClinSum with `--limit 20`.
2. Run deterministic baseline with `--limit 5`.
3. Run Pegasus/BART dry-run readiness with `--dry-run`.
4. Add MTS-Dialog import when the local CSVs exist.
5. Run mtsamples normalization stress test on a small subset.
6. Record all outputs in `outputs/evaluation/`.
7. Keep MIMIC-IV-Ext-BHC and MIMIC-IV-Note as pending Layer D.

## Resource Links

| Resource | Link |
| --- | --- |
| BioASQ MultiClinSum description | https://participants-area.bioasq.org/general_information/MultiClinSum/ |
| MultiClinSum Zenodo release | https://zenodo.org/records/17341582 |
| MTS-Dialog repository | https://github.com/abachaa/MTS-Dialog |
| MEDIQA-Chat 2023 repository | https://github.com/abachaa/MEDIQA-Chat-2023 |
| ACI-BENCH repository | https://github.com/wyim/aci-bench |
| ACI-BENCH paper | https://www.nature.com/articles/s41597-023-02487-3 |
| MIMIC-IV-Ext-BHC | https://physionet.org/content/labelled-notes-hospital-course/ |
| MIMIC-IV-Note | https://physionet.org/content/mimic-iv-note/ |
| MIMIC-III demo | https://physionet.org/content/mimiciii-demo/1.4/ |
| MTSamples source site | https://mtsamples.com/ |

## Mentor-Ready Summary

The strongest current data path is MultiClinSum for Layer C.1 proxy summarization, MTS-Dialog for Layer C.2 dialogue-to-note auxiliary evaluation, and mtsamples_clean for messy input normalization. ACI-BENCH is a useful optional extension. MIMIC-IV-Ext-BHC and MIMIC-IV-Note remain the correct future real EHR note-level benchmarks, but they require credentialed access and cannot be replaced by open proxy datasets.
