import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import Badge from "../common/Badge.jsx";
import EmptyState from "../common/EmptyState.jsx";
import PatientCard from "./PatientCard.jsx";

export default function PatientList({ patients }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return patients || [];
    return (patients || []).filter((patient) =>
      [patient.patient_id, patient.external_patient_id, patient.patient_hash, patient.gender, patient.source_system]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle)),
    );
  }, [patients, query]);

  if (!patients?.length) return <EmptyState title="No patients found" message="Seed demo data or import de-identified records." />;
  return (
    <section className="patient-worklist">
      <div className="patient-worklist-toolbar">
        <label className="clinical-search-field">
          <Search aria-hidden="true" className="ui-icon" size={17} strokeWidth={2.2} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search patient ID, hash, gender, or source"
          />
        </label>
        <div className="worklist-summary">
          <Badge tone="info">{filtered.length} visible</Badge>
          <Badge tone="success">{patients.filter((patient) => patient.is_deidentified).length} de-identified</Badge>
        </div>
      </div>
      {!filtered.length ? (
        <EmptyState title="No matching patients" message="Try a different search term or clear the filter." />
      ) : (
        <div className="patient-worklist-grid">
          {filtered.map((patient) => <PatientCard key={patient.patient_id} patient={patient} />)}
        </div>
      )}
    </section>
  );
}
