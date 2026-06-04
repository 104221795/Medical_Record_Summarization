import { useState } from "react";
import Button from "../common/Button.jsx";
import { summaryApi } from "../../services/summaryApi.js";

export default function ReviewActions({ summary, editedText, onUpdated }) {
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  if (!summary) return null;
  const id = summary.summary_id;
  const runAction = async (name, action) => {
    setBusyAction(name);
    setError(null);
    try {
      const result = await action();
      setLastResult({ action: name, ...result });
      await onUpdated(result);
    } catch (err) {
      setError(err);
    } finally {
      setBusyAction("");
    }
  };
  const disabled = Boolean(busyAction);
  return (
    <>
      <div className="review-actions">
        <Button disabled={disabled} onClick={() => runAction("start", () => summaryApi.startReview(id))}>
          {busyAction === "start" ? "Starting..." : "Start Review"}
        </Button>
        <Button disabled={disabled} variant="secondary" onClick={() => runAction("edit", () => summaryApi.edit(id, { edited_summary_text: editedText || summary.summary_text, edit_comment: "Edited in React console." }))}>
          {busyAction === "edit" ? "Saving..." : "Save Edit"}
        </Button>
        <Button disabled={disabled} variant="success" onClick={() => runAction("approve", () => summaryApi.approve(id, { approval_comment: "Reviewed in React console." }))}>
          {busyAction === "approve" ? "Approving..." : "Approve"}
        </Button>
        <Button disabled={disabled} variant="danger" onClick={() => runAction("reject", () => summaryApi.reject(id, { rejection_reason: "other", rejection_comment: "Requested revision in React console." }))}>
          {busyAction === "reject" ? "Rejecting..." : "Reject"}
        </Button>
      </div>
      {lastResult && (
        <div className="review-result">
          <strong>{reviewActionLabel(lastResult.action)} completed</strong>
          <span>Status: {lastResult.status}</span>
          <span>Review ID: {lastResult.review_id}</span>
          {lastResult.reviewed_at && <span>Reviewed: {new Date(lastResult.reviewed_at).toLocaleString()}</span>}
        </div>
      )}
      {error && <p className="error-text">Review action failed: {error.message}</p>}
    </>
  );
}

function reviewActionLabel(action) {
  return {
    start: "Start review",
    edit: "Save edit",
    approve: "Approve",
    reject: "Reject",
  }[action] || "Review action";
}
