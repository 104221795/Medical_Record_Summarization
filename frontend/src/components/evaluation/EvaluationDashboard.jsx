import Card from "../common/Card.jsx";
import MetricCard from "../common/MetricCard.jsx";
import PageHeader from "../common/PageHeader.jsx";
import {
  bestByRougeL,
  FailurePatternChart,
  formatScore,
  measuredRows,
  MetricComparisonChart,
  PredictionAvailabilityPanel,
  providerLabel,
  RecordsEvaluatedChart,
} from "./BenchmarkVisuals.jsx";
import BenchmarkFlowTabs from "./BenchmarkFlowTabs.jsx";
import ModelComparisonTable from "./ModelComparisonTable.jsx";
import { ClinicalMetricPanel, PerRecordFailureDashboard, UseCaseRecommendationPanel } from "./ClinicalEvaluationPanels.jsx";

export default function EvaluationDashboard() {
  return (
    <BenchmarkFlowTabs loadingLabel="Loading model quality overview...">
      {({ data, reload, flowMeta }) => <EvaluationDashboardContent data={data} reload={reload} flowMeta={flowMeta} />}
    </BenchmarkFlowTabs>
  );
}

function EvaluationDashboardContent({ data, reload, flowMeta }) {
  const rows = data?.models || [];
  const officialRows = measuredRows(rows);
  const best = bestByRougeL(officialRows);
  const bestBertScore = officialRows.reduce(
    (bestRow, row) => (Number(row.bertscore_f1 || 0) > Number(bestRow?.bertscore_f1 || 0) ? row : bestRow),
    null,
  );
  const bertscoreStatus = officialRows.find((row) => row.bertscore_status)?.bertscore_status || "not requested";
  const pegasusPubMed = rows.find((row) => row.model_provider?.includes("pegasus_pubmed"));
  const gemini = rows.find((row) => row.model_provider === "gemini");
  const pubmedFile = data?.prediction_file_availability?.["pegasus_pubmed_predictions.jsonl"];

  return (
    <div className="stack admin-analytics-page evaluation-overview-page">
      <PageHeader
        eyebrow="Operational model quality"
        title={`Evaluation Overview - ${flowMeta.title}`}
        description={flowMeta.description}
        actions={<button className="btn secondary" onClick={reload}>Refresh</button>}
      />
      <div className="metric-grid">
        <MetricCard label="Best official model" value={best ? providerLabel(best.model_provider) : data?.best_model_by_rougeL || "not available"} detail="By ROUGE-L" />
        <MetricCard label="Best ROUGE-L" value={formatScore(best?.rougeL)} />
        <MetricCard
          label="Best BERTScore F1"
          value={formatScore(bestBertScore?.bertscore_f1)}
          detail={bestBertScore?.bertscore_f1 ? providerLabel(bestBertScore.model_provider) : `BERTScore ${bertscoreStatus}`}
        />
        <MetricCard label="Pegasus PubMed" value={pegasusPubMed ? `${pegasusPubMed.completed_count}/${pegasusPubMed.record_count}` : "not available"} detail={pegasusPubMed?.status || "benchmark row missing"} />
        <MetricCard label="Official models" value={officialRows.length} detail="Measured rows only" />
      </div>
      <div className="grid-two">
        <MetricComparisonChart rows={officialRows} title="Official ROUGE Leaderboard" />
        <RecordsEvaluatedChart rows={officialRows} />
      </div>
      <ClinicalMetricPanel rows={officialRows} summary={data?.clinical_metric_summary} />
      <UseCaseRecommendationPanel rows={officialRows} />
      <div className="grid-two">
        <Card title="Provider Domain Fit">
          <div className="status-grid">
            <div><strong>BART</strong><p>General summarization baseline, useful for controlled comparison.</p></div>
            <div><strong>Pegasus PubMed</strong><p>Medical/scientific fit. Preferred Pegasus row when completed and cached.</p></div>
            <div><strong>Deterministic</strong><p>Fast extractive baseline for smoke checks and regression stability.</p></div>
            <div><strong>Gemini</strong><p>External API provider. Show only as official if measured under governance and token limits.</p></div>
          </div>
        </Card>
        <Card title="Latest Run Summary">
          <p>Selected output: <code>{data?.selected_output_dir || data?.output_dir || "not available"}</code></p>
          <p>Freshness: <strong>{data?.data_freshness_timestamp || "not available"}</strong></p>
          <p>Report: <code>{data?.artifact_paths?.evaluation_report || data?.report_path || "not available"}</code></p>
          {pubmedFile?.exists ? (
            <p className="muted">Pegasus PubMed prediction file found with {pubmedFile.record_count} records.</p>
          ) : (
            <p className="warning-line">Pegasus PubMed prediction file is missing from the selected benchmark output.</p>
          )}
          {gemini ? <p className="warning-line">Gemini status: {gemini.status}. Treat token-limited Gemini rows separately unless completed records are present.</p> : <p className="muted">Gemini has no official measured row in the current benchmark output.</p>}
        </Card>
      </div>
      <div className="grid-two">
        <FailurePatternChart summary={data?.failure_analysis_summary} />
        <PredictionAvailabilityPanel availability={data?.prediction_file_availability} />
      </div>
      <PerRecordFailureDashboard examples={data?.per_record_failure_examples} />
      <ModelComparisonTable rows={rows} bestModel={best?.model_provider || data?.best_model_by_rougeL} />
      <Card title="Proxy Evaluation Notice">
        <p className="warning-line">{data?.proxy_warning}</p>
      </Card>
    </div>
  );
}
