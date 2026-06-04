import { Link } from "react-router-dom";
import Card from "../../components/common/Card.jsx";
import Button from "../../components/common/Button.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";

export default function DoctorDashboardPage() {
  return (
    <div className="doctor-golden-page">
      <PageHeader
        eyebrow="Doctor workspace"
        title="Golden Path"
        description="Choose a patient, generate a draft, inspect evidence, then edit, approve, or reject with audit history preserved."
      />
      <div className="golden-step-grid">
        <Card title="1. Select Patient">
          <p>Review patient profile, encounters, and source documents before generation.</p>
          <Link to="/doctor/patients"><Button variant="secondary">Open Patients</Button></Link>
        </Card>
        <Card title="2. Generate Summary">
          <p>Create a draft using deterministic, Gemini, BART, or Pegasus provider options.</p>
          <Link to="/doctor/generate-summary"><Button>Generate Summary</Button></Link>
        </Card>
        <Card title="3. Review Evidence">
          <p>Compare source evidence with the generated summary before approval or rejection.</p>
          <Link to="/doctor/review"><Button variant="secondary">Review & Evidence</Button></Link>
        </Card>
        <Card title="4. Track History">
          <p>See saved summary history and doctor actions from the audit trail.</p>
          <Link to="/doctor/patient-history"><Button variant="ghost">Patient History</Button></Link>
        </Card>
      </div>
      <Card title="Safety Reminder">
        <p>AI summaries are drafts until approved by an authorized doctor. Unsupported evidence remains visible for review.</p>
      </Card>
    </div>
  );
}
