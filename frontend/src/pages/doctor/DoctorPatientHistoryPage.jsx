import { useMemo, useState } from "react";
import Card from "../../components/common/Card.jsx";
import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import Badge from "../../components/common/Badge.jsx";
import PatientSummaryHistoryTable from "../../components/summary/PatientSummaryHistoryTable.jsx";
import { usePatientHistory } from "../../hooks/usePatientHistory.js";

export default function DoctorPatientHistoryPage() {
  const { rows, loading, error, reload } = usePatientHistory();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const filteredRows = useMemo(() => rows.filter((row) => {
    const matchesStatus = status === "all" || String(row.status || "").toLowerCase() === status;
    const needle = query.trim().toLowerCase();
    const matchesQuery = !needle || [row.patient_id, row.encounter, row.summary_id, row.provider, row.model_name, row.reviewer, row.last_action]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle));
    return matchesStatus && matchesQuery;
  }), [rows, query, status]);
  const statusOptions = useMemo(() => ["all", ...new Set(rows.map((row) => String(row.status || "").toLowerCase()).filter(Boolean))], [rows]);
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
      <Card title="Patient Summary History" className="history-worklist-card">
        <div className="history-toolbar">
          <label className="clinical-search-field">
            <span className="sr-only">Search history</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search patient, summary ID, provider, reviewer" />
          </label>
          <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter history status">
            {statusOptions.map((item) => <option value={item} key={item}>{item.replaceAll("_", " ")}</option>)}
          </select>
          <div className="worklist-summary">
            <Badge tone="info">{filteredRows.length} visible</Badge>
            <Badge tone="success">{rows.filter((row) => row.status === "approved").length} approved</Badge>
            <Badge tone="warning">{rows.filter((row) => row.status === "under_review" || row.status === "edited").length} in review</Badge>
          </div>
        </div>
        <PatientSummaryHistoryTable rows={filteredRows} />
        {!filteredRows.length && (
          <p className="muted history-helper">
            No history rows match the current filter. Clear search or status filter to see all available audit-backed summary history.
          </p>
        )}
      </Card>
    </div>
  );
}
