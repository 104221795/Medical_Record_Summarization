import Card from "../../components/common/Card.jsx";
import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import Table from "../../components/common/Table.jsx";
import Badge from "../../components/common/Badge.jsx";
import { auditApi } from "../../services/auditApi.js";
import { useApi } from "../../hooks/useApi.js";
import { actionLabel, formatDateTime, statusTone } from "../../utils/clinicalDisplay.js";

export default function DoctorAuditHistoryPage() {
  const { data, loading, error, reload } = useApi(() => auditApi.logs({ page: 1, page_size: 50 }), []);
  if (loading) return <LoadingState label="Loading doctor audit history..." />;
  if (error) return <ErrorState error={error} />;
  const rows = data?.items || [];
  return (
    <div className="doctor-golden-page">
      <PageHeader
        eyebrow="Audit trail"
        title="Audit History"
        description="Doctor actions for generated drafts, review starts, edits, approvals, rejections, and provider usage."
        actions={<button className="btn secondary" type="button" onClick={reload}>Refresh</button>}
      />
      <Card title="Doctor Workflow Audit">
        <Table
          rows={rows}
          empty="No audit data available yet. Generate and review a summary to populate the audit trail."
          columns={[
            { key: "timestamp", label: "Timestamp", render: (row) => formatDateTime(row.timestamp) },
            { key: "patient", label: "Patient", render: (row) => row.patient_id || "not available" },
            { key: "summary", label: "Summary ID", render: (row) => row.resource_type === "summary" ? row.resource_id : "not available" },
            { key: "action", label: "Action", render: (row) => actionLabel(row.action) },
            { key: "provider", label: "Provider", render: (row) => row.action_metadata?.provider || row.metadata?.provider || row.action_metadata?.model_name || "not available" },
            { key: "status", label: "Status", render: (row) => <Badge tone={statusTone(row.action_metadata?.status || row.metadata?.status)}>{row.action_metadata?.status || row.metadata?.status || "recorded"}</Badge> },
            { key: "user", label: "User", render: (row) => row.user_display_name || row.user_id || "not available" },
          ]}
        />
      </Card>
    </div>
  );
}
