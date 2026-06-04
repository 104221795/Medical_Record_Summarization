import MetricCard from "../common/MetricCard.jsx";

export default function RougeMetricCards({ rows = [] }) {
  const best = rows.reduce((top, row) => (Number(row.rougeL || 0) > Number(top?.rougeL || 0) ? row : top), null);
  return (
    <div className="metric-grid">
      <MetricCard label="Best model" value={best?.model_provider || "not available"} detail="By ROUGE-L" />
      <MetricCard label="ROUGE-1" value={best?.rouge1 ?? "not available"} />
      <MetricCard label="ROUGE-2" value={best?.rouge2 ?? "not available"} />
      <MetricCard label="ROUGE-L" value={best?.rougeL ?? "not available"} />
    </div>
  );
}
