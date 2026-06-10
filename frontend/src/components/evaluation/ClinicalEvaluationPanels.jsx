import { useEffect, useMemo, useState } from "react";
import { Download, Filter } from "lucide-react";
import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import { formatLatency, formatScore, providerLabel, statusTone } from "./BenchmarkVisuals.jsx";

const CLINICAL_METRICS = [
  ["citation_coverage", "Citation coverage", "Higher is better"],
  ["unsupported_claim_rate", "Unsupported claim rate", "Lower is better"],
  ["factuality_proxy_score", "Faithfulness proxy", "Higher is better"],
  ["critical_info_omission_rate", "Critical omission", "Lower is better"],
  ["timeline_completeness", "Timeline completeness", "Higher is better"],
];

export function ClinicalMetricPanel({ rows = [], summary = {} }) {
  const byProvider = summary?.by_provider || {};
  const metricRows = rows.map((row) => ({
    provider: row.model_provider,
    model_name: row.model_name,
    status: row.status,
    citation_coverage: valueOr(row.citation_coverage, byProvider[row.model_provider]?.citation_coverage),
    unsupported_claim_rate: valueOr(row.unsupported_claim_rate, byProvider[row.model_provider]?.unsupported_claim_rate),
    factuality_proxy_score: valueOr(row.factuality_proxy_score, byProvider[row.model_provider]?.factuality_proxy_score),
    critical_info_omission_rate: valueOr(row.critical_info_omission_rate, byProvider[row.model_provider]?.critical_info_omission_rate),
    timeline_completeness: valueOr(row.timeline_completeness, byProvider[row.model_provider]?.timeline_completeness),
    hallucinated_clinical_entity_count: valueOr(row.hallucinated_clinical_entity_count, byProvider[row.model_provider]?.hallucinated_clinical_entity_count),
    latency_p50_ms: valueOr(row.latency_p50_ms, byProvider[row.model_provider]?.latency_p50_ms),
    latency_p95_ms: valueOr(row.latency_p95_ms, byProvider[row.model_provider]?.latency_p95_ms),
  }));
  const best = metricRows.reduce(
    (top, row) => (Number(row.factuality_proxy_score || 0) > Number(top?.factuality_proxy_score || 0) ? row : top),
    null,
  );

  return (
    <div className="grid-two clinical-eval-grid">
      <Card title="Evidence Grounding">
        <div className="clinical-leader">
          <div>
            <span className="muted">Best faithfulness proxy</span>
            <strong>{best ? providerLabel(best.provider) : "not available"}</strong>
          </div>
          <Badge tone="info">{summary?.source || "artifact"}</Badge>
        </div>
        <div className="clinical-metric-list">
          {metricRows.length ? metricRows.map((row) => (
            <ProviderMetricStrip key={`${row.provider}-${row.model_name}`} row={row} />
          )) : <p className="muted">Clinical metric rows are not available for this run.</p>}
        </div>
      </Card>
      <Card title="Safety Metrics">
        <div className="clinical-safety-grid">
          {metricRows.length ? metricRows.map((row) => (
            <div className="clinical-safety-card" key={`${row.provider}-safety`}>
              <div className="prediction-file-head">
                <strong>{providerLabel(row.provider)}</strong>
                <Badge tone={statusTone(row.status)}>{row.status || "unknown"}</Badge>
              </div>
              <span>Hallucinated clinical entities: <strong>{formatScore(row.hallucinated_clinical_entity_count)}</strong></span>
              <span>Latency p50: <strong>{formatLatency(row.latency_p50_ms)}</strong></span>
              <span>Latency p95: <strong>{formatLatency(row.latency_p95_ms)}</strong></span>
            </div>
          )) : <p className="muted">Safety proxy metrics are not available yet.</p>}
        </div>
      </Card>
    </div>
  );
}

