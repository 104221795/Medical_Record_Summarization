import { useCallback, useEffect, useState } from "react";
import { patientApi } from "../services/patientApi.js";
import { summaryApi } from "../services/summaryApi.js";

export function useReviewWorkflow(summaryId) {
  const [summary, setSummary] = useState(null);
  const [patient, setPatient] = useState(null);
  const [encounters, setEncounters] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [editedText, setEditedText] = useState("");
  const [loading, setLoading] = useState(Boolean(summaryId));
  const [error, setError] = useState(null);
  const [busyAction, setBusyAction] = useState("");
  const [toast, setToast] = useState(null);
  const [lastOutcome, setLastOutcome] = useState(null);

  const loadSummary = useCallback(async (id = summaryId) => {
    if (!id) {
      setSummary(null);
      setLoading(false);
      return null;
    }
    setLoading(true);
    setError(null);
    try {
      const detail = await summaryApi.detail(id);
      setSummary(detail);
      setEditedText(detail.latest_edited_summary_text || detail.summary_text || "");
      const reviewList = await summaryApi.reviews(id).catch(() => ({ reviews: [] }));
      setReviews(reviewList?.reviews || []);
      if (detail.patient_id) {
        const [patientDetail, encounterList, documentList] = await Promise.all([
          patientApi.detail(detail.patient_id).catch(() => null),
          patientApi.encounters(detail.patient_id).catch(() => ({ items: [] })),
          patientApi.documents(detail.patient_id).catch(() => ({ items: [] })),
        ]);
        setPatient(patientDetail);
        setEncounters(encounterList?.items || []);
        setDocuments(documentList?.items || []);
      }
      return detail;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [summaryId]);

  useEffect(() => {
    loadSummary().catch(() => undefined);
  }, [loadSummary]);

  const runAction = async (actionName, action, successMessage) => {
    if (!summary?.summary_id) return null;
    setBusyAction(actionName);
    setToast(null);
    try {
      const result = await action(summary.summary_id);
      const refreshed = await loadSummary(summary.summary_id);
      setToast({ tone: "success", message: successMessage });
      if (actionName === "approve" || actionName === "reject") {
        setLastOutcome({
          action: actionName,
          result,
          summary: refreshed || summary,
          patient,
          timestamp: result?.approved_at || result?.rejected_at || result?.reviewed_at || new Date().toISOString(),
        });
      }
      return result;
    } catch (err) {
      setToast({ tone: "error", message: readableReviewError(err) });
      return null;
    } finally {
      setBusyAction("");
    }
  };

  return {
    summary,
    patient,
    encounters,
    documents,
    reviews,
    lastOutcome,
    setLastOutcome,
    editedText,
    setEditedText,
    loading,
    error,
    busyAction,
    toast,
    setToast,
    reload: loadSummary,
    startReview: () => runAction("start", (id) => summaryApi.startReview(id), "Review started."),
    saveEdit: () => runAction(
      "edit",
      (id) => summaryApi.edit(id, {
        edited_summary_text: editedText || summary.summary_text,
        edit_comment: "Edited in doctor evidence review workspace.",
      }),
      "Edited summary saved.",
    ),
    approve: () => runAction(
      "approve",
      (id) => summaryApi.approve(id, { approval_comment: "Approved after evidence review." }),
      "Summary approved.",
    ),
    reject: ({ rejectionReason = "other", rejectionComment = "Rejected from doctor evidence review workspace." } = {}) => runAction(
      "reject",
      (id) => summaryApi.reject(id, {
        rejection_reason: rejectionReason,
        rejection_comment: rejectionComment || "Rejected from doctor evidence review workspace.",
      }),
      "Summary rejected.",
    ),
  };
}

function readableReviewError(error) {
  const message = error?.message || String(error);
  if (message.includes("403")) return "You do not have permission for this review action. Confirm you are signed in as a doctor.";
  if (message.includes("409")) return "This summary is in a state that does not allow that action. Refresh and check the review status.";
  return message;
}
