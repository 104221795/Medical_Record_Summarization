import { formatDateTime, patientLabel, statusTone } from "../../utils/clinicalDisplay.js";

export default function ReviewContextBar({ summary, patient }) {
  return (
    <section className="review-context-bar">
      <ContextItem label="Patient" value={patientLabel(patient) || summary?.patient_id} />
      <ContextItem label="Patient ID" value={compactId(summary?.patient_id) || "not available"} fullValue={summary?.patient_id} />
      <ContextItem label="Encounter" value={compactId(summary?.encounter_id) || "All encounters"} fullValue={summary?.encounter_id} />
      <ContextItem label="Provider" value={summary?.model_provider || summary?.model_name || "not available"} />
      <div className="context-item">
        <span>Flow</span>
        <strong className="context-pill info">Evidence-first</strong>
      </div>
      <div className="context-item">
        <span>Review status</span>
        <strong className={`context-pill ${statusTone(summary?.status)}`}>{summary?.status || "not loaded"}</strong>
      </div>
      <ContextItem label="Last updated" value={formatDateTime(summary?.reviewed_at || summary?.approved_at || summary?.rejected_at || summary?.generated_at)} />
      <ContextItem label="Summary ID" value={compactId(summary?.summary_id) || "not loaded"} fullValue={summary?.summary_id} />
    </section>
  );
}

function ContextItem({ label, value, fullValue }) {
  return (
    <div className="context-item">
      <span>{label}</span>
      <strong title={fullValue || value}>{value}</strong>
    </div>
  );
}

function compactId(value = "") {
  const text = String(value || "");
  if (!text || text.length <= 18) return text;
  return `${text.slice(0, 8)}...${text.slice(-6)}`;
}
