import Card from "../common/Card.jsx";
import Badge from "../common/Badge.jsx";

export default function CitationPanel({ summary }) {
  const claims = summary?.sections?.flatMap((section) => section.claims || []) || [];
  const citations = claims.flatMap((claim) => claim.citations || []);
  return (
    <Card title="Citation & Evidence">
      <div className="stack">
        {citations.length ? citations.map((citation) => (
          <div className="evidence-row" key={citation.citation_id}>
            <Badge tone="info">{citation.source_type || "source"}</Badge>
            <p>{citation.source_text_span || citation.surrounding_context || "Evidence text unavailable."}</p>
          </div>
        )) : <p className="muted">No citations attached yet.</p>}
      </div>
    </Card>
  );
}
