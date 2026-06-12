import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Card from "../../components/common/Card.jsx";
import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import CitationReviewPanel from "../../components/summary/CitationReviewPanel.jsx";
import ReviewActionBar from "../../components/summary/ReviewActionBar.jsx";
import ReviewContextBar from "../../components/summary/ReviewContextBar.jsx";
import ReviewOutcomePanel from "../../components/summary/ReviewOutcomePanel.jsx";
import SourceEvidencePanel from "../../components/summary/SourceEvidencePanel.jsx";
import SummaryQualityPanel from "../../components/summary/SummaryQualityPanel.jsx";
import SummaryEditorPanel from "../../components/summary/SummaryEditorPanel.jsx";
import { useCitationSelection } from "../../hooks/useCitationSelection.js";
import { useRole } from "../../hooks/useRole.js";
import { useReviewWorkflow } from "../../hooks/useReviewWorkflow.js";

export default function DoctorReviewEvidencePage() {
  const { summaryId } = useParams();
  const navigate = useNavigate();
  const { session } = useRole();
  const [manualSummaryId, setManualSummaryId] = useState("");
  const [mobilePanel, setMobilePanel] = useState("source");
  const workflow = useReviewWorkflow(summaryId);
  const citationState = useCitationSelection(workflow.summary);

  const loadManualSummary = () => {
    const trimmed = manualSummaryId.trim();
    if (trimmed) navigate(`/doctor/review/${trimmed}`);
  };

  if (!summaryId) {
    return (
      <div className="doctor-golden-page">
        <PageHeader
          eyebrow="Clinical evidence review"
          title="Review & Evidence"
          description="Load a generated summary to inspect citations, edit the draft, and approve or reject it."
        />
        <Card title="Load Summary">
          <div className="load-summary-row">
            <label className="field">
              <span>Summary ID</span>
              <input value={manualSummaryId} onChange={(event) => setManualSummaryId(event.target.value)} placeholder="Paste generated summary UUID" />
            </label>
            <button className="btn" type="button" onClick={loadManualSummary}>Load Review Workspace</button>
          </div>
        </Card>
      </div>
    );
  }

  if (workflow.loading) return <LoadingState label="Loading summary evidence..." />;
  if (workflow.error) return <ErrorState error={workflow.error} />;

  return (
    <div className="doctor-golden-page review-evidence-page">
      <PageHeader
        eyebrow="Clinical evidence review"
        title="Review & Evidence"
        description="Compare source evidence against the generated draft before editing, approval, or rejection."
      />
      <div className="review-top-area">
        <ReviewContextBar summary={workflow.summary} patient={workflow.patient} />
        <SummaryQualityPanel summary={workflow.summary} />
      </div>
      <div className={`review-zone actions-zone ${mobilePanel === "actions" ? "mobile-active" : ""}`}>
        <ReviewActionBar
          summary={workflow.summary}
          busyAction={workflow.busyAction}
          toast={workflow.toast}
          onStartReview={workflow.startReview}
          onSaveEdit={workflow.saveEdit}
          onApprove={workflow.approve}
          onReject={workflow.reject}
        />
      </div>
      <ReviewOutcomePanel outcome={workflow.lastOutcome} reviewer={session.fullName || session.email || session.userId} />
      <div className="mobile-review-tabs">
        {[
          ["source", "Source"],
          ["summary", "Summary"],
          ["evidence", "Evidence"],
          ["actions", "Actions"],
        ].map(([key, label]) => (
          <button
            type="button"
            key={key}
            className={mobilePanel === key ? "active" : ""}
            onClick={() => setMobilePanel(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="review-evidence-grid">
        <div className={`review-zone source-zone ${mobilePanel === "source" ? "mobile-active" : ""}`}>
          <SourceEvidencePanel
            summary={workflow.summary}
            documents={workflow.documents}
            citations={citationState.citations}
            selectedCitationId={citationState.selectedCitationId}
            hoveredCitationId={citationState.hoveredCitationId}
            activeCitationId={citationState.activeCitationId}
            onSelectCitation={citationState.selectCitation}
            onHoverCitation={citationState.setHoveredCitationId}
          />
        </div>
        <div className={`review-zone summary-zone ${mobilePanel === "summary" ? "mobile-active" : ""}`}>
          <SummaryEditorPanel
            summary={workflow.summary}
            editedText={workflow.editedText}
            setEditedText={workflow.setEditedText}
            citations={citationState.citations}
            selectedCitationId={citationState.selectedCitationId}
            hoveredCitationId={citationState.hoveredCitationId}
            activeCitationId={citationState.activeCitationId}
            selectedClaimId={citationState.selectedClaimId}
            activeClaimId={citationState.activeClaimId}
            onSelectCitation={citationState.selectCitation}
            onSelectClaim={citationState.selectClaim}
            onHoverCitation={citationState.setHoveredCitationId}
            onSave={workflow.saveEdit}
            saving={workflow.busyAction === "edit"}
          />
        </div>
        <div className={`review-zone evidence-zone ${mobilePanel === "evidence" ? "mobile-active" : ""}`}>
          <CitationReviewPanel
            citations={citationState.citations}
            claims={citationState.claims}
            selectedCitationId={citationState.selectedCitationId}
            hoveredCitationId={citationState.hoveredCitationId}
            activeCitationId={citationState.activeCitationId}
            selectedCitation={citationState.activeCitation || citationState.selectedCitation}
            selectedClaim={citationState.selectedClaim}
            selectedClaimId={citationState.selectedClaimId}
            activeClaimId={citationState.activeClaimId}
            onSelectCitation={citationState.selectCitation}
            onHoverCitation={citationState.setHoveredCitationId}
            onSelectClaim={citationState.selectClaim}
          />
        </div>
      </div>
    </div>
  );
}
