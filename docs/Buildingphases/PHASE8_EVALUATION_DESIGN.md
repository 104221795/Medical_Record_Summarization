# Phase 8 Evaluation Design

This MVP uses a three-layer evaluation system so demo readiness is not confused
with real clinical benchmark performance.

## Layer A: Functional Validation

Functional validation runs now with mock/de-identified demo data. It checks the
end-to-end product workflow: demo data, patient lookup, document access, draft
summary generation, claims, citations or unsupported flags, citation source
viewing, HITL review actions, audit logs, and metrics.

Run it through:

```http
POST /api/v1/evaluation/functional/run
```

or open:

```text
http://127.0.0.1:8080/evaluation-demo
```

Functional validation is a system workflow smoke test. It must not be reported
as real EHR benchmark accuracy.

## Layer B: Real EHR Benchmark Evaluation

The benchmark layer is prepared but pending until credentialed, de-identified
EHR benchmark data is available. The MVP expects the processed benchmark file at:

```text
data/processed/ehr_benchmark/test.jsonl
```

Expected JSONL schema:

```json
{
  "note_id": "note_001",
  "patient_id": "patient_001",
  "encounter_id": "enc_001",
  "source_note": "...",
  "reference_summary": "...",
  "dataset": "mimic_iv_note|mimic_iv_ext_bhc",
  "split": "test"
}
```

Use MIMIC-IV-Note or MIMIC-IV-Ext-BHC only after credentialed access and local
data governance approval. Do not commit raw clinical data or processed benchmark
files containing real patient text.

Check benchmark readiness through:

```http
GET /api/v1/evaluation/benchmark/status
```

If the file is missing, the API returns `pending_dataset` and no fake metrics.

## Layer C: Human Evaluation

Human evaluation can run now on generated demo/mock summaries. It collects
reviewer scores for factual correctness, completeness, conciseness, readability,
citation usefulness, hallucination risk, and comments.

Submit through:

```http
POST /api/v1/evaluation/human
```

Summary aggregation is available at:

```http
GET /api/v1/evaluation/human/summary
```

Human evaluation on mock data should be described as demo usability/safety
review, not real clinical validation.

## Evaluation & Demo Control Center

Open:

```text
http://127.0.0.1:8080/evaluation-demo
```

The page summarizes:

- Golden path readiness
- Model provider status for deterministic, BART, Pegasus, and Gemini
- Citation and safety metrics
- HITL review state
- Monitoring summary
- Three-layer evaluation status
- Human evaluation form and score summary
- Final demo checklist

The page does not expose raw PHI and does not fabricate benchmark metrics.

## Later Benchmark Workflow

1. Obtain credentialed access to MIMIC-IV-Note or MIMIC-IV-Ext-BHC.
2. Convert the dataset into `data/processed/ehr_benchmark/test.jsonl`.
3. Verify `GET /api/v1/evaluation/benchmark/status` reports a valid schema.
4. Run the existing baseline/evaluation scripts against the processed file.
5. Store comparison output under `results/ehr_benchmark/model_comparison.csv`.
6. Document real benchmark results separately from functional demo validation.
