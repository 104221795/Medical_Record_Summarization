import { Link } from "react-router-dom";
import { ArrowRight, FileText } from "lucide-react";
import Badge from "../common/Badge.jsx";
import Button from "../common/Button.jsx";

export default function PatientCard({ patient }) {
  return (
    <article className="patient-card">
      <div className="patient-card-main">
        <div>
          <span className="patient-card-label">Patient</span>
          <strong>{patient.external_patient_id || patient.patient_hash || patient.patient_id}</strong>
          <p>{patient.patient_id}</p>
        </div>
        <Badge tone={patient.is_deidentified ? "success" : "warning"}>{patient.is_deidentified ? "de-identified" : "restricted"}</Badge>
      </div>
      <div className="patient-card-facts">
        <span><strong>Gender</strong>{patient.gender || "unknown"}</span>
        <span><strong>Source</strong>{patient.source_system || patient.fhir_patient_id || "local"}</span>
      </div>
      <div className="patient-card-actions">
        <Link to={`/doctor/patients/${patient.patient_id}`}><Button variant="secondary" icon={ArrowRight} iconPosition="right">Open Detail</Button></Link>
        <Link to={`/doctor/generate-summary?patientId=${patient.patient_id}`}><Button variant="ghost" icon={FileText}>Generate</Button></Link>
      </div>
    </article>
  );
}
