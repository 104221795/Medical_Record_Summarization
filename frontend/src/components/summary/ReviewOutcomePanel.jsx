import { Link } from "react-router-dom";
import Badge from "../common/Badge.jsx";
import Button from "../common/Button.jsx";
import Card from "../common/Card.jsx";
import { formatDateTime, patientLabel } from "../../utils/clinicalDisplay.js";

export default function ReviewOutcomePanel({ outcome, reviewer }) {
  if (!outcome) return null;
  const isApproved = outcome.action === "approve";
  const summary = outcome.summary || {};
  const patient = outcome.patient;
  return (
    <Card
      title={isApproved ? "Summary approved" : "Summary rejected"}
      className={`review-outcome-card ${isApproved ? "approved" : "rejected"}`}
      actions={<Badge tone={isApproved ? "success" : "danger"}>{isApproved ? "approved" : "rejected"}</Badge>}
    >
      <div className="review-outcome-grid">
        <OutcomeItem label="Summary ID" value={summary.summary_id || outcome.result?.summary_id} />
        <OutcomeItem label="Patient" value={patientLabel(patient) || summary.patient_id || outcome.result?.patient_id} />
        <OutcomeItem label="Reviewer" value={reviewer || outcome.result?.reviewed_by || "current doctor"} />
        <OutcomeItem label="Timestamp" value={formatDateTime(outcome.timestamp)} />
      </div>
      {isApproved ? (
        <p className="muted">The draft has moved to approved status. Continue with history or audit review if needed.</p>
      ) : (
        <p className="muted">The draft has moved to rejected status. You can edit the summary or generate a new draft.</p>
      )}
      <div className="public-actions">
        <Link to="/doctor/patient-history"><Button variant="secondary">View Patient History</Button></Link>
        <Link to="/doctor/audit-history"><Button variant="secondary">Open Audit History</Button></Link>
        <Link to={`/doctor/generate-summary${summary.patient_id ? `?patientId=${summary.patient_id}` : ""}`}>
          <Button>{isApproved ? "Generate New Summary" : "Generate New Draft"}</Button>
        </Link>
      </div>
    </Card>
  );
}

function OutcomeItem({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value || "not available"}</strong>
    </div>
  );
}
