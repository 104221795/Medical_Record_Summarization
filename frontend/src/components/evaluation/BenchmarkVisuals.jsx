import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";

const METRIC_DEFINITIONS = [
  { key: "rouge1", label: "ROUGE-1", className: "rouge-one" },
  { key: "rouge2", label: "ROUGE-2", className: "rouge-two" },
  { key: "rougeL", label: "ROUGE-L", className: "rouge-l" },
];

const PROVIDER_LABELS = {
  deterministic: "Deterministic",
  bart: "BART",
  pegasus: "Pegasus XSum",
  pegasus_pubmed: "Pegasus PubMed",
  pegasus_cnn_dailymail: "Pegasus CNN",
  pegasus_xsum: "Pegasus XSum",
  gemini: "Gemini",
};

export function providerLabel(provider) {
  return PROVIDER_LABELS[provider] || provider || "Unknown";
}

export function statusTone(status = "") {
  const normalized = String(status).toLowerCase();
  if (normalized.includes("completed")) return "success";
  if (normalized.includes("failed") || normalized.includes("rejected")) return "danger";
  if (
    normalized.includes("skipped")
    || normalized.includes("partial")
    || normalized.includes("warning")
    || normalized.includes("disabled")
    || normalized.includes("not_configured")
  ) {
    return "warning";
  }
  return "info";
}

export function measuredRows(rows = []) {
  return rows.filter((row) => {
    const status = String(row.status || "").toLowerCase();
    return Number(row.completed_count || 0) > 0 && !status.includes("estimated");
  });
}

export function bestByRougeL(rows = []) {
  return rows.reduce(
    (best, row) => (Number(row.rougeL || 0) > Number(best?.rougeL || 0) ? row : best),
    null,
  );
}

export function formatScore(value) {
  if (value === null || value === undefined || value === "") return "n/a";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(4) : "n/a";
}

export function formatInteger(value) {
  const numeric = Number(value || 0);
  return Number.isFinite(numeric) ? numeric.toLocaleString() : "0";
}

export function formatLatency(value) {
  if (value === null || value === undefined || value === "") return "n/a";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/a";
  if (numeric >= 1000) return `${(numeric / 1000).toFixed(1)} s`;
  return `${Math.round(numeric)} ms`;
}

function metricWidth(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return 0;
  return Math.min(100, Math.max(2, numeric * 100));
}

export function MetricComparisonChart({ rows = [], title = "ROUGE Comparison" }) {
  const chartRows = measuredRows(rows).sort((a, b) => Number(b.rougeL || 0) - Number(a.rougeL || 0));
  return (
    <Card title={title}>
      <div className="chart-legend" aria-label="ROUGE metric legend">
        {METRIC_DEFINITIONS.map((metric) => (
          <span key={metric.key}>
            <i className={`legend-dot ${metric.className}`} />
            {metric.label}
          </span>
        ))}
      </div>
      <div className="metric-comparison-chart">
        {chartRows.length ? chartRows.map((row) => (
          <div className="metric-chart-row" key={`${row.model_provider}-${row.model_name}`}>
            <div className="metric-chart-label">
              <strong>{providerLabel(row.model_provider)}</strong>
              <span>{row.checkpoint || row.model_name}</span>
            </div>
            <div className="metric-bars">
              {METRIC_DEFINITIONS.map((metric) => {
                const value = row[metric.key];
                const label = `${providerLabel(row.model_provider)} ${metric.label}: ${formatScore(value)}`;
                return (
                  <div className="metric-bar-line" key={metric.key} title={label} aria-label={label}>
                    <span className="metric-bar-label">{metric.label}</span>
                    <div className="metric-bar-track">
                      <span
                        className={`metric-bar-fill ${metric.className}`}
                        style={{ width: `${metricWidth(value)}%` }}
                      />
                    </div>
                    <strong>{formatScore(value)}</strong>
                  </div>
                );
              })}
            </div>
          </div>
        )) : <p className="muted">No completed benchmark rows are available.</p>}
      </div>
    </Card>
  );
}

export function RecordsEvaluatedChart({ rows = [] }) {
  const chartRows = rows.filter((row) => Number(row.record_count || row.completed_count || 0) > 0);
  return (
    <Card title="Records Evaluated">
      <div className="chart-legend" aria-label="Record status legend">
        <span><i className="legend-dot completed" />Completed</span>
        <span><i className="legend-dot failed" />Failed</span>
        <span><i className="legend-dot skipped" />Skipped</span>
      </div>
      <div className="record-stack-chart">
        {chartRows.length ? chartRows.map((row) => {
          const completed = Number(row.completed_count || 0);
          const failed = Number(row.failed_count || 0);
          const skipped = Number(row.skipped_count || 0);
          const total = Math.max(Number(row.record_count || 0), completed + failed + skipped, 1);
          const title = `${providerLabel(row.model_provider)}: ${completed}/${total} completed, ${failed} failed, ${skipped} skipped`;
          return (
            <div className="record-stack-row" key={`${row.model_provider}-${row.model_name}`} title={title}>
              <div className="record-stack-label">
                <strong>{providerLabel(row.model_provider)}</strong>
                <span>{row.status || "unknown status"}</span>
              </div>
              <div className="stacked-track" aria-label={title}>
                <span className="stacked-segment completed" style={{ width: `${(completed / total) * 100}%` }} />
                <span className="stacked-segment failed" style={{ width: `${(failed / total) * 100}%` }} />
                <span className="stacked-segment skipped" style={{ width: `${(skipped / total) * 100}%` }} />
              </div>
              <strong className="record-stack-value">{formatInteger(completed)} / {formatInteger(total)}</strong>
            </div>
          );
        }) : <p className="muted">No record count data is available.</p>}
      </div>
    </Card>
  );
}

