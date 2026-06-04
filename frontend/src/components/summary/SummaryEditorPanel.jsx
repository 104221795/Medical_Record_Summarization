import Badge from "../common/Badge.jsx";
import Button from "../common/Button.jsx";
import Card from "../common/Card.jsx";
import TextArea from "../common/TextArea.jsx";
import { statusTone } from "../../utils/clinicalDisplay.js";

export default function SummaryEditorPanel({
  summary,
  editedText,
  setEditedText,
  citations = [],
  selectedCitationId,
  onSelectCitation,
  onSave,
  saving,
}) {
  return (
    <Card
      title="Generated Summary / Editable Draft"
      className="summary-editor-panel"
      actions={summary?.status && <Badge tone={statusTone(summary.status)}>{summary.status}</Badge>}
    >
      <p className="muted">Edit only after checking the cited evidence.</p>
      <TextArea
        label="Editable summary"
        rows={18}
        value={editedText}
        onChange={(event) => setEditedText(event.target.value)}
        placeholder="Load or generate a summary before editing."
      />
      <div className="citation-marker-strip" aria-label="Citation markers">
        {citations.length ? citations.map((citation, index) => (
          <button
            type="button"
            key={citation.citation_id}
            className={citation.citation_id === selectedCitationId ? "active" : ""}
            onClick={() => onSelectCitation(citation.citation_id, citation.claim_id)}
          >
            {`[C${index + 1}]`}
          </button>
        )) : <span>No inline citation markers available.</span>}
      </div>
      <div className="summary-version-row">
        <span>Version {summary?.version_number || 1}</span>
        <span>{summary?.citation_coverage != null ? `Citation coverage ${summary.citation_coverage}` : "Citation coverage unavailable"}</span>
        <span>{summary?.unsupported_claim_count ?? 0} unsupported claims</span>
      </div>
      <Button variant="secondary" disabled={!summary || saving} onClick={onSave}>
        {saving ? "Saving..." : "Save Edit"}
      </Button>
    </Card>
  );
}
