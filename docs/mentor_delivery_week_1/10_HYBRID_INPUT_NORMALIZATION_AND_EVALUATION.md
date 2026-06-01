# 10 - Hybrid Input Normalization And Evaluation

## Purpose

This note explains how messy clinical text is normalized for safer downstream summarization experiments. The goal is product safety and input consistency, not diagnosis, treatment recommendation, or autonomous clinical decision-making.

## Current Rule-Based Chunking Limitation

The current rule-based normalizer works well when clinical headings are recognizable. It is weaker when the source text has:

- no headings;
- nonstandard headings;
- dense paragraph-style transcription;
- mixed abbreviations;
- inconsistent line breaks;
- long narrative sections that contain several clinical topics.

For those cases, rule-based output should remain visible but may require review.

## Difficult-Case Detection

`document_difficulty.py` scores whether rule-based section detection is likely to be weak. Signals include missing recognized headings, dense text, unknown headings, irregular formatting, and abbreviation-heavy content.

The score is not a medical classifier. It only answers whether optional LLM-assisted normalization may be useful.

## Gemini-Assisted Normalization Flow

Gemini normalization is disabled by default. It is only attempted when all conditions are true:

1. The caller passes `--allow-llm-normalization`.
2. The difficult-case detector marks the note as difficult.
3. The max-call budget from `--max-llm-cases` has not been reached.
4. Gemini governance settings and credentials are available, or a test fake client is injected.

If Gemini is unavailable or returns invalid output, the importer falls back to rule-based normalization and records a warning.

## Source-Of-Truth Policy

Raw text remains the source of truth. The normalized output is an organizational layer over the raw text, not a new clinical record.

The LLM must not:

- add clinical facts;
- infer missing diagnoses;
- infer missing medications;
- infer normal findings from absent data;
- rewrite uncertainty into certainty;
- produce unsupported clinical claims.

Every normalized section must include `source_text` copied from the original input. If returned `source_text` is not grounded in the raw input, the output is rejected and rule-based fallback is used.

## Output Fields

The mtsamples normalization importer records:

| Field | Meaning |
| --- | --- |
| `normalization_method` | `rule_based`, `llm`, or `fallback` |
| `difficulty_score` | Conservative difficulty score from 0.0 to 1.0 |
| `difficulty_reasons` | Reasons the note may need stronger normalization |
| `needs_review_count` | Number of normalized sections marked for review |
| `llm_attempted` | Whether Gemini normalization was attempted |
| `llm_failed` | Warning text if LLM normalization failed |
| `normalization_warnings` | All warnings from fallback/cap handling |

## Fallback Path

Fallback is a feature, not a failure. If Gemini is not configured, unavailable, over budget, or returns ungrounded JSON, the importer:

1. keeps the raw text;
2. uses rule-based sections;
3. marks review needs;
4. records warning metadata;
5. continues processing without blocking local tests.

## Why This Helps Messy Inputs

Medical transcription-like data can be useful for stress testing ingestion and section normalization even when it is not a primary summarization benchmark. The hybrid path helps identify notes that need clinician or reviewer attention before they are used in summarization, citation, or evaluation workflows.

## Why This Is Product Safety, Not Diagnosis

The normalization layer organizes input text into source-backed sections. It does not diagnose, recommend treatment, prescribe, approve discharge, or write back to an EMR. It reduces downstream ambiguity while keeping the original text visible as the authoritative source.

## Evaluation Role

Normalization quality should be evaluated separately from summarization quality:

| Evaluation question | Dataset/source |
| --- | --- |
| Can the workflow run end to end? | Mock/demo data |
| Can the normalizer handle messy input? | mtsamples_clean |
| Can summarizers match references? | MultiClinSum, MTS-Dialog, ACI-BENCH |
| Can the system claim real EHR performance? | Only future credentialed MIMIC-IV-Ext-BHC/MIMIC-IV-Note |
