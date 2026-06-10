import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, GitCompareArrows, SearchX } from "lucide-react";

import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import ErrorState from "../common/ErrorState.jsx";
import LoadingState from "../common/LoadingState.jsx";
import { useApi } from "../../hooks/useApi.js";
import { evaluationApi } from "../../services/evaluationApi.js";
import { formatScore, providerLabel, statusTone } from "./BenchmarkVisuals.jsx";

const FLOW_ORDER = [
  ["summarization_only", "Flow 1 Raw"],
  ["clinical_context", "Flow 1.5 Context"],
  ["rag_grounded", "Flow 2 RAG"],
];

const PROVIDER_OPTIONS = [
  ["", "All models"],
  ["deterministic", "Deterministic"],
  ["bart", "BART"],
  ["pegasus", "Pegasus XSum"],
  ["pegasus_pubmed", "Pegasus PubMed"],
  ["pegasus_cnn_dailymail", "Pegasus CNN"],
];

export default function FlowComparisonDashboard() {
  const [provider, setProvider] = useState("");
  const { data, error, loading, reload } = useApi(
    () => evaluationApi.benchmarkFlowComparison({ limit: 12, provider }),
    [provider],
  );
  const records = data?.records || [];
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selected = records[Math.min(selectedIndex, Math.max(records.length - 1, 0))];

  const outputSummary = useMemo(() => (
    (data?.flows || []).map((flow) => `${flow.title}: ${flow.output_dir}`).join("\n")
  ), [data]);

  if (loading) return <LoadingState label="Loading three-flow comparison..." />;
  if (error) {
    const notFound = String(error.message || "").toLowerCase().includes("not found");
    if (notFound) {
      return (
        <Card title="Three-Flow Same Record Comparison" actions={<Badge tone="warning">backend restart needed</Badge>}>
          <p className="warning-line">
            The comparison endpoint is not available from the currently running backend process.
            Restart the backend so it loads <code>/api/v1/evaluation/benchmark/flow-comparison</code>.
          </p>
        </Card>
      );
    }
    return <ErrorState error={error} />;
  }

  return (
    <Card
      title="Three-Flow Same Record Comparison"
      actions={(
        <div className="comparison-toolbar">
          <select aria-label="Filter comparison model" value={provider} onChange={(event) => { setSelectedIndex(0); setProvider(event.target.value); }}>
            {PROVIDER_OPTIONS.map(([value, label]) => <option key={value || "all"} value={value}>{label}</option>)}
          </select>
          <button className="btn secondary" type="button" onClick={reload}>Refresh</button>
        </div>
      )}
    >
      <div className="flow-comparison-intro">
        <div>
          <p>
            Compare the same record and same model across raw summarization, sectioned clinical context,
            and RAG-grounded generation. This panel is meant to answer: <strong>why do we need RAG?</strong>
          </p>
          <p className="warning-line">{data?.proxy_warning}</p>
        </div>
        <code title={outputSummary}>{outputSummary || "benchmark output folders not available"}</code>
      </div>

      {records.length ? (
        <div className="flow-comparison-layout">
          <div className="comparison-record-list">
            {records.map((record, index) => (
              <button
                className={`comparison-record-button ${index === selectedIndex ? "active" : ""}`}
                key={`${record.note_id}-${record.model_provider}`}
                onClick={() => setSelectedIndex(index)}
                type="button"
              >
                <strong>{providerLabel(record.model_provider)}</strong>
                <span>{record.note_id}</span>
                <Badge tone={verdictTone(record.verdict)}>{verdictLabel(record.verdict)}</Badge>
              </button>
            ))}
          </div>
          <div className="comparison-detail">
            <div className="comparison-head">
              <div>
                <span className="muted">Same record, same model</span>
                <strong>{selected?.note_id} · {providerLabel(selected?.model_provider)}</strong>
              </div>
              <div className="badge-row">
                {(selected?.highlights || []).map((highlight) => (
                  <Badge key={highlight} tone={highlightTone(highlight)}>{highlight}</Badge>
                ))}
              </div>
            </div>
            <div className="comparison-delta-grid">
              <DeltaCard label="Missing diagnosis" value={selected?.rag_delta?.missing_diagnosis_rate} lowerIsBetter />
              <DeltaCard label="Missing medication" value={selected?.rag_delta?.missing_medication_rate} lowerIsBetter />
              <DeltaCard label="Timeline completeness" value={selected?.rag_delta?.timeline_completeness} />
              <DeltaCard label="Unsupported claims" value={selected?.rag_delta?.unsupported_claim_rate} lowerIsBetter />
              <DeltaCard label="Citation coverage" value={selected?.rag_delta?.citation_coverage} />
            </div>
            <div className="flow-side-by-side">
              {FLOW_ORDER.map(([flowKey, label]) => (
                <FlowColumn
                  key={flowKey}
                  cell={selected?.flows?.[flowKey]}
                  flowKey={flowKey}
                  label={label}
                />
              ))}
            </div>
            <div className="record-context-grid">
              <TextPanel title="Input note" text={selected?.input_note} />
              <TextPanel title="Reference summary" text={selected?.reference_summary} />
              <TextPanel title="RAG evidence" text={selected?.flows?.rag_grounded?.retrieved_evidence} />
            </div>
          </div>
        </div>
      ) : (
        <div className="comparison-empty">
          <SearchX aria-hidden="true" size={28} />
          <div>
            <strong>No joined records are available yet.</strong>
            <p>Run all three flows with at least one overlapping model and record. The comparison requires matching <code>note_id + model_provider</code>.</p>
          </div>
        </div>
      )}
    </Card>
  );
}

