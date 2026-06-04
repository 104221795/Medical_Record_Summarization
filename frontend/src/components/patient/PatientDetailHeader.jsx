import Badge from "../common/Badge.jsx";
import { patientLabel } from "../../utils/clinicalDisplay.js";

export default function PatientDetailHeader({ patient }) {
  if (!patient) return null;
  return (
    <section className="detail-header">
      <div>
        <p className="eyebrow">Patient profile</p>
        <h2>{patientLabel(patient)}</h2>
        <div className="profile-meta-row">
          <span>ID: {patient.patient_id}</span>
          <span>DOB: {patient.date_of_birth || "not available"}</span>
          <span>Source: {patient.source_system || patient.fhir_patient_id || "local"}</span>
        </div>
      </div>
      <div className="profile-badge-group">
        <Badge tone="info">{patient.gender || "unknown"}</Badge>
        <Badge tone={patient.is_deidentified ? "success" : "warning"}>{patient.is_deidentified ? "de-identified" : "review access"}</Badge>
      </div>
    </section>
  );
}
