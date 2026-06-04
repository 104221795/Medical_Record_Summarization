import Card from "../../components/common/Card.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import SummaryWorkspace from "../../components/summary/SummaryWorkspace.jsx";

export default function SummaryReviewPage() {
  return (
    <div className="stack">
      <PageHeader
        eyebrow="Human-in-the-loop"
        title="Summary Review"
        description="Generate, inspect, edit, approve, or reject AI draft summaries with citation evidence visible."
      />
      <Card title="Workspace Context">
        <p className="muted">Open a patient from the Patients page for full context, or load a summary ID inside the workspace.</p>
      </Card>
      <SummaryWorkspace />
    </div>
  );
}
