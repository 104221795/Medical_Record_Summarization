# 09 - Dataset Strategy And Research Evaluation

## Purpose

This note makes the Week 1 dataset strategy explicit so the project does not overclaim. The project evaluates what can be validly evaluated at the current access level, while explicitly reserving real EHR note-level claims for future credentialed datasets.

## Dataset Role Table

| Evidence layer | Dataset/source | Current role | Allowed claim | Not allowed claim |
| --- | --- | --- | --- | --- |
| A | Mock/de-identified demo data | Functional workflow validation | The product flow can run end to end with draft summaries, citations, review status, and audit events | The model is clinically performant |
| B | MIMIC-III demo structured data | Structured EHR mapping validation | The system can map structured patients, encounters, diagnoses, labs, and medications | The system has solved note-level summarization |
| C.1 | MultiClinSum | Primary open clinical summarization benchmark | Baseline summarizers can be compared on an open proxy clinical summarization task | MultiClinSum is a real EHR benchmark |
| C.2 | MTS-Dialog | Auxiliary dialogue-to-note proxy evaluation | The system can evaluate dialogue-to-note-section behavior as a related proxy | MTS-Dialog proves real EHR performance |
| C.3 | ACI-BENCH | Optional full-visit dialogue-to-note proxy evaluation | Full-visit dialogue-to-note behavior can be evaluated if the dataset is available | ACI-BENCH replaces credentialed EHR notes |
| Normalization | BIOMEDNLP/mtsamples_clean | Messy transcription normalization stress test | The input normalizer can handle difficult medical transcription-like text | mtsamples_clean is the main supervised summarization benchmark |
| D | MIMIC-IV-Ext-BHC / MIMIC-IV-Note | Future real EHR note-level benchmark | Real EHR note-level claims can be made after credentialed access and governed processing | Available in Week 1 |
| E | Human evaluation | Usefulness and safety perception review | Reviewers can score factuality, completeness, readability, citation usefulness, and perceived risk | Automatic clinical validation |

## Why MultiClinSum Is Primary

MultiClinSum is the main Layer C.1 dataset because it provides paired clinical source/reference summarization examples that can drive automatic metrics such as ROUGE and optional BERTScore. It is stronger for Week 1 proxy summarization than mock data, structured EHR demo rows, or noisy transcription-only corpora.

The allowed claim is narrow: MultiClinSum supports open proxy model comparison. It does not support a claim that the system has been benchmarked on real hospital EHR notes.

## Why MTS-Dialog Is Auxiliary

MTS-Dialog is useful because dialogue-to-note generation is clinically relevant, especially for ambient documentation and visit summarization. It remains auxiliary because the source is a dialogue and the target is a note section, not the same task as summarizing a complete EHR note or discharge summary.

Layer C.2 should be reported separately from Layer C.1 so model strengths and weaknesses are not mixed across task types.

## Why mtsamples_clean Is A Normalization Stress Test

mtsamples_clean is valuable because medical transcriptions can be messy: inconsistent headings, long narrative text, abbreviations, and uneven formatting. This makes it a good stress test for section detection and controlled LLM-assisted normalization.

It should not be presented as the main supervised summarization benchmark unless reliable source/reference summary pairs are introduced and validated separately.

## Why MIMIC-BHC Remains Future Work

MIMIC-IV-Ext-BHC and MIMIC-IV-Note are reserved for Layer D because they are credentialed real EHR note-level resources. They require approved access, local-only handling, de-identification discipline, and a governed evaluation protocol. Until then, real EHR benchmark claims remain pending.

## Exact Allowed Claims

| Dataset/source | Exact allowed wording |
| --- | --- |
| Mock/demo data | "Validates local workflow behavior only." |
| MIMIC-III demo | "Validates structured EHR mapping and evidence workflow only." |
| MultiClinSum | "Primary open proxy clinical summarization benchmark for Layer C.1." |
| MTS-Dialog | "Auxiliary dialogue-to-note proxy evaluation for Layer C.2." |
| ACI-BENCH | "Optional full-visit dialogue-to-note proxy evaluation for Layer C.3." |
| mtsamples_clean | "Normalization stress test for messy transcription-like inputs." |
| MIMIC-IV-Ext-BHC / MIMIC-IV-Note | "Future real EHR note-level benchmark pending credentialed access." |

## Evaluation Metrics Mapping

| Component | Role in evaluation |
| --- | --- |
| Pegasus/BART output | Generated summaries evaluated with ROUGE and optional BERTScore |
| Deterministic output | Stable local baseline and test control |
| BERT/BioBERT | Semantic evaluation or future evidence similarity support, not the main generator |
| Gemini | Controlled input normalization and/or governed product LLM provider |
| Human review | Final safety/usefulness layer for factuality, completeness, readability, citation usefulness, and perceived hallucination risk |

## What Current Results Mean

Current smoke results can show that importers, deterministic generation, metric writing, and dry-run readiness work. They do not show clinical deployment readiness or real EHR benchmark performance.
