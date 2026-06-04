import { useState } from "react";
import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import EmptyState from "../common/EmptyState.jsx";
import { statusTone } from "../../utils/clinicalDisplay.js";

const tabs = [
  { key: "citations", label: "Citations" },
  { key: "claims", label: "Claims" },
  { key: "unsupported", label: "Needs Review" },
];

export default function CitationReviewPanel({
  citations = [],
  claims = [],
  selectedCitationId,
  selectedClaimId,
  onSelectCitation,
  onSelectClaim,
}) {
  const [activeTab, setActiveTab] = useState("citations");
  const unsupported = claims.filter((claim) => claim.support_status !== "supported");

  return (
    <Card title="Citation & Claim Review" className="citation-review-panel">
      <div className="review-tabs">
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab.key}
            className={activeTab === tab.key ? "active" : ""}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {activeTab === "citations" && (
        <div className="review-tab-panel">
          {!citations.length && <EmptyState title="No citations attached yet." message="Generate or load a summary to review evidence." />}
          {citations.map((citation, index) => (
            <button
              type="button"
              className={`citation-card ${citation.citation_id === selectedCitationId ? "selected" : ""}`}
              key={citation.citation_id}
              onClick={() => onSelectCitation(citation.citation_id, citation.claim_id)}
            >
              <Badge tone="info">{`C${index + 1}`}</Badge>
              <strong>{citation.source_type || citation.source_record_type || "Source"}</strong>
              <span>{citation.claim_text || "Supported claim unavailable."}</span>
            </button>
          ))}
        </div>
      )}
      {activeTab === "claims" && (
        <div className="review-tab-panel">
          {!claims.length && <EmptyState title="No claim validation available." message="Generate or load a summary to review claims." />}
          {claims.map((claim) => (
            <button
              type="button"
              className={`claim-review-card ${claim.claim_id === selectedClaimId ? "selected" : ""}`}
              key={claim.claim_id}
              onClick={() => onSelectClaim(claim.claim_id)}
            >
              <Badge tone={statusTone(claim.support_status)}>{claim.support_status || "needs review"}</Badge>
              <span>{claim.claim_text}</span>
              {claim.citations?.length ? <small>{claim.citations.length} evidence link(s)</small> : <small>No evidence link attached.</small>}
            </button>
          ))}
        </div>
      )}
      {activeTab === "unsupported" && (
        <div className="review-tab-panel">
          {!unsupported.length && <EmptyState title="No unsupported claims detected." message="Continue reviewing citations before approval." />}
          {unsupported.map((claim) => (
            <button
              type="button"
              className={`claim-review-card needs-review ${claim.claim_id === selectedClaimId ? "selected" : ""}`}
              key={claim.claim_id}
              onClick={() => onSelectClaim(claim.claim_id)}
            >
              <Badge tone={statusTone(claim.support_status)}>{claim.support_status || "needs review"}</Badge>
              <span>{claim.claim_text}</span>
              <small>{claim.clinical_risk_level ? `Risk: ${claim.clinical_risk_level}` : "Review evidence before approving."}</small>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}
