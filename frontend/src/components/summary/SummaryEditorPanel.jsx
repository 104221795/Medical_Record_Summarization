import { useEffect, useRef, useState } from "react";
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
  hoveredCitationId,
  activeCitationId,
  selectedClaimId,
  activeClaimId,
  onSelectCitation,
  onSelectClaim,
  onHoverCitation,
  onSave,
  saving,
}) {
  const [editing, setEditing] = useState(false);
  return (
    <Card
      title="Generated Summary"
      className="summary-editor-panel"
      actions={summary?.status && <Badge tone={statusTone(summary.status)}>{summary.status}</Badge>}
    >
      <div className="summary-review-toolbar">
        <p className="muted">Compact clinical brief. Open sections only when reviewing details.</p>
        <Button variant="secondary" onClick={() => setEditing((value) => !value)}>
          {editing ? "Back to Review" : "Edit Draft"}
        </Button>
      </div>
      {!editing ? (
        <ClinicalSectionRenderer
          summary={summary}
          fallbackText={editedText || summary?.summary_text || ""}
          selectedCitationId={selectedCitationId}
          hoveredCitationId={hoveredCitationId}
          activeCitationId={activeCitationId}
          selectedClaimId={selectedClaimId}
          activeClaimId={activeClaimId}
          onSelectCitation={onSelectCitation}
          onSelectClaim={onSelectClaim}
          onHoverCitation={onHoverCitation}
        />
      ) : (
        <div className="summary-edit-mode">
          <TextArea
            label="Editable summary"
            rows={10}
            value={editedText}
            onChange={(event) => setEditedText(event.target.value)}
            placeholder="Load or generate a summary before editing."
          />
          <Button variant="secondary" disabled={!summary || saving} onClick={onSave}>
            {saving ? "Saving..." : "Save Edit"}
          </Button>
        </div>
      )}
      <div className="summary-version-row compact">
        <span>Version {summary?.version_number || 1}</span>
        <span>{summary?.citation_coverage != null ? `Citation coverage ${summary.citation_coverage}` : "Citation coverage unavailable"}</span>
        <span>{summary?.unsupported_claim_count ?? 0} unsupported claims</span>
      </div>
    </Card>
  );
}

