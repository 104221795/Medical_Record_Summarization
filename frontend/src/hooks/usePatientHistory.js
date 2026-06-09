import { useMemo, useState } from "react";
import { auditApi } from "../services/auditApi.js";
import { useApi } from "./useApi.js";
import {
  auditActor,
  auditEncounterId,
  auditModelName,
  auditPatientId,
  auditProvider,
  auditStatus,
  auditSummaryId,
  eventTimeValue,
  isReviewAuditEvent,
  isSummaryAuditEvent,
} from "../utils/historyDisplay.js";

const summaryActions = new Set([
  "generate_summary",
  "regenerate_summary",
  "start_review",
  "edit_summary",
  "approve_summary",
  "reject_summary",
  "view_summary",
  "view_review_history",
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
    .filter((event) => summaryActions.has(event.action) || isSummaryAuditEvent(event))
    .forEach((event) => {
      const summaryId = auditSummaryId(event, "");
      if (!summaryId) return;
      const eventProvider = providerFromEvent(event);
      const eventModelName = auditModelName(event);
      const eventEncounter = auditEncounterId(event, "");
      const eventActor = auditActor(event, "");
      const eventStatus = auditStatus(event, "");
      const current = grouped.get(summaryId) || {
        id: summaryId,
        summary_id: summaryId,
        patient_id: auditPatientId(event, ""),
        encounter: eventEncounter,
        provider: eventProvider,
        model_name: eventModelName,
        status: eventStatus || "draft",
        generated_at: null,
        reviewed_at: null,
        reviewer: eventActor,
        last_action: event.action,
        last_timestamp: event.timestamp,
        events: [],
      };
      current.patient_id = current.patient_id || auditPatientId(event, "");
      current.encounter = current.encounter || eventEncounter;
      current.provider = current.provider || eventProvider;
      current.model_name = current.model_name || eventModelName;
      if (isReviewAuditEvent(event) && eventActor) {
        current.reviewer = eventActor;
      } else {
        current.reviewer = current.reviewer || eventActor;
      }
      if (isNewerOrSame(event, current.last_timestamp)) {
        current.status = eventStatus || current.status;
        current.last_action = event.action;
        current.last_timestamp = event.timestamp || current.last_timestamp;
      }
      current.events.push(event);
      if (event.action === "generate_summary" || event.action === "regenerate_summary") {
        current.generated_at = earlierTimestamp(current.generated_at, event.timestamp);
      }
      if (isReviewAuditEvent(event)) {
        current.reviewed_at = laterTimestamp(current.reviewed_at, event.timestamp);
      }
      grouped.set(summaryId, current);
    });
  return Array.from(grouped.values()).sort((a, b) => new Date(b.last_timestamp || 0) - new Date(a.last_timestamp || 0));
}

function providerFromEvent(event) {
  return auditProvider(event, { emptyLabel: "", nonSummaryLabel: "" });
}

function isNewerOrSame(event, currentTimestamp) {
  if (!currentTimestamp) return true;
  return eventTimeValue(event) >= eventTimeValue({ timestamp: currentTimestamp });
}

function earlierTimestamp(current, next) {
  if (!next) return current;
  if (!current) return next;
  return new Date(next) < new Date(current) ? next : current;
}

function laterTimestamp(current, next) {
  if (!next) return current;
  if (!current) return next;
  return new Date(next) > new Date(current) ? next : current;
}
