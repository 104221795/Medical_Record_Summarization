import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import ErrorState from "../common/ErrorState.jsx";
import LoadingState from "../common/LoadingState.jsx";
import MetricCard from "../common/MetricCard.jsx";
import PageHeader from "../common/PageHeader.jsx";
import {
  ArtifactPathPanel,
  BenchmarkFolderPanel,
  FailurePatternChart,
  formatScore,
  MetricComparisonChart,
  PredictionAvailabilityPanel,
  providerLabel,
  RecordsEvaluatedChart,
} from "./BenchmarkVisuals.jsx";
import ModelComparisonTable from "./ModelComparisonTable.jsx";
import { useEvaluationResults } from "../../hooks/useEvaluationResults.js";

export default function BenchmarkResults() {
  const { data, loading, error, reload } = useEvaluationResults();
  if (loading) return <LoadingState label="Loading benchmark artifacts..." />;
  if (error) return <ErrorState error={error} />;
  const rows = data?.models || [];
  const pubmed = rows.find((row) => row.model_provider?.includes("pegasus_pubmed"));
  const pubmedFile = data?.prediction_file_availability?.["pegasus_pubmed_predictions.jsonl"];
  return (
    <div className="stack benchmark-results-page admin-analytics-page">
      <PageHeader
        eyebrow="Experiment artifacts"
        title="Benchmark Results"
        description="Inspect run artifacts, CSV outputs, report locations, and measured model comparison rows."
        actions={<button className="btn secondary" onClick={reload}>Refresh</button>}
      />
      <div className="metric-grid">
        <MetricCard label="Selected output" value={data?.selected_output_dir ? "available" : "missing"} detail={data?.selected_output_dir || data?.output_dir || "not available"} />
        <MetricCard label="Report" value={data?.report_exists ? "available" : "missing"} detail={data?.report_path || "not available"} />
        <MetricCard label="Pegasus PubMed" value={pubmed ? `${pubmed.completed_count}/${pubmed.record_count}` : "missing"} detail={pubmed?.model_name || "prediction row not found"} />
        <MetricCard label="PubMed ROUGE-L" value={formatScore(pubmed?.rougeL)} detail={pubmed?.stage_name || "stage not available"} />
      </div>
      <Card title="Pegasus PubMed 200-Record Run" actions={<Badge tone={pubmed?.status?.includes("completed") ? "success" : "warning"}>{pubmed?.status || "not found"}</Badge>}>
        <p>
          {pubmed
            ? `${providerLabel(pubmed.model_provider)} appears in the current comparison from ${pubmed.model_name}, completed ${pubmed.completed_count}/${pubmed.record_count} records.`
            : "Pegasus PubMed metrics are not present in the selected benchmark output yet."}
        </p>
        <p className={pubmedFile?.exists ? "muted" : "warning-line"}>
          Prediction file: {pubmedFile?.exists ? `${pubmedFile.path} (${pubmedFile.record_count} records)` : "pegasus_pubmed_predictions.jsonl is missing."}
        </p>
        <p className="muted">Required run label: stage_pegasus_pegasus_pubmed_limit200 completed 200/200 records when available.</p>
      </Card>
      <div className="grid-two">
        <MetricComparisonChart rows={rows} title="Benchmark ROUGE Comparison" />
        <RecordsEvaluatedChart rows={rows} />
      </div>
      <div className="grid-two">
        <FailurePatternChart summary={data?.failure_analysis_summary} />
        <PredictionAvailabilityPanel availability={data?.prediction_file_availability} />
      </div>
      <div className="grid-two">
        <BenchmarkFolderPanel folders={data?.discovered_benchmark_folders} />
        <ArtifactPathPanel paths={data?.artifact_paths} />
      </div>
      <ModelComparisonTable rows={rows} bestModel={data?.best_model_by_rougeL} />
      <Card title="Proxy Evaluation Notice">
        <p className="warning-line">{data?.proxy_warning}</p>
      </Card>
    </div>
  );
}
