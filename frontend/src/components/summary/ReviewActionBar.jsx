import { Link } from "react-router-dom";
import { useState } from "react";
import Button from "../common/Button.jsx";

export default function ReviewActionBar({
  summary,
  busyAction,
  toast,
  onStartReview,
  onSaveEdit,
  onApprove,
  onReject,
}) {
  const [rejectionReason, setRejectionReason] = useState("other");
  const [rejectionComment, setRejectionComment] = useState("");
  const hasSummary = Boolean(summary?.summary_id);
  return (
    <section className="review-action-bar">
      <div className="review-action-message">
        <strong>{hasSummary ? "Doctor review actions" : "Load a summary to begin review"}</strong>
        {toast && <span className={toast.tone === "error" ? "toast-error" : "toast-success"}>{toast.message}</span>}
        <div className="reject-fields">
          <select value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} aria-label="Rejection reason">
            <option value="other">Other</option>
            <option value="unsupported_claim">Unsupported claim</option>
            <option value="wrong_citation">Wrong citation</option>
            <option value="missing_critical_info">Missing critical info</option>
            <option value="incorrect_clinical_fact">Incorrect clinical fact</option>
            <option value="poor_readability">Poor readability</option>
          </select>
          <input
            value={rejectionComment}
            onChange={(event) => setRejectionComment(event.target.value)}
            placeholder="Optional rejection comment"
          />
        </div>
      </div>
      <div className="review-action-buttons">
        <Button disabled={!hasSummary || Boolean(busyAction)} onClick={onStartReview}>
          {busyAction === "start" ? "Starting..." : "Start Review"}
        </Button>
        <Button variant="secondary" disabled={!hasSummary || Boolean(busyAction)} onClick={onSaveEdit}>
          {busyAction === "edit" ? "Saving..." : "Save Edit"}
        </Button>
        <Button variant="success" disabled={!hasSummary || Boolean(busyAction)} onClick={onApprove}>
          {busyAction === "approve" ? "Approving..." : "Approve"}
        </Button>
        <Button
          variant="danger"
          disabled={!hasSummary || Boolean(busyAction)}
          onClick={() => onReject({ rejectionReason, rejectionComment })}
        >
          {busyAction === "reject" ? "Rejecting..." : "Reject"}
        </Button>
        <Link to="/doctor/generate-summary">
          <Button variant="ghost">Back to Generate Summary</Button>
        </Link>
      </div>
    </section>
  );
}
