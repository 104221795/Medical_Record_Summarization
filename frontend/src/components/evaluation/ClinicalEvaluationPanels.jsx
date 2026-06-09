import { useMemo, useState } from "react";
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
  const ordered = useMemo(() => examples || [], [examples]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selected = ordered[Math.min(selectedIndex, Math.max(ordered.length - 1, 0))];

  return (
    <Card title="Per-Record Failure Analysis">
      {ordered.length ? (
        <div className="failure-dashboard">
          <div className="failure-example-list">
            {ordered.map((example, index) => (
              <button
                className={`failure-example-button ${index === selectedIndex ? "active" : ""}`}
                key={example.note_id || index}
                onClick={() => setSelectedIndex(index)}
                type="button"
              >
                <strong>{example.note_id || `record ${index + 1}`}</strong>
                <span>{(example.failure_labels || []).slice(0, 3).join(", ") || "no major proxy failure"}</span>
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
                {(selected?.failure_labels || []).map((label) => <Badge key={label} tone="warning">{label}</Badge>)}
              </div>
            </div>
            <div className="record-context-grid">
              <TextPanel title="Input note" text={selected?.input_note} />
              <TextPanel title="Reference summary" text={selected?.reference_summary} />
              <TextPanel title="Retrieved evidence" text={selected?.retrieved_evidence || citationText(selected?.citations)} />
            </div>
            <div className="model-output-grid">
              {(selected?.model_outputs || []).map((output) => (
                <div className="model-output-card" key={`${selected?.note_id}-${output.model_provider}`}>
                  <div className="prediction-file-head">
                    <strong>{providerLabel(output.model_provider)}</strong>
                    <Badge tone={statusTone(output.status)}>{output.status || "unknown"}</Badge>
                  </div>
                  <div className="mini-metrics">
                    <span>ROUGE-L <strong>{formatScore(output.rougeL)}</strong></span>
                    <span>Faithfulness <strong>{formatScore(output.clinical_metrics?.factuality_proxy_score)}</strong></span>
                    <span>Unsupported <strong>{formatScore(output.clinical_metrics?.unsupported_claim_rate)}</strong></span>
                  </div>
                  <p className="text-sample">{output.generated_summary || output.error_message || "No generated output available."}</p>
                </div>
              ))}
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
