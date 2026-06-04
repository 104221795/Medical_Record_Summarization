import Card from "../common/Card.jsx";

export default function UnsupportedClaimsPanel({ summary }) {
  const claims = summary?.sections?.flatMap((section) => section.claims || []) || [];
  const unsupported = claims.filter((claim) => claim.support_status !== "supported");
  return (
    <Card title="Unsupported / Review Needed">
      {unsupported.length ? unsupported.map((claim) => <p key={claim.claim_id} className="warning-line">{claim.claim_text}</p>) : <p className="muted">No unsupported claims reported.</p>}
    </Card>
  );
}
