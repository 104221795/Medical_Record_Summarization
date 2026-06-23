# Portable Evaluation Artifacts

This is the repository-relative staging location for prepared benchmark
snapshots used by the Admin evaluation pages.

Configure a different location with:

```env
RAG_EVALUATION_ARTIFACT_ROOT=<path>
```

For the local Docker Compose demo, copy the completed benchmark folder and
pointer file here:

```text
artifacts/evaluation/
  latest_rag_best_models.json
  rag_best_models_benchmark_50_gated/
  rag_best_models_benchmark_50_no_gate/
    model_comparison.csv
    per_record_metrics.csv
    ...
  historical_flow_metrics/
    flow_1_raw_per_record_metrics.csv
    flow_1_5_context_per_record_metrics.csv
    flow_2_rag_per_record_metrics.csv
  week5_analysis/
    WEEK5_P1_P2_ANALYSIS.md
    diversity_strata_metrics.csv
    provider_failure_matrix.csv
    metric_correlations.csv
    retrieval_gate_case_analysis.csv
    retrieval_threshold_sensitivity.csv
    human_review_cases.jsonl
    human_review_scores.csv
```

Use a relative `selected_output_dir` in the pointer for portability:

```json
{
  "selected_output_dir": "rag_best_models_benchmark_50_no_gate"
}
```

Benchmark files are intentionally ignored by Git because they can be large and
may contain generated clinical text. Package and transfer only approved,
de-identified proxy-evaluation artifacts.

Regenerate only the post-hoc Week 5 analysis (without rerunning generation):

```powershell
python -m scripts.analyze_week5_evaluation
```

The gated and no-gate snapshots must remain separate. The former demonstrates
the evidence-policy boundary; the latter provides 50/50 outputs for all five
providers. Human-review scores must remain blank until real reviewers complete
the documented protocol.

The three `historical_flow_metrics` files are the minimum portable inputs for
the controlled Flow 1/1.5/2/2.1 comparison. The analyzer prefers these files
and uses the legacy `D:\clin_summ_outputs` paths only as a fallback.
