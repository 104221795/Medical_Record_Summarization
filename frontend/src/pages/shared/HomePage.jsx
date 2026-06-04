import { Link } from "react-router-dom";
import Button from "../../components/common/Button.jsx";
import PublicNav from "../../components/navigation/PublicNav.jsx";
import { brandAssets } from "../../assets/branding.js";

export default function HomePage() {
  return (
    <main className="public-page">
      <PublicNav />
      <section className="public-hero">
        <div>
          <p className="eyebrow">Evidence-grounded clinical summarization</p>
          <h1>Medical Record Summarization</h1>
          <p>
            A role-based workspace for draft clinical summaries, citation review,
            dataset governance, and controlled proxy evaluation.
          </p>
          <div className="public-actions">
            <Link to="/login"><Button>Open Workspace</Button></Link>
            <Link to="/about"><Button variant="secondary">About</Button></Link>
          </div>
        </div>
      </section>
      <section className="public-section">
        <div className="section-copy">
          <p className="eyebrow">Why It Matters</p>
          <h2>Turn fragmented records into reviewable clinical drafts.</h2>
          <p>Doctors need concise context, evidence, and a safe review workflow. Administrators need benchmark visibility, dataset governance, provider status, and auditability.</p>
        </div>
        <VisualPanel label="Citation-grounded summaries" image={brandAssets.images[0]} />
      </section>
      <section className="feature-grid">
        {[
          ["Citation Evidence", "Every important claim is tied to source context or surfaced for review."],
          ["Human Review", "Drafts move through start review, edit, approve, reject, and audit history."],
          ["Provider Choice", "Compare deterministic, Gemini, BART, and Pegasus variants from one gateway."],
          ["Governed Evaluation", "Proxy benchmarks are separated from real EHR validation requirements."],
        ].map(([title, text]) => <article key={title}><h3>{title}</h3><p>{text}</p></article>)}
      </section>
      <section className="public-section reverse">
        <VisualPanel label="Doctor and admin workspaces" image={brandAssets.images[1]} />
        <div className="section-copy">
          <p className="eyebrow">Role-Based Workflows</p>
          <h2>Focused tools for doctors and administrators.</h2>
          <p>Doctor pages prioritize patient context, summary editing, citation validation, and audit history. Admin pages focus on evaluation, benchmark artifacts, dataset layers, and platform settings.</p>
        </div>
      </section>
      <section className="workflow-band">
        {["Ingest", "Retrieve", "Generate Draft", "Review Evidence", "Approve or Reject", "Audit"].map((step, index) => (
          <div key={step}><span>{index + 1}</span><strong>{step}</strong></div>
        ))}
      </section>
      <section className="public-cta">
        <h2>Build safer summarization habits before real EHR benchmarking.</h2>
        <p>Proxy evaluation only. Real clinical performance requires credentialed datasets and approved governance.</p>
        <Link to="/login"><Button>Login</Button></Link>
      </section>
      <footer className="public-footer">Medical Record Summarization · Clinical drafts require authorized doctor review.</footer>
    </main>
  );
}

function VisualPanel({ label, image }) {
  return <div className="visual-panel" style={{ "--panel-image": `url(${image})` }}><span>{label}</span></div>;
}
