# 10 - Hybrid Input Normalization And Evaluation

## Purpose

This document explains how the MVP handles messy clinical text before summarization. It is focused on product safety and evaluation validity.

The goal is not to diagnose, recommend treatment, prescribe, approve discharge, or create new clinical facts. The goal is to turn messy input into source-backed sections that downstream summarization and citation workflows can inspect more safely.

## Why Input Normalization Matters

Medical record summarization usually receives imperfect input:

- discharge summaries with inconsistent section headings;
- progress notes with dense narrative paragraphs;
- medical transcription samples with irregular formatting;
- doctor-patient dialogue that must become a note section;
- structured records that need to be displayed as evidence;
- OCR/ASR-like text with missing punctuation or speaker noise.

If the system treats all input as clean, it may produce summaries that look fluent but hide weak evidence, missing source spans, or formatting ambiguity. Normalization makes those risks visible before model evaluation.

## Normalization Is A Separate Evaluation Track

Normalization quality is not the same as summarization quality.

| Question | Belongs to | Example dataset |
| --- | --- | --- |
| Can the product workflow run? | Functional validation | Mock/demo data |
| Can the system map structured EHR records? | Structured EHR validation | MIMIC-III demo |
| Can the system organize messy note text? | Normalization stress test | mtsamples_clean / MTSamples-derived text |
| Can a summarizer match a reference summary? | Proxy summarization evaluation | MultiClinSum |
| Can a dialogue become a note section? | Dialogue-to-note proxy evaluation | MTS-Dialog |
| Can we claim real EHR note performance? | Future real benchmark | MIMIC-IV-Ext-BHC / MIMIC-IV-Note |

Keeping these separate prevents the common mistake of using messy transcription data as if it were a supervised summarization benchmark.

## Current Code Path

Current implementation components:

| Component | Path | Role |
| --- | --- | --- |
| Difficulty detector | `backend/app/services/document_difficulty.py` | Scores whether rule-based sectioning may be weak |
| Normalizer | `backend/app/services/input_normalization.py` | Produces source-backed normalized sections |
| mtsamples importer | `backend/app/evaluation/datasets/mtsamples_importer.py` | Imports messy transcription data and records normalization metadata |
| Tests | `backend/tests/test_mtsamples_importer.py` | Verifies rule-based, fake LLM, and fallback paths |

## Rule-Based Normalization

Rule-based normalization is the default. It is deterministic, local, cheap, and safe for tests.

It works best when text contains recognizable headings such as:

- history;
- medications;
- allergies;
- vitals;
- labs;
- imaging;
- assessment;
- plan;
- procedure.

It is weaker when:

- headings are missing;
- headings are nonstandard;
- the note is one long paragraph;
- multiple clinical topics are mixed in one section;
- abbreviation density is high;
- punctuation is sparse;
- the text appears to mix language patterns or formatting conventions.

Rule-based output must remain visible even when it is weak. It should not be silently replaced by an LLM output.

## Difficult-Case Detection

The difficult-case detector is a routing tool, not a medical classifier.

It looks for signals such as:

| Signal | Meaning |
| --- | --- |
| `no_recognized_clinical_headings` | Section parser could not identify familiar headings |
| `low_section_detection_confidence` | Very few known headings for a long note |
| `too_much_text_classified_as_narrative` | Large narrative span before usable headings |
| `unknown_or_nonstandard_headings` | Possible headings that are not in the known heading map |
| `long_dense_text` | Weak punctuation and long text |
| `irregular_formatting_or_dense_lines` | Dense lines or unusual layout |
| `mixed_language_or_abbreviation_heavy` | Many abbreviations or mixed language signal |

The detector outputs:

```json
{
  "difficulty_score": 0.45,
  "reasons": ["no_recognized_clinical_headings"],
  "should_use_llm_normalization": true
}
```

The threshold is conservative. It should identify cases where optional LLM assistance may help organize text, not cases where medical interpretation is needed.

## Controlled Gemini-Assisted Normalization

Gemini-assisted normalization is optional and disabled by default.

It is only allowed when all of these are true:

1. The CLI passes `--allow-llm-normalization`.
2. The note is difficult according to `document_difficulty.py`.
3. The total LLM calls stay within `--max-llm-cases`.
4. Gemini is configured with explicit governance flags, or tests inject a fake client.
5. The LLM output passes strict JSON validation.
6. Every returned `source_text` is grounded in the original raw text.

Command:

```powershell
python -m backend.app.evaluation.datasets.mtsamples_importer `
  --limit 20 `
  --allow-llm-normalization `
  --max-llm-cases 5
