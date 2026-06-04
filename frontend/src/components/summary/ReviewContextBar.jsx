import Badge from "../common/Badge.jsx";
import { formatDateTime, patientLabel, statusTone } from "../../utils/clinicalDisplay.js";

export default function ReviewContextBar({ summary, patient }) {
  return (
    <section className="review-context-bar">
      <ContextItem label="Patient" value={patientLabel(patient) || summary?.patient_id} />
      <ContextItem label="Patient ID" value={summary?.patient_id || "not available"} />
      <ContextItem label="Encounter" value={summary?.encounter_id || "All encounters"} />
      <ContextItem label="Provider" value={summary?.model_provider || summary?.model_name || "not available"} />
      <div className="context-item">
        <span>Review status</span>
        <Badge tone={statusTone(summary?.status)}>{summary?.status || "not loaded"}</Badge>
      </div>
      <ContextItem label="Last updated" value={formatDateTime(summary?.reviewed_at || summary?.approved_at || summary?.rejected_at || summary?.generated_at)} />
      <ContextItem label="Summary ID" value={summary?.summary_id || "not loaded"} />
    </section>
  );
}

function ContextItem({ label, value }) {
  return (
    <div className="context-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
