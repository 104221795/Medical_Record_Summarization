import Card from "../../components/common/Card.jsx";
import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import MetricCard from "../../components/common/MetricCard.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import Badge from "../../components/common/Badge.jsx";
import {
  bestByRougeL,
  FailurePatternChart,
  formatScore,
  measuredRows,
  MetricComparisonChart,
  ProviderReadinessChart,
  providerLabel,
  RecordsEvaluatedChart,
} from "../../components/evaluation/BenchmarkVisuals.jsx";
import { apiClient } from "../../services/apiClient.js";
import { evaluationApi } from "../../services/evaluationApi.js";
import { useApi } from "../../hooks/useApi.js";

export default function AdminDashboardPage() {
  const { data, loading, error, reload } = useApi(async () => {
    const [usage, quality, safety, status, benchmark] = await Promise.all([
      apiClient("/metrics/usage"),
      apiClient("/metrics/summary-quality"),
      apiClient("/metrics/safety"),
      evaluationApi.status(),
      evaluationApi.benchmarkResults(),
    ]);
    return { usage, quality, safety, status, benchmark };
  }, []);

  if (loading) return <LoadingState label="Loading admin monitor..." />;
  if (error) return <ErrorState error={error} />;
  const models = data?.benchmark?.models || [];
  const officialRows = measuredRows(models);
  const best = bestByRougeL(officialRows);

  return (
    <div className="stack admin-monitor-page">
      <PageHeader
        eyebrow="Admin monitor"
        title="System Monitoring"
        description="Operational summary for summaries, approvals, audit readiness, providers, dataset readiness, and latest proxy benchmark status."
        actions={<button className="btn secondary" onClick={reload}>Refresh</button>}
      />
      <div className="metric-grid">
        <MetricCard label="Summaries generated" value={data?.quality?.total_summaries} detail="Persisted drafts" />
        <MetricCard label="Approvals" value={data?.quality?.approved_count} detail="Doctor approved" />
        <MetricCard label="Rejections" value={data?.quality?.rejected_count} detail="Doctor rejected" />
        <MetricCard label="Benchmark-ready records" value="25,902" detail="Governed MultiClinSum set" />
      </div>
      <div className="grid-two">
        <MetricComparisonChart rows={officialRows} title="Latest Benchmark Quality" />
        <ProviderReadinessChart providers={data?.status?.provider_readiness} />
      </div>
      <div className="grid-two">
        <Card title="Dataset Readiness Chart">
          <div className="readiness-chart">
            <DatasetRow label="Governed MultiClinSum" value={1} suffix="25,902 benchmark-ready records" tone="success" />
            <DatasetRow label="Synthea / SyntheticMass" value={.76} suffix="ingestion validation" tone="info" />
            <DatasetRow label="MTS-Dialog / MEDIQA-Sum" value={.42} suffix="planned proxy datasets" tone="warning" />
            <DatasetRow label="MIMIC-IV governed access" value={.18} suffix="pending credentialed approval" tone="danger" />
          </div>
        </Card>
        <Card title="Latest Benchmark Status" actions={best && <Badge tone="success">Best {providerLabel(best.model_provider)}</Badge>}>
          <p>Best model: <strong>{best ? providerLabel(best.model_provider) : data?.benchmark?.best_model_by_rougeL || "not available"}</strong></p>
          <p>Best ROUGE-L: <strong>{formatScore(best?.rougeL)}</strong></p>
          <p>Selected output: <code>{data?.benchmark?.selected_output_dir || data?.benchmark?.output_dir || "not available"}</code></p>
          <p>Freshness: <strong>{data?.benchmark?.data_freshness_timestamp || "not available"}</strong></p>
          <p className="warning-line">{data?.benchmark?.proxy_warning}</p>
        </Card>
      </div>
      <div className="grid-two">
        <RecordsEvaluatedChart rows={officialRows} />
        <FailurePatternChart summary={data?.benchmark?.failure_analysis_summary} />
      </div>
    </div>
  );
}

function DatasetRow({ label, value, suffix, tone = "info" }) {
  const percent = Math.max(4, Math.min(100, value * 100));
  return (
    <div className="readiness-row">
      <div><strong>{label}</strong><span>{suffix}</span></div>
      <div className="readiness-track"><span className={tone} style={{ width: `${percent}%` }} /></div>
      <Badge tone={tone}>{Math.round(value * 100)}%</Badge>
    </div>
  );
}
