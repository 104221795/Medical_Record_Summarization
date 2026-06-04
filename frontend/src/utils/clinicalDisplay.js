export function patientLabel(patient) {
  if (!patient) return "No patient selected";
  return patient.external_patient_id || patient.patient_hash || patient.patient_id || "Patient";
}

export function formatDateTime(value) {
  if (!value) return "not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

export function statusTone(status = "") {
  const normalized = String(status).toLowerCase();
  if (["approved", "supported", "completed", "active"].includes(normalized)) return "success";
  if (["rejected", "unsupported", "failed", "blocked"].includes(normalized)) return "danger";
  if (["under_review", "edited", "needs_review", "insufficient_evidence", "conflicting"].includes(normalized)) return "warning";
  return "info";
}

export function actionLabel(action = "") {
  return action
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
