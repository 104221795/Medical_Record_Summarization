const SUMMARY_ACTIONS = new Set([
  "generate_summary",
  "regenerate_summary",
  "view_summary",
  "start_review",
  "edit_summary",
  "approve_summary",
  "reject_summary",
  "view_review_history",
]);

const REVIEW_ACTIONS = new Set([
  "start_review",
  "edit_summary",
  "approve_summary",
  "reject_summary",
  "view_review_history",
]);

export function auditMetadata(event) {
  return event?.action_metadata || event?.metadata || {};
}

export function isSummaryAuditEvent(event) {
  return event?.resource_type === "summary" || SUMMARY_ACTIONS.has(event?.action);
}

export function isReviewAuditEvent(event) {
  return REVIEW_ACTIONS.has(event?.action);
}

export function auditSummaryId(event, fallback = "not available") {
  const metadata = auditMetadata(event);
  const summaryId =
    (event?.resource_type === "summary" ? event?.resource_id : null) ||
    metadata.summary_id ||
    metadata.parent_summary_id;
  return summaryId || fallback;
}

export function auditPatientId(event, fallback = "not available") {
  const metadata = auditMetadata(event);
  return event?.patient_id || metadata.patient_id || fallback;
}

export function auditEncounterId(event, fallback = "not available") {
  const metadata = auditMetadata(event);
  return metadata.encounter_id || metadata.encounter || fallback;
}

export function auditProvider(event, options = {}) {
  const { emptyLabel = "not available", nonSummaryLabel = "not applicable" } = options;
  const metadata = auditMetadata(event);
  const provider =
    metadata.provider ||
    metadata.model_provider ||
    event?.provider ||
    event?.model_provider ||
    metadata.model_name ||
    event?.model_name;

  if (provider) return provider;
  return isSummaryAuditEvent(event) ? emptyLabel : nonSummaryLabel;
}

export function auditModelName(event) {
  const metadata = auditMetadata(event);
  return metadata.model_name || event?.model_name || "";
}

export function auditStatus(event, fallback = "recorded") {
  const metadata = auditMetadata(event);
  return metadata.status || metadata.summary_status || event?.status || fallback;
}

export function auditActor(event, fallback = "not available") {
  const metadata = auditMetadata(event);
  return event?.user_display_name || metadata.actor_external_id || event?.user_id || fallback;
}

export function eventTimeValue(event) {
  const value = event?.timestamp || event?.created_at;
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date.getTime() : 0;
}
