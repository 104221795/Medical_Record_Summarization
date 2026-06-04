import Card from "../common/Card.jsx";
import Badge from "../common/Badge.jsx";

export default function ClaimValidationPanel({ summary }) {
  const claims = summary?.sections?.flatMap((section) => section.claims || []) || [];
  return (
    <Card title="Claim Validation">
      <div className="stack">
        {claims.map((claim) => <div className="claim-row" key={claim.claim_id}><Badge tone={claim.support_status === "supported" ? "success" : "warning"}>{claim.support_status}</Badge><span>{claim.claim_text}</span></div>)}
      </div>
    </Card>
  );
}
