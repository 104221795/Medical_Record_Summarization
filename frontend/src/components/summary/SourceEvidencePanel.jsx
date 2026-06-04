import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import EmptyState from "../common/EmptyState.jsx";

const sectionLabels = ["Diagnosis", "Medication", "Timeline", "Assessment", "Plan"];

export default function SourceEvidencePanel({
  summary,
  documents = [],
  citations = [],
  selectedCitationId,
  onSelectCitation,
}) {
  const fallbackEvidence = documents.map((document, index) => ({
    citation_id: `document-${document.document_id || index}`,
    source_type: document.document_type || "document",
    source_text_span: document.raw_text || document.document_title || document.document_type,
    source_metadata: document.department || document.source_system || "clinical document",
    exactSpan: false,
  }));
  const evidence = citations.length
    ? citations.map((citation) => ({
      ...citation,
      exactSpan: Boolean(citation.source_text_span),
      source_text_span: citation.source_text_span || citation.surrounding_context || "Exact span unavailable; showing source chunk.",
    }))
    : fallbackEvidence;

  return (
    <Card title="Source Record / Evidence" className="evidence-panel">
      <div className="section-chip-row">
        {sectionLabels.map((label) => <Badge key={label} tone="info">{label}</Badge>)}
      </div>
      {!evidence.length && (
        <EmptyState
          title="Generate or load a summary to review evidence"
          message="Citation evidence and source chunks will appear here."
        />
      )}
      <div className="evidence-card-list">
        {evidence.map((item, index) => {
          const citationId = item.citation_id || `evidence-${index}`;
          const active = citationId === selectedCitationId;
          return (
            <button
              type="button"
              key={citationId}
              className={`evidence-card ${active ? "selected" : ""}`}
              onClick={() => onSelectCitation(citationId, item.claim_id)}
            >
              <span className="evidence-card-top">
                <Badge tone={item.claim_status === "supported" ? "success" : "info"}>{`C${index + 1}`}</Badge>
                <span>{item.source_type || item.source_record_type || "source"}</span>
              </span>
              <p>{item.source_text_span}</p>
              {!item.exactSpan && <small>Exact span unavailable; showing source chunk.</small>}
              {item.claim_text && <small>Linked claim: {item.claim_text}</small>}
              {item.source_metadata && <small>{item.source_metadata}</small>}
            </button>
          );
        })}
      </div>
      {summary && !citations.length && <p className="muted">No citations attached yet; source documents are shown as fallback context.</p>}
    </Card>
  );
}
