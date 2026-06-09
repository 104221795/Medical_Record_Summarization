import { Link } from "react-router-dom";
import Badge from "../common/Badge.jsx";
import Button from "../common/Button.jsx";
import EmptyState from "../common/EmptyState.jsx";
import Table from "../common/Table.jsx";
import { actionLabel, formatDateTime, statusTone } from "../../utils/clinicalDisplay.js";

export default function PatientSummaryHistoryTable({ rows = [] }) {
  if (!rows.length) {
    return (
      <EmptyState
        title="No patient summary history yet"
        message="Generate a draft summary, then review or approve it to populate this history."
      />
    );
  }
  return (
    <Table
      rows={rows}
      columns={[
        { key: "patient", label: "Patient", render: (row) => row.patient_id || "not available" },
        { key: "encounter", label: "Encounter", render: (row) => row.encounter || "not available" },
        { key: "summary", label: "Summary ID", render: (row) => row.summary_id },
        { key: "provider", label: "Provider", render: (row) => <ProviderCell row={row} /> },
        { key: "status", label: "Status", render: (row) => <Badge tone={statusTone(row.status)}>{row.status}</Badge> },
        { key: "generated", label: "Generated", render: (row) => formatDateTime(row.generated_at) },
        { key: "reviewed", label: "Reviewed", render: (row) => formatDateTime(row.reviewed_at) },
        { key: "reviewer", label: "Reviewer", render: (row) => row.reviewer || "not available" },
        { key: "last_action", label: "Last Action", render: (row) => actionLabel(row.last_action) },
        {
          key: "actions",
          label: "Actions",
          render: (row) => (
            <div className="table-actions">
              <Link to={`/doctor/review/${row.summary_id}`}><Button variant="secondary">View Review</Button></Link>
              {row.patient_id && <Link to={`/doctor/patients/${row.patient_id}`}><Button variant="ghost">Open Patient</Button></Link>}
            </div>
          ),
        },
      ]}
    />
  );
}

function ProviderCell({ row }) {
  if (!row.provider && !row.model_name) return "not available";
  if (!row.model_name || row.model_name === row.provider) return row.provider || row.model_name;
  return (
    <div className="provider-table-cell">
      <strong>{row.provider || "not available"}</strong>
      <span>{row.model_name}</span>
    </div>
  );
}
