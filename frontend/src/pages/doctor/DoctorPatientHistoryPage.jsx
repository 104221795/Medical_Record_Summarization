import Card from "../../components/common/Card.jsx";
import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import PatientSummaryHistoryTable from "../../components/summary/PatientSummaryHistoryTable.jsx";
import { usePatientHistory } from "../../hooks/usePatientHistory.js";

export default function DoctorPatientHistoryPage() {
  const { rows, loading, error, reload } = usePatientHistory();
  if (loading) return <LoadingState label="Loading patient summary history..." />;
  if (error) return <ErrorState error={error} />;
  return (
    <div className="doctor-golden-page">
      <PageHeader
        eyebrow="Saved summary history"
        title="Patient History"
        description="Track generated summaries, review status, provider usage, and final doctor actions from audit events."
        actions={<button className="btn secondary" type="button" onClick={reload}>Refresh</button>}
      />
      <Card title="Patient Summary History">
        <PatientSummaryHistoryTable rows={rows} />
        {!rows.length && (
          <p className="muted history-helper">
            If drafts already exist but do not appear here, the backend audit events may be missing summary metadata for list-style history.
          </p>
        )}
      </Card>
    </div>
  );
}
