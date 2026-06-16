import { useEffect, useRef } from "react";
import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import EmptyState from "../common/EmptyState.jsx";

const sectionLabels = ["Diagnosis", "Medication", "Timeline", "Diagnostics", "Assessment", "Plan", "Unknown/Missing"];

export default function SourceEvidencePanel({
  summary,
  documents = [],
  citations = [],
  selectedCitationId,
  hoveredCitationId,
  activeCitationId,
  onSelectCitation,
  onHoverCitation,
}) {
  const evidenceRefs = useRef({});
  const activeId = activeCitationId || hoveredCitationId || selectedCitationId;
  useEffect(() => {
    if (!activeId) return;
    evidenceRefs.current[activeId]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeId]);

  const fallbackEvidence = documents.map((document, index) => ({
    citation_id: `document-${document.document_id || index}`,
    source_type: document.document_type || "document",
    source_text_span: document.raw_text || document.document_title || document.document_type,
    source_metadata: document.department || document.source_system || "clinical document",
    exactSpan: false,
  }));
  const evidence = citations.length
    ? citations.map((citation, index) => ({
      ...citation,
      citationLabel: citation.citation_label || `C${index + 1}`,
      category: evidenceCategory(citation),
      exactSpan: Boolean(citation.source_text_span),
      source_text_span: citation.source_text_span || citation.surrounding_context || "Exact span unavailable; showing source chunk.",
    }))
    : fallbackEvidence.map((item) => ({ ...item, category: "Unknown/Missing", citationLabel: "SRC" }));
  const grouped = sectionLabels
    .map((label) => ({ label, items: evidence.filter((item) => item.category === label) }))
    .filter((group) => group.items.length);

  return (
    <Card title="Source Evidence Explorer" className="evidence-panel">
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
        {grouped.map((group) => (
          <section className="evidence-category-group" key={group.label}>
            <div className="evidence-category-title">
              <strong>{group.label}</strong>
              <span>{group.items.length} item(s)</span>
            </div>
            {group.items.map((item, index) => {
              const citationId = item.citation_id || `evidence-${group.label}-${index}`;
              const active = citationId === activeId;
              return (
                <button
                  type="button"
                  key={citationId}
                  ref={(node) => { if (node) evidenceRefs.current[citationId] = node; }}
                  className={`evidence-card ${active ? "selected" : ""}`}
                  onMouseEnter={() => onHoverCitation?.(citationId)}
                  onMouseLeave={() => onHoverCitation?.("")}
                  onFocus={() => onHoverCitation?.(citationId)}
                  onBlur={() => onHoverCitation?.("")}
                  onClick={() => onSelectCitation?.(citationId, item.claim_id)}
                >
                  <span className="evidence-card-top">
                    <Badge tone={item.claim_status === "supported" ? "success" : statusTone(item.claim_status)}>{item.citationLabel}</Badge>
                    <span>{item.source_type || item.source_record_type || "source"}</span>
                  </span>
                  <p>{item.source_text_span}</p>
                  {!item.exactSpan && <small>Exact span unavailable; showing source chunk.</small>}
                  {item.claim_text && <small>Linked claim: {item.claim_text}</small>}
                  {item.source_metadata && <small>{item.source_metadata}</small>}
                </button>
              );
            })}
          </section>
        ))}
      </div>
      {summary && !citations.length && <p className="muted">No citations attached yet; source documents are shown as fallback context.</p>}
    </Card>
  );
}

function evidenceCategory(item) {
  const text = `${item.claim_text || ""} ${item.source_text_span || ""} ${item.source_type || ""}`.toLowerCase();
  if (item.claim_type === "diagnosis" || includesAny(text, ["diagnosis", "condition", "problem", "cancer", "tumor"])) return "Diagnosis";
  if (item.claim_type === "medication" || includesAny(text, ["medication", "dose", "dosage", "mg", "tablet", "insulin"])) return "Medication";
  if (item.claim_type === "lab_result" || item.claim_type === "imaging_finding" || includesAny(text, ["lab", "ct", "mri", "x-ray", "biopsy", "pathology", "creatinine", "hemoglobin"])) return "Diagnostics";
  if (item.claim_type === "follow_up" || includesAny(text, ["plan", "follow-up", "follow up", "pending", "scheduled"])) return "Plan";
  if (includesAny(text, ["assessment", "impression"])) return "Assessment";
  if (item.claim_type === "timeline_event" || item.claim_type === "encounter_context") return "Timeline";
  return "Unknown/Missing";
}

function statusTone(status = "") {
  const normalized = String(status).toLowerCase();
  if (normalized === "supported") return "success";
  if (normalized === "unsupported" || normalized === "conflicting") return "danger";
  if (normalized.includes("insufficient") || normalized.includes("unchecked")) return "warning";
  return "info";
}

function includesAny(text, terms) {
  return terms.some((term) => text.includes(term));
}
