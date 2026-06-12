import { Link } from "react-router-dom";
import Badge from "../common/Badge.jsx";
import Button from "../common/Button.jsx";
import Card from "../common/Card.jsx";
import { formatDateTime, statusTone } from "../../utils/clinicalDisplay.js";

export default function DraftPreviewCard({ summary }) {
  if (!summary) {
    return (
      <Card title="Draft Preview" className="golden-card draft-preview-card compact">
        <div className="draft-empty-compact">
          <strong>No draft yet</strong>
          <p>Select patient, choose provider, then generate a draft.</p>
        </div>
      </Card>
    );
  }
  return (
    <Card
      title="Draft Preview"
      className="golden-card draft-preview-card compact"
      actions={<Badge tone={statusTone(summary.status)}>{summary.status}</Badge>}
    >
      <div className="draft-preview-meta">
        <div><span>Summary ID</span><strong title={summary.summary_id}>{compactId(summary.summary_id)}</strong></div>
        <div><span>Provider</span><strong>{summary.model_provider || summary.model_name || "not available"}</strong></div>
        <div><span>Generated</span><strong>{formatDateTime(summary.generated_at)}</strong></div>
      </div>
      <div className="draft-preview-text">
        {summary.summary_text || "Draft summary text is unavailable."}
      </div>
      <div className="public-actions">
        <Link to={`/doctor/review/${summary.summary_id}`}>
          <Button>Review Evidence</Button>
        </Link>
      </div>
    </Card>
  );
}

function compactId(value = "") {
  const text = String(value || "");
  if (text.length <= 18) return text || "not available";
  return `${text.slice(0, 8)}...${text.slice(-6)}`;
}