export function PerRecordFailureDashboard({ examples = [] }) {
  const [modelFilter, setModelFilter] = useState("all");
  const [failureFilter, setFailureFilter] = useState("all");
  const filterOptions = useMemo(() => buildFailureFilterOptions(examples), [examples]);
  const ordered = useMemo(
    () => filterFailureExamples(examples || [], modelFilter, failureFilter),
    [examples, modelFilter, failureFilter],
  );
  const allModelOptions = useMemo(() => buildModelOptions(examples), [examples]);
  const failureCounts = useMemo(() => countFailureLabels(ordered), [ordered]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selected = ordered[Math.min(selectedIndex, Math.max(ordered.length - 1, 0))];
  const selectedOutputs = useMemo(
    () => orderModelOutputs(selected?.model_outputs || [], modelFilter),
    [selected, modelFilter],
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [modelFilter, failureFilter, examples]);

  return (
    <Card
      title="Per-Record Failure Analysis"
      actions={(
        <div className="failure-toolbar">
          <Filter aria-hidden="true" size={16} />
          <select aria-label="Filter failure analysis by model" value={modelFilter} onChange={(event) => setModelFilter(event.target.value)}>
            {allModelOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <select aria-label="Filter failure analysis by failure type" value={failureFilter} onChange={(event) => setFailureFilter(event.target.value)}>
            {filterOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <button className="btn secondary" type="button" onClick={() => exportFailureCase(selected)} disabled={!selected}>
            <Download aria-hidden="true" className="ui-icon" size={16} />
            Export case
          </button>
        </div>
      )}
    >
      {ordered.length ? (
        <div className="failure-analysis-workspace">
          <div className="failure-summary-strip">
            <div><span>Total records</span><strong>{examples.length}</strong></div>
            <div><span>Filtered records</span><strong>{ordered.length}</strong></div>
            <div><span>Selected model</span><strong>{modelFilter === "all" ? "All" : providerLabel(modelFilter)}</strong></div>
            <div><span>Selected failure</span><strong>{failureFilter === "all" ? "All" : failureFilter}</strong></div>
          </div>
          <div className="failure-chip-row">
            {Object.entries(failureCounts).map(([label, count]) => (
              <button
                className={failureFilter === label ? "active" : ""}
                key={label}
                onClick={() => setFailureFilter(failureFilter === label ? "all" : label)}
                type="button"
              >
                <span>{label}</span>
                <strong>{count}</strong>
              </button>
            ))}
          </div>
          <div className="failure-dashboard">
            <div className="failure-example-list">
              {ordered.map((example, index) => (
                <button
                  className={`failure-example-button ${index === selectedIndex ? "active" : ""}`}
                  key={`${example.note_id || index}-${example.model_provider || ""}`}
                  onClick={() => setSelectedIndex(index)}
                  type="button"
                >
                  <strong>{example.note_id || `record ${index + 1}`}</strong>
                  <span>{(matchingFailureLabels(example, modelFilter) || []).slice(0, 3).join(", ") || "no major proxy failure"}</span>
                  <small>{modelSummary(example)}</small>
                </button>
              ))}
            </div>
            <div className="failure-example-detail">
              <div className="prediction-file-head">
                <div>
                  <strong>{selected?.note_id || "not available"}</strong>
                  <span className="muted">{selected?.dataset || "dataset not available"}</span>
                </div>
                <div className="badge-row">
                  {(selected?.failure_labels || []).map((label) => <Badge key={label} tone={labelTone(label)}>{label}</Badge>)}
                </div>
              </div>
              <div className="record-context-grid">
                <TextPanel title="Input note" text={selected?.input_note} />
                <TextPanel title="Reference summary" text={selected?.reference_summary} />
                <TextPanel title="Retrieved evidence" text={selected?.retrieved_evidence || citationText(selected?.citations)} />
              </div>
              <div className="model-output-grid failure-model-grid">
                {selectedOutputs.map((output) => (
                  <div className={`model-output-card ${modelFilter === output.model_provider ? "selected" : ""}`} key={`${selected?.note_id}-${output.model_provider}`}>
                    <div className="prediction-file-head">
                      <div>
                        <strong>{providerLabel(output.model_provider)}</strong>
                        <span className="muted">{output.model_name || "model name not available"}</span>
                      </div>
                      <Badge tone={statusTone(output.status)}>{output.status || "unknown"}</Badge>
                    </div>
                    <div className="mini-metrics">
                      <span>ROUGE-L <strong>{formatScore(output.rougeL)}</strong></span>
                      <span>Faithfulness <strong>{formatScore(output.clinical_metrics?.factuality_proxy_score)}</strong></span>
                      <span>Unsupported <strong>{formatScore(output.clinical_metrics?.unsupported_claim_rate)}</strong></span>
                      <span>Diagnosis miss <strong>{formatScore(output.clinical_metrics?.missing_diagnosis_rate)}</strong></span>
                      <span>Medication miss <strong>{formatScore(output.clinical_metrics?.missing_medication_rate)}</strong></span>
                      <span>Timeline <strong>{formatScore(output.clinical_metrics?.timeline_completeness)}</strong></span>
                    </div>
                    <div className="badge-row flow-labels">
                      {(output.failure_labels || []).map((label) => <Badge key={label} tone={labelTone(label)}>{label}</Badge>)}
                    </div>
                    <p className="text-sample">{output.generated_summary || output.error_message || "No generated output available."}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : <p className="muted">Per-record failure examples are not available yet. Run the upgraded benchmark pipeline to generate them.</p>}
    </Card>
  );
}

export function UseCaseRecommendationPanel({ rows = [] }) {
  const completed = rows.filter((row) => Number(row.completed_count || 0) > 0);
  const recommendations = [
    ["Best lexical overlap", bestBy(completed, "rougeL", "high"), "ROUGE-L"],
    ["Best semantic similarity", bestBy(completed, "bertscore_f1", "high"), "BERTScore F1"],
    ["Best evidence grounding", bestBy(completed, "citation_coverage", "high"), "Citation coverage"],
    ["Lowest unsupported claims", bestBy(completed, "unsupported_claim_rate", "low"), "Unsupported claim rate"],
    ["Fastest local run", bestBy(completed, "average_latency_ms", "low"), "Average latency"],
  ];
  return (
    <Card title="Best Model By Use Case">
      <div className="status-grid">
        {recommendations.map(([label, row, metric]) => (
          <div key={label}>
            <span className="muted">{label}</span>
            <strong>{row ? providerLabel(row.model_provider) : "not available"}</strong>
            <p>{metric}: {row ? formatUseCaseMetric(row, metric) : "n/a"}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ProviderMetricStrip({ row }) {
  return (
    <div className="clinical-provider-strip">
      <div className="metric-chart-label">
        <strong>{providerLabel(row.provider)}</strong>
        <span>{row.model_name}</span>
      </div>
      <div className="clinical-metric-grid">
        {CLINICAL_METRICS.map(([key, label, hint]) => (
          <div key={key} title={hint}>
            <span>{label}</span>
            <strong>{formatScore(row[key])}</strong>
          </div>
        ))}
      </div>
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

function citationText(citations = []) {
  if (!Array.isArray(citations) || !citations.length) return "";
  return citations.map((citation) => citation.source_text || citation.text || citation.source_id || JSON.stringify(citation)).join("\n");
}

function buildModelOptions(examples = []) {
  const providers = new Set();
  examples.forEach((example) => (example.model_outputs || []).forEach((output) => providers.add(output.model_provider)));
  return [
    { value: "all", label: "All models" },
    ...[...providers].filter(Boolean).sort(providerSort).map((provider) => ({ value: provider, label: providerLabel(provider) })),
  ];
}

function buildFailureFilterOptions(examples = []) {
  const labels = new Set();
  examples.forEach((example) => {
    (example.failure_labels || []).forEach((label) => labels.add(label));
    (example.model_outputs || []).forEach((output) => (output.failure_labels || []).forEach((label) => labels.add(label)));
  });
  return [
    { value: "all", label: "All failure types" },
    ...[...labels].filter(Boolean).sort().map((label) => ({ value: label, label })),
  ];
}

function filterFailureExamples(examples, modelFilter, failureFilter) {
  return examples.filter((example) => {
    const outputs = example.model_outputs || [];
    const matchingOutputs = modelFilter === "all" ? outputs : outputs.filter((output) => output.model_provider === modelFilter);
    if (!matchingOutputs.length) return false;
    if (failureFilter === "all") return true;
    const recordLabels = example.failure_labels || [];
    return recordLabels.includes(failureFilter) || matchingOutputs.some((output) => (output.failure_labels || []).includes(failureFilter));
  });
}

function matchingFailureLabels(example, modelFilter) {
  if (modelFilter === "all") return example.failure_labels || [];
  const labels = new Set();
  (example.model_outputs || [])
    .filter((output) => output.model_provider === modelFilter)
    .forEach((output) => (output.failure_labels || []).forEach((label) => labels.add(label)));
  return [...labels];
}

function orderModelOutputs(outputs, modelFilter) {
  const ordered = [...outputs].sort((a, b) => providerSort(a.model_provider, b.model_provider));
  if (modelFilter === "all") return ordered;
  return ordered.sort((a, b) => (a.model_provider === modelFilter ? -1 : b.model_provider === modelFilter ? 1 : 0));
}

function providerSort(a, b) {
  const order = ["deterministic", "bart", "pegasus", "qwen2.5", "llama3.2", "gemini2.5_flash_lite", "pegasus_pubmed", "pegasus_cnn_dailymail", "gemini"];
  return (order.indexOf(a) === -1 ? 99 : order.indexOf(a)) - (order.indexOf(b) === -1 ? 99 : order.indexOf(b));
}

function countFailureLabels(examples = []) {
  const counts = {};
  examples.forEach((example) => (example.failure_labels || []).forEach((label) => {
    counts[label] = (counts[label] || 0) + 1;
  }));
  return counts;
}

function labelTone(label = "") {
  const text = label.toLowerCase();
  if (text.includes("no major")) return "success";
  if (text.includes("retrieval") || text.includes("hallucinated") || text.includes("unsupported")) return "danger";
  if (text.includes("missing") || text.includes("incomplete")) return "warning";
  return "info";
}

function modelSummary(example) {
  const providers = (example.model_outputs || []).map((output) => providerLabel(output.model_provider));
  return providers.length ? providers.join(" / ") : "no model outputs";
}

function exportFailureCase(example) {
  if (!example) return;
  const payload = {
    exported_at: new Date().toISOString(),
    review_type: "per_record_failure_analysis",
    case: example,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `failure_case_${example.note_id || "record"}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function valueOr(primary, fallback) {
  return primary === null || primary === undefined || primary === "" ? fallback : primary;
}

function bestBy(rows, key, direction) {
  const candidates = rows.filter((row) => row[key] !== null && row[key] !== undefined && row[key] !== "" && Number.isFinite(Number(row[key])));
  if (!candidates.length) return null;
  return candidates.reduce((best, row) => {
    const value = Number(row[key]);
    const bestValue = Number(best[key]);
    return direction === "low" ? (value < bestValue ? row : best) : (value > bestValue ? row : best);
  }, candidates[0]);
}

function formatUseCaseMetric(row, metric) {
  if (metric === "Average latency") return formatLatency(row.average_latency_ms);
  if (metric === "Unsupported claim rate") return formatScore(row.unsupported_claim_rate);
  if (metric === "Citation coverage") return formatScore(row.citation_coverage);
  if (metric === "BERTScore F1") return formatScore(row.bertscore_f1);
  return formatScore(row.rougeL);
}