function ClinicalSectionRenderer({
  summary,
  fallbackText = "",
  selectedCitationId,
  hoveredCitationId,
  activeCitationId,
  selectedClaimId,
  activeClaimId,
  onSelectCitation,
  onSelectClaim,
  onHoverCitation,
}) {
  const claimRefs = useRef({});
  const [expandedSections, setExpandedSections] = useState(new Set());
  const currentClaimId = activeClaimId || claimIdForCitation(summary, activeCitationId || hoveredCitationId || selectedCitationId) || selectedClaimId;
  useEffect(() => {
    if (!currentClaimId) return;
    claimRefs.current[currentClaimId]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [currentClaimId]);

  const sections = summary?.sections?.length ? summary.sections : parsePlainSummarySections(fallbackText);

  if (!sections.length) {
    return <p className="muted">Load or generate a summary to review structured claims.</p>;
  }

  return (
    <div className="clinical-section-renderer">
      {sections.map((section, index) => {
        const sectionKey = section.section_id || section.section_title || `section-${index}`;
        const sectionHasActiveClaim = (section.claims || []).some((claim) => claim.claim_id === currentClaimId);
        const open = expandedSections.has(sectionKey) || sectionHasActiveClaim || (!expandedSections.size && !currentClaimId && index === 0);
        const claims = section.claims || [];
        const visibleClaims = open ? claims : claims.slice(0, 1);
        return (
        <section className={`clinical-summary-section ${open ? "open" : "collapsed"}`} key={sectionKey}>
          <div className="clinical-section-heading">
            <h3>{section.section_title || "Generated Section"}</h3>
            <div className="section-heading-actions">
              <Badge tone={claims.some((claim) => claim.support_status !== "supported") ? "warning" : "info"}>{claims.length || 0} claims</Badge>
              <button
                type="button"
                className="section-toggle"
                onClick={() => setExpandedSections((current) => toggleSection(current, sectionKey))}
              >
                {open ? "Collapse" : "Open"}
              </button>
            </div>
          </div>
          <div className="clinical-claim-list">
            {claims.length ? visibleClaims.map((claim) => {
              const active = claim.claim_id === currentClaimId;
              return (
                <article
                  key={claim.claim_id}
                  ref={(node) => { if (node) claimRefs.current[claim.claim_id] = node; }}
                  className={`summary-claim-block ${claim.support_status !== "supported" ? "needs-review" : ""} ${active ? "selected" : ""}`}
                  onMouseEnter={() => onSelectClaim?.(claim.claim_id)}
                  onFocus={() => onSelectClaim?.(claim.claim_id)}
                >
                  <button type="button" className="summary-claim-text" onClick={() => onSelectClaim?.(claim.claim_id)}>
                    {claim.claim_text}
                  </button>
                  <div className="summary-claim-meta">
                    <Badge tone={statusTone(claim.support_status)}>{claim.support_status || "unchecked"}</Badge>
                    <span>{claim.claim_type || "general"}</span>
                    <span>{claim.clinical_risk_level ? `risk ${claim.clinical_risk_level}` : "risk n/a"}</span>
                  </div>
                  <div className="inline-citation-row">
                    {claim.citations?.length ? claim.citations.map((citation, index) => (
                      <CitationChip
                        key={citation.citation_id}
                        citation={{ ...citation, claim_text: claim.claim_text, claim_status: claim.support_status, claim_type: claim.claim_type }}
                        label={`C${index + 1}`}
                        active={(activeCitationId || hoveredCitationId || selectedCitationId) === citation.citation_id}
                        onClick={() => onSelectCitation(citation.citation_id, claim.claim_id)}
                        onHover={(citationId) => onHoverCitation?.(citationId)}
                      />
                    )) : <span className="no-citation-note">No citation attached</span>}
                  </div>
                </article>
              );
            }) : <p className="muted">{section.section_text || "No claims in this section."}</p>}
            {!open && claims.length > 1 && (
              <button type="button" className="show-more-claims" onClick={() => setExpandedSections((current) => toggleSection(current, sectionKey))}>
                Show {claims.length - 1} more claim(s)
              </button>
            )}
          </div>
        </section>
        );
      })}
    </div>
  );
}

function CitationChip({ citation, label, active, onClick, onHover }) {
  const excerpt = citation.source_text_span || citation.surrounding_context || citation.source_type || "Evidence span unavailable";
  return (
    <button
      type="button"
      className={`citation-chip ${active ? "active" : ""}`}
      onClick={onClick}
      onMouseEnter={() => onHover?.(citation.citation_id)}
      onMouseLeave={() => onHover?.("")}
      onFocus={() => onHover?.(citation.citation_id)}
      onBlur={() => onHover?.("")}
      aria-label={`Select citation ${label}`}
    >
      <strong>{label}</strong>
      <span>{citation.source_type || citation.source_record_type || "Evidence"}</span>
      <span className="citation-popover" role="tooltip">
        <b>{label}</b>
        <em>{citation.source_type || citation.source_record_type || "source"} - {citation.claim_status || "unchecked"}</em>
        {citation.claim_text && <small><strong>Claim:</strong> {citation.claim_text}</small>}
        <small>{excerpt}</small>
      </span>
    </button>
  );
}

function claimIdForCitation(summary, citationId) {
  if (!citationId) return "";
  const claims = summary?.sections?.flatMap((section) => section.claims || []) || [];
  return claims.find((claim) => claim.citations?.some((citation) => citation.citation_id === citationId))?.claim_id || "";
}

function toggleSection(current, sectionKey) {
  const next = new Set(current);
  if (next.has(sectionKey)) next.delete(sectionKey);
  else next.add(sectionKey);
  return next;
}

function parsePlainSummarySections(text = "") {
  const normalized = String(text || "").trim();
  if (!normalized) return [];
  const knownHeadings = [
    "Patient Snapshot",
    "Active Problems",
    "Recent Clinical Course",
    "Medications",
    "Labs and Imaging Highlights",
    "Needs Clinician Review",
    "Diagnosis Evidence",
    "Medication Evidence",
    "Timeline Evidence",
    "Diagnostics Evidence",
    "Assessment Evidence",
    "Plan Evidence",
    "Unknown / Missing Evidence",
  ];
  const escaped = knownHeadings.map((heading) => heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const headingPattern = new RegExp(`^\\s*\\[?(${escaped})\\]?\\s*:?\\s*$`, "i");
  const sections = [];
  let current = { section_title: "Generated Summary", section_text: "" };

  normalized.split(/\r?\n/).forEach((line) => {
    const heading = line.match(headingPattern)?.[1];
    if (heading) {
      if (current.section_text.trim()) sections.push(current);
      current = { section_title: heading, section_text: "" };
      return;
    }
    current.section_text += `${line}\n`;
  });
  if (current.section_text.trim()) sections.push(current);
  return sections.map((section, index) => ({
    section_id: `plain-section-${index + 1}`,
    section_title: section.section_title,
    section_text: section.section_text.trim(),
    claims: [],
  }));
}
