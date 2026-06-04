import { Link, useParams } from "react-router-dom";
import Button from "../../components/common/Button.jsx";
import Card from "../../components/common/Card.jsx";
import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import ClinicalTimeline from "../../components/patient/ClinicalTimeline.jsx";
import DocumentViewer from "../../components/patient/DocumentViewer.jsx";
import PatientDetailHeader from "../../components/patient/PatientDetailHeader.jsx";
import PatientSummaryHistoryTable from "../../components/summary/PatientSummaryHistoryTable.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import { usePatientHistory } from "../../hooks/usePatientHistory.js";
import { usePatientContext } from "../../hooks/usePatients.js";

export default function PatientDetailPage() {
  const { patientId } = useParams();
  const { data, loading, error } = usePatientContext(patientId);
  const { rows: historyRows } = usePatientHistory();
  const patientHistory = historyRows.filter((row) => row.patient_id === patientId);
  const latestSummary = patientHistory[0];
  if (loading) return <LoadingState label="Loading patient context..." />;
  if (error) return <ErrorState error={error} />;
  return (
    <div className="stack">
      <PageHeader
        eyebrow="Patient detail"
        title="Patient Context"
        description="Review profile, encounters, source documents, and summary history before generation or evidence review."
      />
      <PatientDetailHeader patient={data?.patient} />
      <Card title="Quick Actions">
        <div className="quick-action-row">
          <Link to={`/doctor/generate-summary?patientId=${patientId}`}>
            <Button>Generate New Summary</Button>
          </Link>
          {latestSummary ? (
            <Link to={`/doctor/review/${latestSummary.summary_id}`}>
              <Button variant="secondary">Review Latest Summary</Button>
            </Link>
          ) : (
            <Button variant="secondary" disabled>Review Latest Summary</Button>
          )}
        </div>
      </Card>
      <div className="grid-two"><ClinicalTimeline encounters={data?.encounters} /><DocumentViewer documents={data?.documents} /></div>
      <Card title="Previous Summaries">
        <PatientSummaryHistoryTable rows={patientHistory.slice(0, 6)} />
      </Card>
    </div>
  );
}