export function FailurePatternChart({ summary }) {
  const counts = summary?.counts || {};
  const rows = Object.entries(counts)
    .filter(([, value]) => Number.isFinite(Number(value)))
    .map(([label, value]) => ({ label, value: Number(value) }))
    .sort((a, b) => b.value - a.value);
  const max = Math.max(...rows.map((row) => row.value), 1);
  return (
    <Card title="Failure Pattern Summary">
      <p className="muted">Source: {summary?.source || "not available"}</p>
      <div className="failure-chart">
        {rows.length ? rows.map((row) => {
          const title = `${row.label}: ${formatInteger(row.value)} records`;
          return (
            <div className="failure-row" key={row.label} title={title}>
              <span>{row.label}</span>
              <div className="failure-track" aria-label={title}>
                <span style={{ width: `${Math.max(4, (row.value / max) * 100)}%` }} />
              </div>
              <strong>{formatInteger(row.value)}</strong>
            </div>
          );
        }) : <p className="muted">Failure categories are not available for this run.</p>}
      </div>
    </Card>
  );
}

export function PredictionAvailabilityPanel({ availability = {} }) {
  const files = Object.entries(availability);
  return (
    <Card title="Prediction Files">
      <div className="prediction-file-grid">
        {files.length ? files.map(([filename, info]) => (
          <div className="prediction-file-card" key={filename}>
            <div className="prediction-file-head">
              <strong>{providerLabel(info.provider)}</strong>
              <Badge tone={info.exists ? "success" : "warning"}>{info.exists ? "found" : "missing"}</Badge>
            </div>
            <span>{filename}</span>
            <p>{formatInteger(info.record_count)} records</p>
            <code title={info.path}>{info.path || "not available"}</code>
          </div>
        )) : <p className="muted">Prediction file metadata is not available.</p>}
      </div>
    </Card>
  );
}

export function BenchmarkFolderPanel({ folders = [] }) {
  return (
    <Card title="Benchmark Folder Discovery">
      <div className="benchmark-folder-list">
        {folders.length ? folders.map((folder) => (
          <div className={`benchmark-folder-card ${folder.selected ? "selected" : ""}`} key={folder.path}>
            <div className="prediction-file-head">
              <strong>{folder.path}</strong>
              <Badge tone={folder.selected ? "success" : folder.exists ? "info" : "warning"}>
                {folder.selected ? "selected" : folder.exists ? "available" : "missing"}
              </Badge>
            </div>
            <div className="folder-facts">
              <span>model_comparison: {folder.has_model_comparison ? "yes" : "no"}</span>
              <span>per_record: {folder.has_per_record_metrics ? "yes" : "no"}</span>
              <span>PubMed rows: {formatInteger(folder.pegasus_pubmed_record_count)}</span>
              <span>Freshness: {folder.last_modified || "not available"}</span>
            </div>
          </div>
        )) : <p className="muted">No benchmark output folders were discovered.</p>}
      </div>
    </Card>
  );
}

export function ProviderReadinessChart({ providers = [] }) {
  return (
    <Card title="Provider Readiness">
      <div className="readiness-chart">
        {providers.length ? providers.map((provider) => {
          const value = provider.enabled ? 1 : provider.configured ? 0.55 : 0.25;
          const label = `${providerLabel(provider.provider)}: ${provider.status}`;
          return (
            <div className="readiness-row" key={provider.provider} title={label}>
              <div>
                <strong>{providerLabel(provider.provider)}</strong>
                <span>{provider.model_name || "not configured"}</span>
              </div>
              <div className="readiness-track" aria-label={label}>
                <span className={statusTone(provider.status)} style={{ width: `${value * 100}%` }} />
              </div>
              <Badge tone={statusTone(provider.status)}>{provider.status}</Badge>
            </div>
          );
        }) : <p className="muted">Provider readiness is not available.</p>}
      </div>
    </Card>
  );
}

export function ArtifactPathPanel({ paths = {} }) {
  const entries = Object.entries(paths).filter(([, value]) => value);
  return (
    <Card title="Run Artifacts">
      <div className="artifact-path-grid">
        {entries.length ? entries.map(([key, value]) => (
          <div key={key}>
            <Badge tone="info">{key.replaceAll("_", " ")}</Badge>
            <code title={value}>{value}</code>
          </div>
        )) : <p className="muted">No artifact paths are available.</p>}
      </div>
    </Card>
  );
}
