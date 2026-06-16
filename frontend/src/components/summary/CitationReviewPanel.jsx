import { useEffect, useMemo, useState } from "react";
import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import EmptyState from "../common/EmptyState.jsx";
import { statusTone } from "../../utils/clinicalDisplay.js";

export default function CitationReviewPanel({
  citations = [],
  claims = [],
  selectedCitationId,
  hoveredCitationId,
  activeCitationId,
  selectedCitation,
  selectedClaim,
  selectedClaimId,
  activeClaimId,
  onSelectCitation,
  onHoverCitation,
  onSelectClaim,
}) {
  const [activeTab, setActiveTab] = useState("citations");
  const unsupported = claims.filter((claim) => claim.support_status !== "supported");
  const currentCitationId = activeCitationId || hoveredCitationId || selectedCitationId;
  const tabItems = useMemo(() => ([
    { key: "citations", label: "Citations", count: citations.length },
    { key: "claims", label: "Claims", count: claims.length },
    { key: "unsupported", label: "Needs Review", count: unsupported.length },
  ]), [citations.length, claims.length, unsupported.length]);

  useEffect(() => {
    if (unsupported.length && activeTab === "citations" && !citations.length) setActiveTab("unsupported");
  }, [activeTab, citations.length, unsupported.length]);

  useEffect(() => {
    if (activeClaimId && unsupported.some((claim) => claim.claim_id === activeClaimId)) {
      setActiveTab("unsupported");
    }
  }, [activeClaimId, unsupported]);

  return (
    <Card title="Citation & Claim Review" className="citation-review-panel">
      <SelectedCitationDetail citation={selectedCitation} claim={selectedClaim} />
      <div className="claim-status-legend" aria-label="Claim status legend">
        <LegendItem tone="success" label="Supported" />
        <LegendItem tone="warning" label="Insufficient evidence" />
        <LegendItem tone="danger" label="Unsupported / conflict" />
        <LegendItem tone="info" label="Unchecked" />
      </div>
      <div className="review-tabs">
        {tabItems.map((tab) => (
          <button
            type="button"
            key={tab.key}
            className={activeTab === tab.key ? "active" : ""}
            onClick={() => setActiveTab(tab.key)}
          >
            <span>{tab.label}</span>
            <Badge tone={tab.key === "unsupported" && tab.count ? "danger" : "info"}>{tab.count}</Badge>
          </button>
        ))}
      </div>
      {activeTab === "citations" && (
        <div className="review-tab-panel">
          {!citations.length && <EmptyState title="No citations attached yet." message="Generate or load a summary to review evidence." />}
          {citations.map((citation, index) => (
            <button
              type="button"
              className={`citation-card ${citation.citation_id === currentCitationId ? "selected" : ""}`}
              key={citation.citation_id}
              onMouseEnter={() => onHoverCitation?.(citation.citation_id)}
              onMouseLeave={() => onHoverCitation?.("")}
              onFocus={() => onHoverCitation?.(citation.citation_id)}
              onBlur={() => onHoverCitation?.("")}
              onClick={() => onSelectCitation(citation.citation_id, citation.claim_id)}
            >
              <Badge tone="info">{citation.citation_label || `C${index + 1}`}</Badge>
              <strong>{citation.source_type || citation.source_record_type || "Source"}</strong>
              <span>{citation.claim_text || "Supported claim unavailable."}</span>
              <small>{citation.source_text_span || citation.surrounding_context || "Evidence excerpt unavailable."}</small>
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
              className={`claim-review-card ${claim.claim_id === (activeClaimId || selectedClaimId) ? "selected" : ""}`}
              key={claim.claim_id}
              onClick={() => onSelectClaim(claim.claim_id)}
            >
              <Badge tone={statusTone(claim.support_status)}>{claim.support_status || "needs review"}</Badge>
              <span>{claim.claim_text}</span>
              <small>{claim.claim_type || "general"} - {claim.citations?.length ? `${claim.citations.length} evidence link(s)` : "No evidence link attached."}</small>
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
              className={`claim-review-card needs-review ${claim.claim_id === (activeClaimId || selectedClaimId) ? "selected" : ""}`}
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

function SelectedCitationDetail({ citation, claim }) {
  if (!citation && !claim) {
    return (
      <div className="selected-citation-detail empty">
        <strong>No citation selected</strong>
        <p>Hover or click a citation chip, evidence card, or claim to inspect linked source evidence.</p>
      </div>
    );
  }
  const excerpt = citation?.source_text_span || citation?.surrounding_context || "Evidence excerpt unavailable.";
  return (
    <div className={`selected-citation-detail ${claim?.support_status !== "supported" ? "needs-review" : ""}`}>
      <div>
        <Badge tone={statusTone(claim?.support_status || citation?.claim_status)}>{claim?.support_status || citation?.claim_status || "unchecked"}</Badge>
        <strong>{citation?.source_type || citation?.source_record_type || "Source evidence"}</strong>
      </div>
      {claim?.claim_text && <p><span>Claim</span>{claim.claim_text}</p>}
      <p><span>Evidence excerpt</span>{excerpt}</p>
    </div>
  );
}

function LegendItem({ tone, label }) {
  return (
    <span>
      <Badge tone={tone}>{label}</Badge>
    </span>
  );
}
