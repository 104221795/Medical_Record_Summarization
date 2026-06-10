import { Activity } from "lucide-react";

export default function MetricCard({ label, value, detail, icon: Icon = Activity }) {
  return (
    <div className="metric-card">
      <div className="metric-card-topline">
        <Icon aria-hidden="true" className="ui-icon metric-card-icon" size={18} strokeWidth={2.2} />
        <span>{label}</span>
      </div>
      <strong>{value ?? "not available"}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}
