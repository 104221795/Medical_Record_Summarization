import { useState } from "react";
import Card from "../common/Card.jsx";
import Button from "../common/Button.jsx";
import SummaryProviderSelector from "./SummaryProviderSelector.jsx";
import SummaryEditor from "./SummaryEditor.jsx";
import CitationPanel from "./CitationPanel.jsx";
import ClaimValidationPanel from "./ClaimValidationPanel.jsx";
import UnsupportedClaimsPanel from "./UnsupportedClaimsPanel.jsx";
import ReviewActions from "./ReviewActions.jsx";
import { useSummary } from "../../hooks/useSummary.js";

export default function SummaryWorkspace({ patientId, encounters = [], documents = [] }) {
  const [provider, setProvider] = useState("deterministic");
  const [encounterId, setEncounterId] = useState("");
  const [editedText, setEditedText] = useState("");
  const { summary, generate, load, loading, error } = useSummary();

  const generateDraft = async () => {
    const result = await generate(patientId, {
      encounter_id: encounterId || null,
      summary_type: "patient_snapshot",
      language: "vi",
      model_provider: provider,
    });
    setEditedText(result.summary_text);
  };

  const refreshAfterReview = async (result) => {
    const summaryId = result?.summary_id || summary?.summary_id;
    if (!summaryId) return null;
    const detail = await load(summaryId);
    setEditedText(detail.latest_edited_summary_text || detail.summary_text || editedText);
    return detail;
  };

  return (
    <div className="review-workspace">
      <Card title="Source Record" className="source-panel">
        <div className="filter-row">
          {["Diagnosis", "Medication", "Timeline", "Assessment", "Plan"].map((label) => <span className="badge info" key={label}>{label}</span>)}
        </div>
        <SourceContext documents={documents} summary={summary} />
      </Card>
      <Card title="Generated Draft">
        <div className="form-grid">
          <SummaryProviderSelector value={provider} onChange={setProvider} />
          <label className="field"><span>Encounter</span><select value={encounterId} onChange={(e) => setEncounterId(e.target.value)}><option value="">All encounters</option>{encounters.map((enc) => <option value={enc.encounter_id} key={enc.encounter_id}>{enc.encounter_type || enc.encounter_id}</option>)}</select></label>
          <label className="field"><span>Load summary by ID</span><input onBlur={(e) => e.target.value && load(e.target.value)} placeholder="summary UUID" /></label>
        </div>
        <Button onClick={generateDraft} disabled={!patientId || loading}>{loading ? "Generating..." : "Generate Draft"}</Button>
        {error && <p className="error-text">{error.message}</p>}
        {summary && (
          <div className="summary-meta">
            <span className="badge info">{summary.model_provider || "provider unknown"}</span>
            <span className="badge">{summary.status}</span>
            <span>{summary.generated_at ? new Date(summary.generated_at).toLocaleString() : ""}</span>
          </div>
        )}
        <SummaryEditor summary={summary} value={editedText} onChange={setEditedText} />
      </Card>
      <div className="stack">
        <CitationPanel summary={summary} />
        <ClaimValidationPanel summary={summary} />
        <UnsupportedClaimsPanel summary={summary} />
        <ReviewActions summary={summary} editedText={editedText} onUpdated={refreshAfterReview} />
      </div>
    </div>
  );
}

function SourceContext({ documents, summary }) {
  const citationTexts = summary?.sections?.flatMap((section) =>
    section.claims?.flatMap((claim) => claim.citations?.map((citation) => citation.source_text_span).filter(Boolean) || []) || [],
  ) || [];
  const snippets = citationTexts.length
    ? citationTexts
    : documents.map((document) => document.raw_text || document.document_title || document.document_type).filter(Boolean);
  if (!snippets.length) {
    return <p className="muted">No source text loaded yet. Open a patient detail page or load a generated summary to inspect evidence.</p>;
  }
  return (
    <div className="source-list">
      {snippets.slice(0, 8).map((text, index) => (
        <article className="source-card" key={`${index}-${text.slice(0, 12)}`}>
          <span className="citation-id">EV-{index + 1}</span>
          <p>{text}</p>
        </article>
      ))}
    </div>
  );
}
