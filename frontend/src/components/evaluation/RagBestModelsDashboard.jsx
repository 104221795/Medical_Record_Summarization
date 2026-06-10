import { Link } from "react-router-dom";
import { BrainCircuit, DatabaseZap, ShieldCheck, Timer } from "lucide-react";

import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import ErrorState from "../common/ErrorState.jsx";
import LoadingState from "../common/LoadingState.jsx";
import MetricCard from "../common/MetricCard.jsx";
import PageHeader from "../common/PageHeader.jsx";
import { useEvaluationResults } from "../../hooks/useEvaluationResults.js";
import {
  ArtifactPathPanel,
  formatLatency,
  formatScore,
  MetricComparisonChart,
  PredictionAvailabilityPanel,
  providerLabel,
  RecordsEvaluatedChart,
  statusTone,
} from "./BenchmarkVisuals.jsx";
import { ClinicalMetricPanel, PerRecordFailureDashboard, UseCaseRecommendationPanel } from "./ClinicalEvaluationPanels.jsx";
import ModelComparisonTable from "./ModelComparisonTable.jsx";

const TARGET_PROVIDERS = ["bart", "pegasus", "qwen2.5", "llama3.2", "gemini2.5_flash_lite"];

export default function RagBestModelsDashboard() {
  const { data, loading, error, reload } = useEvaluationResults("rag_best_models");

  if (loading) return <LoadingState label="Loading Flow 2.1 benchmark artifacts..." />;
  if (error) return <ErrorState error={error} />;

  const rows = data?.models || [];
  const measured = rows.filter((row) => Number(row.completed_count || 0) > 0);
  const bestRouge = measured.reduce((best, row) => (Number(row.rougeL || 0) > Number(best?.rougeL || 0) ? row : best), null);
  const bestCitation = measured.reduce(
    (best, row) => (Number(row.citation_coverage || 0) > Number(best?.citation_coverage || 0) ? row : best),
    null,
  );
  const fastest = measured.reduce(
    (best, row) => (Number(row.average_latency_ms || Infinity) < Number(best?.average_latency_ms || Infinity) ? row : best),
    null,
  );
  const targetCoverage = TARGET_PROVIDERS.filter((provider) => rows.some((row) => row.model_provider === provider));

  return (
    <div className="stack admin-analytics-page rag-best-page">
      <PageHeader
        eyebrow="Flow 2.1"
        title="RAG Best Models"
        description="MiniLM retrieval, Qdrant evidence, citation-first clinical context, and gateway/local model comparison."
        actions={(
          <div className="page-header-actions">
            <button className="btn secondary" onClick={reload} type="button">Refresh</button>
            <Link to="/admin/evaluation/benchmark"><button className="btn ghost" type="button">Benchmark Results</button></Link>
          </div>
        )}
      />

      <div className="metric-grid">
        <MetricCard label="Selected output" value={data?.selected_output_dir ? "available" : "missing"} detail={data?.selected_output_dir || "not available"} />
        <MetricCard label="Target providers found" value={`${targetCoverage.length}/${TARGET_PROVIDERS.length}`} detail={TARGET_PROVIDERS.map(providerLabel).join(", ")} />
        <MetricCard label="Best ROUGE-L" value={formatScore(bestRouge?.rougeL)} detail={bestRouge ? providerLabel(bestRouge.model_provider) : "not available"} />
        <MetricCard label="Best citation coverage" value={formatScore(bestCitation?.citation_coverage)} detail={bestCitation ? providerLabel(bestCitation.model_provider) : "not available"} />
        <MetricCard label="Fastest provider" value={formatLatency(fastest?.average_latency_ms)} detail={fastest ? providerLabel(fastest.model_provider) : "not available"} />
      </div>

      <Card className="rag-best-flow-card">
        <div className="rag-best-flow">
          <FlowStep icon={DatabaseZap} title="Retrieve" detail="source note -> chunks -> MiniLM -> Qdrant" />
          <FlowStep icon={ShieldCheck} title="Ground" detail="balanced evidence + citation-first clinical facts" />
          <FlowStep icon={BrainCircuit} title="Generate" detail="BART, Pegasus, Qwen, Llama, Gemini" />
          <FlowStep icon={Timer} title="Score" detail="ROUGE, citation quality, safety failures, latency" />
        </div>
      </Card>

      <Card title="Provider Readiness" actions={<Badge tone={targetCoverage.length >= 3 ? "success" : "warning"}>{targetCoverage.length} active</Badge>}>
        <div className="provider-readiness-grid">
          {TARGET_PROVIDERS.map((provider) => {
            const row = rows.find((item) => item.model_provider === provider);
            return (
              <div className="provider-readiness-card" key={provider}>
                <span>{providerLabel(provider)}</span>
                <Badge tone={statusTone(row?.status || "missing")}>{row?.status || "missing"}</Badge>
                <small>{row ? `${row.completed_count}/${row.record_count} records` : "prediction file not found"}</small>
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid-two">
        <MetricComparisonChart rows={rows} title="Flow 2.1 ROUGE Leaderboard" />
        <RecordsEvaluatedChart rows={rows} />
      </div>

      <ClinicalMetricPanel rows={rows} summary={data?.clinical_metric_summary} />
      <UseCaseRecommendationPanel rows={rows} />
      <PerRecordFailureDashboard examples={data?.per_record_failure_examples} />

      <div className="grid-two">
        <PredictionAvailabilityPanel availability={data?.prediction_file_availability} />
        <ArtifactPathPanel paths={data?.artifact_paths} />
      </div>

      <ModelComparisonTable rows={rows} bestModel={data?.best_model_by_rougeL} />
      <Card title="Proxy Evaluation Notice">
        <p className="warning-line">{data?.proxy_warning}</p>
      </Card>
    </div>
  );
}

function FlowStep({ icon: Icon, title, detail }) {
  return (
    <div className="rag-best-flow-step">
      <Icon className="ui-icon" size={20} strokeWidth={2.25} />
      <div>
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
    </div>
  );
}
