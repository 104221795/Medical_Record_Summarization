export default function MetricCard({ label, value, detail }) {
  return <div className="metric-card"><span>{label}</span><strong>{value ?? "not available"}</strong>{detail && <small>{detail}</small>}</div>;
}
