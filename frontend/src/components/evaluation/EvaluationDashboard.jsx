import { Link } from "react-router-dom";
import { Activity, ClipboardCheck, FileCheck2, ShieldCheck, Stethoscope } from "lucide-react";

import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import ErrorState from "../common/ErrorState.jsx";
import LoadingState from "../common/LoadingState.jsx";
import MetricCard from "../common/MetricCard.jsx";
import PageHeader from "../common/PageHeader.jsx";
import { useApi } from "../../hooks/useApi.js";
import { evaluationApi } from "../../services/evaluationApi.js";
import { formatScore, ProviderReadinessChart, statusTone } from "./BenchmarkVisuals.jsx";

export default function EvaluationDashboard() {
  const { data, error, loading, reload } = useApi(async () => {
    const [status, benchmarkStatus, humanSummary, latestBenchmark] = await Promise.all([
      evaluationApi.status(),
      evaluationApi.benchmarkStatus(),
      evaluationApi.humanSummary(),
      evaluationApi.benchmarkResults(),
    ]);
    return { status, benchmarkStatus, humanSummary, latestBenchmark };
  }, []);

  if (loading) return <LoadingState label="Loading evaluation readiness..." />;
  if (error) return <ErrorState error={error} />;

  const readiness = data?.status || {};
  const human = data?.humanSummary || {};
  const benchmark = data?.benchmarkStatus || {};
  const latest = data?.latestBenchmark || {};
  const readyProviders = (readiness.provider_readiness || []).filter((provider) => provider.enabled).length;
  const totalProviders = (readiness.provider_readiness || []).length;

  return (
    <div className="stack admin-analytics-page evaluation-control-page">
      <PageHeader
        eyebrow="Evaluation control center"
        title="Evaluation Readiness"
        description="System readiness, provider health, clinical safety gates, human review coverage, and benchmark governance. Model output comparison lives in Benchmark Results."
        actions={(
          <div className="page-header-actions">
            <button className="btn secondary" onClick={reload} type="button">Refresh</button>
            <Link to="/admin/evaluation/benchmark"><button className="btn" type="button">Open Benchmark Results</button></Link>
          </div>
        )}
      />

      <div className="metric-grid">
        <MetricCard label="Providers ready" value={`${readyProviders}/${totalProviders || 0}`} detail="Configured generation backends" />
        <MetricCard label="Citation readiness" value={readiness.citation_readiness || "unknown"} detail="Evidence-grounded claim checks" />
        <MetricCard label="Safety readiness" value={readiness.safety_readiness || "unknown"} detail="Unsupported and conflicting claim gates" />
        <MetricCard label="Human reviews" value={human.total_evaluations ?? 0} detail="Doctor rubric submissions" />
        <MetricCard label="Benchmark dataset" value={benchmark.status || "unknown"} detail={benchmark.dataset_path || "dataset path unavailable"} />
      </div>

      <div className="evaluation-distinction-grid">
        <Card title="What This Page Is For" actions={<Badge tone="info">readiness</Badge>}>
          <div className="evaluation-purpose-list">
            <PurposeItem icon={Activity} title="Operational readiness" text="Provider health, cache/config state, and whether core evaluation layers are runnable." />
            <PurposeItem icon={ShieldCheck} title="Clinical safety gates" text="Citation validation, unsupported-claim surfacing, auditability, and human approval workflow." />
            <PurposeItem icon={ClipboardCheck} title="Human review coverage" text="Rubric scores and reviewer feedback are tracked separately from automated benchmark metrics." />
          </div>
        </Card>
        <Card title="What Benchmark Results Is For" actions={<Badge tone="success">artifacts</Badge>}>
          <div className="evaluation-purpose-list">
            <PurposeItem icon={FileCheck2} title="Model comparison" text="ROUGE, BERTScore, clinical proxy metrics, prediction files, and model comparison CSVs." />
            <PurposeItem icon={Stethoscope} title="Three-flow comparison" text="Raw vs clinical context vs RAG-grounded outputs on the same record and same model." />
            <PurposeItem icon={Activity} title="Per-record failures" text="Generated summary, reference summary, retrieved evidence, citations, and failure labels side by side." />
          </div>
        </Card>
      </div>

      <div className="grid-two">
        <ProviderReadinessChart providers={readiness.provider_readiness} />
        <Card title="Evaluation Layer Status">
          <div className="evaluation-layer-list">
            {(readiness.evaluation_layers || []).map((layer) => (
              <div className="evaluation-layer-row" key={layer.layer}>
                <div>
                  <strong>{humanize(layer.layer)}</strong>
                  <p>{layer.message}</p>
                  {layer.expected_path ? <code>{layer.expected_path}</code> : null}
                </div>
                <Badge tone={statusTone(layer.status)}>{layer.status}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid-two">
        <Card title="Human Review Snapshot">
          <div className="human-review-score-grid">
            <ReviewScore label="Factual correctness" value={human.average_factual_correctness_score} />
            <ReviewScore label="Completeness" value={human.average_completeness_score} />
            <ReviewScore label="Conciseness" value={human.average_conciseness_score} />
            <ReviewScore label="Readability" value={human.average_readability_score} />
            <ReviewScore label="Citation usefulness" value={human.average_citation_usefulness_score} />
          </div>
          <div className="review-risk-list">
            {(human.hallucination_risk_distribution || []).length ? human.hallucination_risk_distribution.map((item) => (
              <span key={item.key}><strong>{item.key}</strong>{item.count}</span>
            )) : <p className="muted">No human hallucination-risk ratings have been submitted yet.</p>}
          </div>
        </Card>

        <Card title="Benchmark Governance Snapshot">
          <div className="metric-list">
            <div><span>Runner</span><strong>{benchmark.benchmark_runner_exists ? "available" : "missing"}</strong></div>
            <div><span>Model comparison output</span><strong>{benchmark.model_comparison_output_exists ? "available" : "missing"}</strong></div>
            <div><span>Latest selected output</span><strong>{latest.selected_output_dir || latest.output_dir || "not available"}</strong></div>
            <div><span>Latest report</span><strong>{latest.report_exists ? "available" : "missing"}</strong></div>
          </div>
          <p className="warning-line">{latest.proxy_warning || "Proxy evaluation only. Real clinical validation remains pending governed EHR access."}</p>
        </Card>
      </div>
    </div>
  );
}

function PurposeItem({ icon: Icon, title, text }) {
  return (
    <div>
      <Icon aria-hidden="true" size={18} />
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
    </div>
  );
}

function ReviewScore({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value === null || value === undefined ? "n/a" : formatScore(value)}</strong>
    </div>
  );
}

function humanize(value = "") {
  return value.replaceAll("_", " ");
}
