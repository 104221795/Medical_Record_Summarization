import Badge from "../../components/common/Badge.jsx";
import Card from "../../components/common/Card.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";

const workflowSteps = [
  ["1", "Select Patient", "Open Patients, inspect profile, encounters, and source documents."],
  ["2", "Generate Summary", "Choose a provider and create a draft only. Do not approve from this page."],
  ["3", "Review Evidence", "Compare source evidence, editable summary, citations, and claim status."],
  ["4", "Decide", "Start review, save edits, then approve or reject with audit history preserved."],
];

const providers = [
  ["Deterministic", "Fast extractive baseline", "Local"],
  ["Gemini", "API LLM provider; requires external governance", "API"],
  ["BART", "facebook/bart-large-cnn general summarization baseline", "Local"],
  ["Pegasus PubMed", "google/pegasus-pubmed; better medical/scientific fit", "Local"],
  ["Pegasus CNN/DailyMail", "google/pegasus-cnn_dailymail general baseline", "Local"],
];

const troubleshooting = [
  ["Provider unavailable", "Check provider status, cache paths, and API key governance before retrying."],
  ["No citations", "Use Review & Evidence. If no exact span exists, inspect the displayed source chunk."],
  ["Audit log empty", "Generate/review a summary first. If still empty, backend audit metadata may be unavailable."],
  ["Login/session issue", "Logout clears local session. Sign in again and confirm the badge shows the correct role."],
];

export default function UserGuidePage() {
  return (
    <div className="stack guide-page">
      <PageHeader
        eyebrow="Clinical workflow guide"
        title="Doctor User Guide"
        description="A practical walkthrough for generating evidence-grounded draft summaries and safely completing doctor review."
      />
      <div className="guide-steps">
        {workflowSteps.map(([number, title, text]) => (
          <Card key={title} title={title}>
            <span className="guide-step-icon">{number}</span>
            <p>{text}</p>
          </Card>
        ))}
      </div>
      <div className="grid-two">
        <Card title="Generate Summary Page">
          <p>Select a patient, choose an encounter or all encounters, inspect provider status, then generate a draft. This page should stay focused on draft creation.</p>
          <p className="muted">After generation, click Review Evidence to open the clinical review workspace.</p>
        </Card>
        <Card title="Review & Evidence Page">
          <p>Use the left panel for source evidence, the center panel for editable summary text, and the right panel for citations, claim validation, and unsupported claims.</p>
          <p className="muted">Edit only after checking cited evidence.</p>
        </Card>
      </div>
      <Card title="How to Inspect Citations and Claims">
        <div className="status-grid">
          <div><Badge tone="success">Supported</Badge><p>The claim has linked evidence and can be considered during review.</p></div>
          <div><Badge tone="warning">Needs Review</Badge><p>Evidence is weak, missing, or requires clinician inspection before approval.</p></div>
          <div><Badge tone="danger">Unsupported</Badge><p>Do not approve until the issue is resolved or the summary is rejected.</p></div>
        </div>
      </Card>
      <Card title="Provider Meanings">
        <div className="provider-guide-grid">
          {providers.map(([name, description, type]) => (
            <div key={name}>
              <strong>{name}</strong>
              <Badge tone={type === "API" ? "warning" : "info"}>{type}</Badge>
              <p>{description}</p>
            </div>
          ))}
        </div>
      </Card>
      <Card title="Approve / Reject Safety Notes">
        <p className="warning-line">AI summary must be reviewed before use. The system is a clinical draft workflow, not autonomous diagnosis, treatment, prescription, or discharge approval.</p>
        <p>Approve only after citations and unsupported claims are inspected. Reject when evidence is missing, citation mapping is wrong, or critical information is absent.</p>
      </Card>
      <Card title="Troubleshooting">
        <div className="dataset-layers">
          {troubleshooting.map(([title, text]) => (
            <section key={title}><h3>{title}</h3><p>{text}</p></section>
          ))}
        </div>
      </Card>
    </div>
  );
}
