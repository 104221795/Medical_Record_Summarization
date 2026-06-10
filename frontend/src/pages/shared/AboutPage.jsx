import { Link } from "react-router-dom";
import { ArrowRight, Database, FileCheck2, Home, ShieldCheck, Stethoscope, UserPlus } from "lucide-react";
import Card from "../../components/common/Card.jsx";
import Button from "../../components/common/Button.jsx";
import PublicNav from "../../components/navigation/PublicNav.jsx";
import { brandAssets } from "../../assets/branding.js";

export default function AboutPage() {
  return (
    <main className="public-page about-page">
      <PublicNav />
      <section className="about-hero">
        <div className="about-hero-copy">
          <img src={brandAssets.logo} alt="Medical Record Summarization logo" />
          <p className="eyebrow">Mission</p>
          <h1>Clinical summaries that stay inspectable, governed, and human-approved.</h1>
          <p>This platform is designed for citation-grounded medical record summarization research and MVP validation. It separates draft generation from clinician approval and keeps proxy evaluation clearly labeled.</p>
        </div>
        <div className="about-hero-visual about-medical-visual" style={{ "--thumbnail-image": `url(${brandAssets.aboutHero})` }}>
          <div className="about-visual-card primary">
            <span><Stethoscope aria-hidden="true" size={16} /> Clinical Context</span>
            <strong>Diagnosis, medications, timeline, assessment, and plan</strong>
          </div>
          <div className="about-visual-card">
            <span><FileCheck2 aria-hidden="true" size={16} /> Citation Review</span>
            <small>Unsupported claims stay visible for clinician review.</small>
          </div>
          <div className="about-visual-row">
            <span><Database aria-hidden="true" size={15} /> Dataset governance</span>
            <span><ShieldCheck aria-hidden="true" size={15} /> Audit-ready</span>
          </div>
        </div>
      </section>
      <div className="about-grid">
        <Card title="Objectives">
          <p>Reduce record review friction, preserve evidence traceability, support doctor review, and make model comparisons transparent before medium or large-scale benchmarking.</p>
        </Card>
        <Card title="Architecture">
          <p>FHIR-like ingestion, retrieval, provider-selectable generation, citation safety checks, human review, audit logs, PostgreSQL-ready persistence, and admin evaluation dashboards.</p>
        </Card>
        <Card title="Dataset Layers">
          <p>Synthea/SyntheticMass validate ingestion. MultiClinSum powers proxy summarization benchmarking. MTS-Dialog and MEDIQA-Sum are planned cross-dataset checks. MIMIC access remains future governed work.</p>
        </Card>
        <Card title="Governance">
          <p className="warning-line">Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, or real-world healthcare performance.</p>
        </Card>
      </div>
      <section className="public-section">
        <div className="section-copy"><h2>Doctor Workflow</h2><p>Generate a draft, start review, inspect citations, edit, approve or reject, and keep the action history visible.</p></div>
        <div className="section-copy"><h2>Admin Workflow</h2><p>Inspect provider readiness, benchmark outputs, dataset governance, model domain fit, and operational metrics.</p></div>
      </section>
      <section className="public-section">
        <div className="visual-panel" style={{ "--panel-image": `url(${brandAssets.images[2]})` }}><span>Evidence and review workflow</span></div>
        <div className="visual-panel" style={{ "--panel-image": `url(${brandAssets.images[3]})` }}><span>Governed benchmark operations</span></div>
      </section>
      <div className="public-actions">
        <Link to="/login"><Button icon={ArrowRight} iconPosition="right">Sign In</Button></Link>
        <Link to="/signup"><Button variant="secondary" icon={UserPlus}>Sign Up</Button></Link>
        <Link to="/"><Button variant="secondary" icon={Home}>Home</Button></Link>
      </div>
    </main>
  );
}
