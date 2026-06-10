import { Link } from "react-router-dom";

import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
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
import BenchmarkFlowTabs from "./BenchmarkFlowTabs.jsx";
import ModelComparisonTable from "./ModelComparisonTable.jsx";
import { ClinicalMetricPanel, PerRecordFailureDashboard, UseCaseRecommendationPanel } from "./ClinicalEvaluationPanels.jsx";

export default function BenchmarkResults() {
  return (
    <BenchmarkFlowTabs loadingLabel="Loading benchmark artifacts...">
      {({ data, reload, flowMeta }) => <BenchmarkResultsContent data={data} reload={reload} flowMeta={flowMeta} />}
    </BenchmarkFlowTabs>
  );
}

function BenchmarkResultsContent({ data, reload, flowMeta }) {
  const rows = data?.models || [];
  const pubmed = rows.find((row) => row.model_provider?.includes("pegasus_pubmed"));
  const pubmedFile = data?.prediction_file_availability?.["pegasus_pubmed_predictions.jsonl"];
  const bestBertScore = rows.reduce(
    (bestRow, row) => (Number(row.bertscore_f1 || 0) > Number(bestRow?.bertscore_f1 || 0) ? row : bestRow),
    null,
  );
  const bertscoreStatus = rows.find((row) => row.bertscore_status)?.bertscore_status || "not requested";
  return (
    <div className="stack benchmark-results-page admin-analytics-page">
      <PageHeader
        eyebrow="Experiment artifacts"
        title={`Benchmark Results - ${flowMeta.title}`}
        description={flowMeta.description}
        actions={(
          <div className="page-header-actions">
            <button className="btn secondary" onClick={reload} type="button">Refresh</button>
            <Link to="/admin/evaluation/flow-comparison"><button className="btn" type="button">Compare 3 Flows</button></Link>
          </div>
        )}
      />
      <div className="metric-grid">
        <MetricCard label="Selected output" value={data?.selected_output_dir ? "available" : "missing"} detail={data?.selected_output_dir || data?.output_dir || "not available"} />
        <MetricCard label="Report" value={data?.report_exists ? "available" : "missing"} detail={data?.report_path || "not available"} />
        <MetricCard label="Pegasus PubMed" value={pubmed ? `${pubmed.completed_count}/${pubmed.record_count}` : "missing"} detail={pubmed?.model_name || "prediction row not found"} />
        <MetricCard label="PubMed ROUGE-L" value={formatScore(pubmed?.rougeL)} detail={pubmed?.stage_name || "stage not available"} />
        <MetricCard
          label="Best BERTScore F1"
          value={formatScore(bestBertScore?.bertscore_f1)}
          detail={bestBertScore?.bertscore_f1 ? providerLabel(bestBertScore.model_provider) : `BERTScore ${bertscoreStatus}`}
        />
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
      <ClinicalMetricPanel rows={rows} summary={data?.clinical_metric_summary} />
      <UseCaseRecommendationPanel rows={rows} />
      <div className="grid-two">
        <FailurePatternChart summary={data?.failure_analysis_summary} />
        <PredictionAvailabilityPanel availability={data?.prediction_file_availability} />
      </div>
      <PerRecordFailureDashboard examples={data?.per_record_failure_examples} />
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