```

This command should be used only for mock/de-identified or otherwise approved data.

## Source-Of-Truth Policy

Raw input text remains the source of truth.

The normalized record is only an organizational layer. It helps the product display sections and route review, but it does not replace the original text.

The LLM must not:

- add symptoms, diagnoses, medications, allergies, lab values, procedures, or plans;
- infer "normal" when the source is silent;
- infer trend from a single value;
- turn uncertainty into certainty;
- rewrite patient statements as verified clinician findings;
- remove conflicting or unsupported evidence;
- create facts that do not appear in the source.

Every normalized section must include `source_text`. That `source_text` must be copied from the raw input. If the normalizer cannot verify grounding, it rejects the LLM output and falls back safely.

## Output Schema

The importer output includes top-level normalization metadata:

```json
{
  "record_id": "sample_001",
  "source_dataset": "BIOMEDNLP/mtsamples_clean",
  "validation_layer": "Normalization stress test",
  "raw_text": "...",
  "normalization_method": "rule_based",
  "difficulty_score": 0.32,
  "difficulty_reasons": ["no_recognized_clinical_headings"],
  "needs_review_count": 1,
  "llm_attempted": false,
  "llm_failed": null,
  "normalization_warnings": []
}
```

The nested `normalization` object preserves section-level detail:

```json
{
  "document_type": "medical_transcription",
  "language": "en",
  "normalization_method": "rule_based",
  "sections": [
    {
      "raw_section_name": "Narrative",
      "normalized_section_type": "narrative",
      "source_text": "...",
      "confidence": 0.55,
      "needs_review": true
    }
  ],
  "difficulty": {
    "difficulty_score": 0.32,
    "reasons": ["no_recognized_clinical_headings"],
    "should_use_llm_normalization": false
  },
  "warnings": []
}
```

## Normalization Method Values

| Method | Meaning | Interpretation |
| --- | --- | --- |
| `rule_based` | Local deterministic sectioning | Default and safe |
| `llm` | Gemini returned valid grounded JSON | Useful for difficult cases, still requires review |
| `fallback` | LLM was attempted but failed or was ungrounded | Safe fallback, keep warning visible |

## Fallback Policy

Fallback is expected and safe.

If Gemini is unavailable, blocked by governance settings, over budget, or returns invalid/ungrounded JSON, the system:

1. keeps raw text unchanged;
2. uses rule-based sections;
3. marks weak sections for review;
4. records `llm_attempted`;
5. records `llm_failed` and warnings;
6. continues processing.

The importer must not fail a local smoke test just because Gemini is unavailable.

## Evaluation Plan For Normalization

Use three levels:

| Level | Metric/check | Target |
| --- | --- | --- |
| Basic smoke | Import completes and writes JSONL | Pass |
| Difficulty routing | Difficult notes have higher `difficulty_score` and reasons | Visible |
| Safety fallback | LLM unavailable path falls back without data loss | Pass |

Optional human review criteria:

| Criterion | Reviewer question |
| --- | --- |
| Section correctness | Did the normalized section label match the source text? |
| Grounding | Is every section backed by raw source text? |
| Missing section risk | Did the normalizer lose important content? |
| Over-inference risk | Did any normalized section add a fact not present in the source? |
| Review usefulness | Did `needs_review` flag the right hard cases? |

## Why mtsamples_clean Fits This Track

MTSamples-style text is not a clean supervised summarization benchmark, but it is valuable for normalization because:

- it includes many medical specialties;
- report formats vary substantially;
- headings can be inconsistent;
- transcriptions are often narrative-heavy;
- the text resembles the messy input a product might see before robust integration.

Because the source quality and reference structure are not designed for the main summarization task, it belongs in the normalization track.

## Why This Is Product Safety

Normalization supports safety by making uncertainty visible:

- difficult notes are flagged;
- weak sectioning is recorded;
- fallback warnings are preserved;
- raw text remains available;
- generated summaries can later cite source text rather than hidden LLM-inferred sections.

This is documentation support, not clinical decision automation.

## Data Handling Rules

- Use mock/de-identified text by default.
- Do not send credentialed MIMIC text to external LLMs.
- Do not commit raw imported transcription datasets.
- Keep processed normalization outputs local unless they contain only safe synthetic/demo text.
- If Gemini is enabled, document the data governance basis.

## Recommended Week 1 Commands

Rule-based default:

```powershell
python -m backend.app.evaluation.datasets.mtsamples_importer `
  --split train `
  --limit 20 `
  --output data/processed/mtsamples_clean/mtsamples_clean_train.jsonl
```

Controlled LLM-assisted path:

```powershell
python -m backend.app.evaluation.datasets.mtsamples_importer `
  --split train `
  --limit 20 `
  --output data/processed/mtsamples_clean/mtsamples_clean_train.jsonl `
  --allow-llm-normalization `
  --max-llm-cases 5
```

Expected report fields:

```text
normalization_method
difficulty_score
difficulty_reasons
needs_review_count
llm_attempted
llm_failed
normalization_warnings
```

## Mentor-Ready Summary

The input normalization layer exists because medical record summarization quality depends on source handling, not only model generation. Rule-based normalization remains the default. Gemini-assisted normalization is controlled, difficult-case-only, capped, and source-grounded. This improves product safety for messy clinical text without turning the system into a diagnostic or treatment recommendation tool.
