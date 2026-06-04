import EmptyState from "../common/EmptyState.jsx";
import PatientCard from "./PatientCard.jsx";

export default function PatientList({ patients }) {
  if (!patients?.length) return <EmptyState title="No patients found" message="Seed demo data or import de-identified records." />;
  return <div className="patient-grid">{patients.map((patient) => <PatientCard key={patient.patient_id} patient={patient} />)}</div>;
}
