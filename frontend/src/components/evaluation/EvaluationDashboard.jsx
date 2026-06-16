import { Link } from "react-router-dom";
import { Activity, BrainCircuit, ClipboardCheck, DatabaseZap, FileCheck2, ShieldCheck, Stethoscope } from "lucide-react";

import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import ErrorState from "../common/ErrorState.jsx";
import LoadingState from "../common/LoadingState.jsx";
import MetricCard from "../common/MetricCard.jsx";
import PageHeader from "../common/PageHeader.jsx";
import { useApi } from "../../hooks/useApi.js";
import { evaluationApi } from "../../services/evaluationApi.js";
import { formatScore, providerLabel, ProviderReadinessChart, statusTone } from "./BenchmarkVisuals.jsx";

const FLOW_2_1_PROVIDERS = ["qwen2.5", "llama3.2", "gemini2.5_flash_lite"];

export default function EvaluationDashboard() {
  const { data, error, loading, reload } = useApi(async () => {
    const [status, benchmarkStatus, humanSummary, humanRubric, humanAnalytics, latestBenchmark] = await Promise.all([
      evaluationApi.status(),
      evaluationApi.benchmarkStatus(),
      evaluationApi.humanSummary(),
      evaluationApi.humanRubric(),
      evaluationApi.humanAnalytics(),
      evaluationApi.benchmarkResults(),
    ]);
    return { status, benchmarkStatus, humanSummary, humanRubric, humanAnalytics, latestBenchmark };
  }, []);

  if (loading) return <LoadingState label="Loading evaluation readiness..." />;
  if (error) return <ErrorState error={error} />;

  const readiness = data?.status || {};
  const human = data?.humanSummary || {};
  const humanRubric = data?.humanRubric || {};
  const humanAnalytics = data?.humanAnalytics || {};
  const benchmark = data?.benchmarkStatus || {};
  const latest = data?.latestBenchmark || {};
  const ragGate = readiness.rag_readiness_gate || {};
  const readyProviders = (readiness.provider_readiness || []).filter((provider) => provider.enabled).length;
  const totalProviders = (readiness.provider_readiness || []).length;
  const flow21Providers = FLOW_2_1_PROVIDERS.map((name) => (
    (readiness.provider_readiness || []).find((provider) => provider.provider === name)
  )).filter(Boolean);

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

      <Card title="Flow 2.1 Provider Readiness" actions={<Badge tone="info">RAG best models</Badge>}>
        <div className="flow-provider-grid">
          {flow21Providers.length ? flow21Providers.map((provider) => (
            <FlowProviderCard key={provider.provider} provider={provider} />
          )) : <p className="muted">Qwen2.5, Llama3.2, and Gemini 2.5 Flash Lite are not reported by the backend yet. Restart the backend after pulling local models.</p>}
        </div>
      </Card>

      <Card title="RAG Readiness Gate" actions={<Badge tone={gateTone(ragGate.status)}>{ragGate.status || "not available"}</Badge>}>
        <div className="rag-gate-panel">
          <div className="rag-gate-summary">
            <DatabaseZap aria-hidden="true" size={20} />
            <div>
              <strong>{humanize(ragGate.decision || "do_not_replace_doctor_flow")}</strong>
              <p>{ragGate.message || "Run Flow 2.1 benchmark before considering doctor-flow integration."}</p>
              <code>{ragGate.selected_output_dir || "Flow 2.1 output not selected"}</code>
            </div>
          </div>
          <div className="rag-gate-metrics">
            <div><span>Records</span><strong>{ragGate.record_count ?? "n/a"}</strong></div>
            <div><span>Weak retrieval</span><strong>{ragGate.retrieval_summary?.weak_retrieval_count ?? "n/a"}</strong></div>
            <div><span>Recall@5</span><strong>{formatScore(ragGate.retrieval_summary?.average_recall_at_5)}</strong></div>
            <div><span>MRR</span><strong>{formatScore(ragGate.retrieval_summary?.average_mrr)}</strong></div>
          </div>
          <div className="rag-gate-checks">
            {(ragGate.checks || []).map((check) => (
              <div key={check.name}>
                <Badge tone={gateTone(check.status)}>{check.status}</Badge>
                <strong>{humanize(check.name)}</strong>
                <span>{formatGateValue(check.value)}</span>
                <p>{check.message}</p>
              </div>
            ))}
          </div>
        </div>
      </Card>

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

        <Card title="Human Evaluation At Scale" actions={<Badge tone="success">{humanRubric.rubric_version || "rubric"}</Badge>}>
          <div className="metric-list">
            <div><span>Total reviews</span><strong>{humanAnalytics.total_reviews ?? 0}</strong></div>
            <div><span>Approved locks</span><strong>{humanAnalytics.final_locked_approved_summaries ?? 0}</strong></div>
            <div><span>Approvals / rejections</span><strong>{humanAnalytics.approvals ?? 0} / {humanAnalytics.rejections ?? 0}</strong></div>
            <div><span>Average edit distance</span><strong>{humanAnalytics.average_edit_distance ?? "n/a"}</strong></div>
          </div>
          <div className="evaluation-purpose-list compact">
            {(humanRubric.dimensions || []).slice(0, 3).map((dimension) => (
              <PurposeItem key={dimension.key} icon={ClipboardCheck} title={dimension.label} text={dimension.description} />
            ))}
          </div>
          <div className="review-risk-list">
            {(humanAnalytics.rejection_reasons_distribution || []).length ? humanAnalytics.rejection_reasons_distribution.map((item) => (
              <span key={item.key}><strong>{humanize(item.key)}</strong>{item.count}</span>
            )) : <p className="muted">No rejection reasons have been recorded yet.</p>}
          </div>
          <p className="muted">Export endpoint: <code>/api/v1/evaluation/human/export?include_text=false</code></p>
        </Card>

      </div>

      <div className="grid-two">
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

function FlowProviderCard({ provider }) {
  return (
    <div className="flow-provider-card">
      <div>
        <BrainCircuit aria-hidden="true" size={18} />
        <strong>{providerLabel(provider.provider)}</strong>
      </div>
      <Badge tone={statusTone(provider.status)}>{provider.status}</Badge>
      <span>{provider.model_name || "model not configured"}</span>
      <p>{provider.message}</p>
      {provider.health_checks ? (
        <div className="provider-health-list">
          {"ollama_running" in provider.health_checks ? <span>Ollama: {provider.health_checks.ollama_running ? "running" : "offline"}</span> : null}
          {"model_present" in provider.health_checks ? <span>Model: {provider.health_checks.model_present ? "found" : "missing"}</span> : null}
          {provider.warmup_latency_ms ? <span>Warmup: {provider.warmup_latency_ms} ms</span> : null}
          {"api_key_format_valid" in provider.health_checks ? <span>Gemini key: {provider.health_checks.api_key_format_valid ? "format ok" : "missing/invalid"}</span> : null}
        </div>
      ) : null}
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

function gateTone(status = "") {
  const normalized = String(status).toLowerCase();
  if (normalized.includes("ready") || normalized.includes("passed")) return "success";
  if (normalized.includes("blocked") || normalized.includes("failed")) return "danger";
  if (normalized.includes("caution") || normalized.includes("warning")) return "warning";
  return "info";
}

function formatGateValue(value) {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(4);
  return String(value);
}
