import { BookOpen, CheckCircle2, ClipboardCheck, FileText, Search, ShieldCheck } from "lucide-react";
import Badge from "../../components/common/Badge.jsx";
import Card from "../../components/common/Card.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";

const workflowSteps = [
  ["1", "Select Patient", "Open Patients, inspect profile, encounters, and source documents.", Search],
  ["2", "Generate Summary", "Choose a provider and create a draft only. Do not approve from this page.", FileText],
  ["3", "Review Evidence", "Compare source evidence, editable summary, citations, and claim status.", ShieldCheck],
  ["4", "Decide", "Start review, save edits, then approve or reject with audit history preserved.", ClipboardCheck],
];

const providers = [
  ["Deterministic", "Fast extractive baseline", "Local"],
  ["Qwen2.5 / Llama3.2", "Local Ollama testing providers for RAG-style strict prompts", "Testing"],
  ["Gemini 2.5 Flash Lite", "Gateway API provider; use only with approved governed data", "API"],
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
        description="A one-minute guide for generating draft summaries and completing evidence-first doctor review."
      />
      <section className="guide-hero-card">
        <BookOpen aria-hidden="true" className="ui-icon" size={26} strokeWidth={2.2} />
        <div>
          <h2>Use the system as a draft-and-review workspace.</h2>
          <p>Generate drafts, verify citations, resolve unsupported claims, then decide. Never treat generated output as final until doctor approval.</p>
        </div>
      </section>
      <div className="guide-step-grid">
        {workflowSteps.map(([number, title, text, Icon]) => (
          <article className="guide-step-card" key={title}>
            <div>
              <span>{number}</span>
              <Icon aria-hidden="true" className="ui-icon" size={21} strokeWidth={2.2} />
            </div>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
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
      <Card title="Claim Statuses">
        <div className="guide-status-grid">
          <StatusExplainer tone="success" label="Supported" text="The claim has linked evidence and can be considered during review." />
          <StatusExplainer tone="warning" label="Needs Review" text="Evidence is weak, missing, or requires clinician inspection before approval." />
          <StatusExplainer tone="danger" label="Unsupported" text="Do not approve until resolved or rejected." />
          <StatusExplainer tone="info" label="Unchecked" text="No final support decision has been made yet." />
        </div>
      </Card>
      <Card title="Provider Meanings">
        <div className="provider-guide-grid">
          {providers.map(([name, description, type]) => (
            <div key={name}>
              <strong>{name}</strong>
              <Badge tone={type === "API" || type === "Testing" ? "warning" : "info"}>{type}</Badge>
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
        <div className="guide-troubleshooting-list">
          {troubleshooting.map(([title, text]) => (
            <section key={title}><CheckCircle2 aria-hidden="true" className="ui-icon" size={18} strokeWidth={2.2} /><div><h3>{title}</h3><p>{text}</p></div></section>
          ))}
        </div>
      </Card>
    </div>
  );
}

function StatusExplainer({ tone, label, text }) {
  return (
    <div>
      <Badge tone={tone}>{label}</Badge>
      <p>{text}</p>
    </div>
  );
}
