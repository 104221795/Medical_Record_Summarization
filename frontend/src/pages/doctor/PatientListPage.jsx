import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import PatientList from "../../components/patient/PatientList.jsx";
import { usePatients } from "../../hooks/usePatients.js";

export default function PatientListPage() {
  const { data, loading, error } = usePatients();
  if (loading) return <LoadingState label="Loading patients..." />;
  if (error) return <ErrorState error={error} />;
  return (
    <div className="doctor-golden-page">
      <PageHeader
        eyebrow="Clinical context"
        title="Patients"
        description="Open a patient profile before generating a summary or reviewing evidence."
      />
      <PatientList patients={data?.items || []} />
    </div>
  );
}
