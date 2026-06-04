import { Link } from "react-router-dom";
import Badge from "../common/Badge.jsx";

export default function PatientCard({ patient }) {
  return (
    <article className="patient-card">
      <div>
        <strong>{patient.external_patient_id || patient.patient_hash || patient.patient_id}</strong>
        <p>{patient.gender || "gender unknown"}</p>
      </div>
      <Badge tone={patient.is_deidentified ? "success" : "warning"}>{patient.is_deidentified ? "de-identified" : "sensitive"}</Badge>
      <div className="patient-card-actions">
        <Link className="btn secondary" to={`/doctor/patients/${patient.patient_id}`}>Open Detail</Link>
        <Link className="btn ghost" to={`/doctor/generate-summary?patientId=${patient.patient_id}`}>Generate</Link>
      </div>
    </article>
  );
}
