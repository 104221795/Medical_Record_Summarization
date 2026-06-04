import { useMemo, useState } from "react";
import { auditApi } from "../services/auditApi.js";
import { useApi } from "./useApi.js";

const summaryActions = new Set([
  "generate_summary",
  "regenerate_summary",
  "start_review",
  "edit_summary",
  "approve_summary",
  "reject_summary",
]);

export function usePatientHistory() {
  const [pageSize] = useState(100);
  const { data, error, loading, reload } = useApi(() => auditApi.logs({ page: 1, page_size: pageSize }), [pageSize]);
  const rows = useMemo(() => buildHistoryRows(data?.items || []), [data]);
  return { rows, rawEvents: data?.items || [], error, loading, reload };
}

export function buildHistoryRows(events) {
  const grouped = new Map();
  events
    .filter((event) => summaryActions.has(event.action) || event.resource_type === "summary")
    .forEach((event) => {
      const summaryId = event.resource_id || event.action_metadata?.summary_id || event.metadata?.summary_id;
      if (!summaryId) return;
      const current = grouped.get(summaryId) || {
        id: summaryId,
        summary_id: summaryId,
        patient_id: event.patient_id,
        encounter: "not available",
        provider: providerFromEvent(event),
        status: event.action_metadata?.status || event.metadata?.status || "draft",
        generated_at: null,
        reviewed_at: null,
        reviewer: event.user_display_name || "not available",
        last_action: event.action,
        last_timestamp: event.timestamp,
        events: [],
      };
      current.patient_id = current.patient_id || event.patient_id;
      current.provider = current.provider || providerFromEvent(event);
      current.status = event.action_metadata?.status || event.metadata?.status || current.status;
      current.reviewer = event.user_display_name || current.reviewer;
      current.last_action = event.action;
      current.last_timestamp = event.timestamp || current.last_timestamp;
      current.events.push(event);
      if (event.action === "generate_summary" || event.action === "regenerate_summary") {
        current.generated_at = event.timestamp;
      }
      if (["start_review", "edit_summary", "approve_summary", "reject_summary"].includes(event.action)) {
        current.reviewed_at = event.timestamp;
      }
      grouped.set(summaryId, current);
    });
  return Array.from(grouped.values()).sort((a, b) => new Date(b.last_timestamp || 0) - new Date(a.last_timestamp || 0));
}

function providerFromEvent(event) {
  return (
    event.action_metadata?.provider ||
    event.metadata?.provider ||
    event.action_metadata?.model_provider ||
    event.metadata?.model_provider ||
    event.action_metadata?.model_name ||
    event.metadata?.model_name ||
    ""
  );
}
