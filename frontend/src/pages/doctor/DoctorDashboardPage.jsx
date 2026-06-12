import { Link } from "react-router-dom";
import { ArrowRight, ClipboardCheck, FileText, History, ShieldCheck, UserRound } from "lucide-react";
import Card from "../../components/common/Card.jsx";
import Button from "../../components/common/Button.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import Badge from "../../components/common/Badge.jsx";

const workflowSteps = [
  {
    number: "01",
    title: "Select Patient",
    description: "Open the worklist and confirm the de-identified patient context before generation.",
    action: "Open Patients",
    to: "/doctor/patients",
    icon: UserRound,
    status: "ready",
  },
  {
    number: "02",
    title: "Generate Draft",
    description: "Choose a testing or baseline provider and create a draft only.",
    action: "Generate Summary",
    to: "/doctor/generate-summary",
    icon: FileText,
    status: "draft only",
  },
  {
    number: "03",
    title: "Review Evidence",
    description: "Inspect citations, unsupported claims, and source evidence before editing.",
    action: "Review Evidence",
    to: "/doctor/review",
    icon: ShieldCheck,
    status: "critical",
  },
  {
    number: "04",
    title: "Finalize / Track",
    description: "Approve, reject, or save edits with audit history preserved.",
    action: "Open History",
    to: "/doctor/patient-history",
    icon: History,
    status: "audit ready",
  },
];

export default function DoctorDashboardPage() {
  return (
    <div className="doctor-golden-page">
      <PageHeader
        eyebrow="Doctor workspace"
        title="Doctor Workflow"
        description="A focused path for evidence-grounded draft summaries: select patient, generate, review evidence, then decide."
      />
      <section className="doctor-workflow-hero">
        <div>
          <Badge tone="info">Evidence-first review</Badge>
          <h2>Move from patient context to final review with citations visible at every step.</h2>
          <p>
            The system creates AI draft summaries only. Doctors verify evidence, resolve unsupported claims,
            and approve or reject through the auditable review workspace.
          </p>
        </div>
        <div className="doctor-next-box">
          <ClipboardCheck aria-hidden="true" className="ui-icon" size={26} strokeWidth={2.2} />
          <span>What to do next</span>
          <strong>Open a patient, generate a draft, then review citation support before any decision.</strong>
          <Link to="/doctor/patients"><Button icon={ArrowRight} iconPosition="right">Start Workflow</Button></Link>
        </div>
      </section>
      <div className="clinical-workflow-steps">
        {workflowSteps.map((step) => <WorkflowStepCard key={step.number} step={step} />)}
      </div>
      <section className="clinical-notice-card">
        <ShieldCheck aria-hidden="true" className="ui-icon" size={20} strokeWidth={2.3} />
        <div>
          <strong>Clinical safety boundary</strong>
          <p>AI summaries are draft-only. Unsupported or conflicting evidence must remain visible until a doctor resolves it.</p>
        </div>
      </section>
    </div>
  );
}

function WorkflowStepCard({ step }) {
  const Icon = step.icon;
  return (
    <article className="clinical-workflow-step">
      <div className="workflow-step-top">
        <span className="workflow-step-number">{step.number}</span>
        <Icon aria-hidden="true" className="ui-icon" size={22} strokeWidth={2.2} />
      </div>
      <h3>{step.title}</h3>
      <p>{step.description}</p>
      <div className="workflow-step-footer">
        <Badge tone={step.status === "critical" ? "warning" : "info"}>{step.status}</Badge>
        <Link to={step.to}><Button variant={step.number === "02" ? "primary" : "secondary"}>{step.action}</Button></Link>
      </div>
    </article>
  );
}
