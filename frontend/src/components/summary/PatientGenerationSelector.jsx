import { useMemo, useState } from "react";
import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import EmptyState from "../common/EmptyState.jsx";
import LoadingState from "../common/LoadingState.jsx";
import { patientLabel } from "../../utils/clinicalDisplay.js";

export default function PatientGenerationSelector({
  patients = [],
  loading,
  error,
  selectedPatientId,
  onSelectPatient,
  patientContext,
  contextLoading,
  encounterId,
  setEncounterId,
  sourceDocumentId,
  setSourceDocumentId,
}) {
  const [query, setQuery] = useState("");
  const filteredPatients = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return patients;
    return patients.filter((patient) =>
      [patient.patient_id, patient.external_patient_id, patient.patient_hash, patient.gender]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized)),
    );
  }, [patients, query]);

  return (
    <Card title="Patient & Encounter" className="golden-card">
      <div className="patient-selector-layout">
        <label className="field">
          <span>Patient search</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search patient ID, hash, or gender" />
        </label>
        {loading && <LoadingState label="Loading patients..." />}
        {error && <p className="warning-line">{error.message || String(error)}</p>}
        {!loading && !filteredPatients.length && <EmptyState title="No matching patients" message="Try another search or seed/import de-identified records." />}
        <div className="patient-pick-list">
          {filteredPatients.slice(0, 8).map((patient) => (
            <button
              type="button"
              className={`patient-pick-card ${patient.patient_id === selectedPatientId ? "active" : ""}`}
              key={patient.patient_id}
              onClick={() => onSelectPatient(patient.patient_id)}
            >
              <strong>{patientLabel(patient)}</strong>
              <span>{patient.gender || "gender unknown"}</span>
              <Badge tone={patient.is_deidentified ? "success" : "warning"}>{patient.is_deidentified ? "de-identified" : "restricted"}</Badge>
            </button>
          ))}
        </div>
        {contextLoading ? <LoadingState label="Loading selected patient context..." /> : (
          <SelectedContext
            context={patientContext}
            encounterId={encounterId}
            setEncounterId={setEncounterId}
            sourceDocumentId={sourceDocumentId}
            setSourceDocumentId={setSourceDocumentId}
          />
        )}
      </div>
    </Card>
  );
}

function SelectedContext({ context, encounterId, setEncounterId, sourceDocumentId, setSourceDocumentId }) {
  if (!context?.patient) {
    return <EmptyState title="Select a patient" message="Patient context will appear here before draft generation." />;
  }
  return (
    <div className="selected-context">
      <div className="selected-context-header">
        <div>
          <span>Selected patient</span>
          <strong>{patientLabel(context.patient)}</strong>
        </div>
        <Badge tone={context.patient.is_deidentified ? "success" : "warning"}>
          {context.patient.is_deidentified ? "de-identified" : "restricted"}
        </Badge>
      </div>
      <label className="field">
        <span>Encounter</span>
        <select value={encounterId} onChange={(event) => setEncounterId(event.target.value)}>
          <option value="">All encounters</option>
          {context.encounters.map((encounter) => (
            <option key={encounter.encounter_id} value={encounter.encounter_id}>
              {encounter.encounter_type || encounter.department || encounter.reason_for_visit || encounter.encounter_id}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Source document</span>
        <select value={sourceDocumentId} onChange={(event) => setSourceDocumentId(event.target.value)}>
          <option value="">All source documents</option>
          {context.documents.map((document) => (
            <option key={document.document_id} value={document.document_id}>
              {document.document_title || document.document_type || document.document_id}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