function FlowColumn({ cell, flowKey, label }) {
  const metrics = cell?.clinical_metrics || {};
  return (
    <div className={`flow-column ${flowKey}`}>
      <div className="prediction-file-head">
        <div>
          <span className="muted">{label}</span>
          <strong>{cell?.model_name || "not available"}</strong>
        </div>
        <Badge tone={statusTone(cell?.status)}>{cell?.status || "missing"}</Badge>
      </div>
      <div className="flow-metric-strip">
        <span>ROUGE-L <strong>{formatScore(cell?.rougeL)}</strong></span>
        <span>Diagnosis miss <strong>{formatScore(metrics.missing_diagnosis_rate)}</strong></span>
        <span>Medication miss <strong>{formatScore(metrics.missing_medication_rate)}</strong></span>
        <span>Timeline <strong>{formatScore(metrics.timeline_completeness)}</strong></span>
        <span>Unsupported <strong>{formatScore(metrics.unsupported_claim_rate)}</strong></span>
        <span>Citation <strong>{formatScore(metrics.citation_coverage)}</strong></span>
      </div>
      <div className="badge-row flow-labels">
        {(cell?.failure_labels || []).length
          ? cell.failure_labels.map((labelText) => <Badge key={labelText} tone={labelText.includes("retrieval") ? "danger" : "warning"}>{labelText}</Badge>)
          : <Badge tone="success">no major proxy failure</Badge>}
      </div>
      <p className="text-sample">{cell?.generated_summary || cell?.error_message || "No generated summary available."}</p>
      {flowKey === "rag_grounded" ? (
        <p className="flow-evidence-preview">{cell?.retrieved_evidence || "Retrieved evidence not available for this record."}</p>
      ) : null}
    </div>
  );
}

function DeltaCard({ label, value }) {
  const numeric = Number(value);
  const available = Number.isFinite(numeric);
  const tone = !available ? "info" : numeric >= 0.05 ? "success" : numeric <= -0.05 ? "danger" : "info";
  return (
    <div className={`comparison-delta-card ${tone}`}>
      {tone === "success" ? <CheckCircle2 aria-hidden="true" size={16} /> : tone === "danger" ? <AlertTriangle aria-hidden="true" size={16} /> : <GitCompareArrows aria-hidden="true" size={16} />}
      <span>{label}</span>
      <strong>{available ? `${numeric > 0 ? "+" : ""}${numeric.toFixed(4)}` : "n/a"}</strong>
    </div>
  );
}

function TextPanel({ title, text }) {
  return (
    <div className="text-panel">
      <strong>{title}</strong>
      <p>{text || "not available"}</p>
    </div>
  );
}

function verdictTone(verdict = "") {
  if (verdict === "rag_helped") return "success";
  if (verdict === "rag_needs_review") return "danger";
  return "info";
}

function verdictLabel(verdict = "") {
  if (verdict === "rag_helped") return "RAG helped";
  if (verdict === "rag_needs_review") return "RAG review";
  return "mixed";
}

function highlightTone(highlight = "") {
  const text = highlight.toLowerCase();
  if (text.includes("increased") || text.includes("worsened") || text.includes("weak") || text.includes("mismatched")) return "danger";
  if (text.includes("reduced") || text.includes("improved")) return "success";
  return "info";
}
