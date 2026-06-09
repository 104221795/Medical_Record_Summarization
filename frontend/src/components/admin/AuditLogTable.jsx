import Table from "../common/Table.jsx";
import Badge from "../common/Badge.jsx";
import { useApi } from "../../hooks/useApi.js";
import { auditApi } from "../../services/auditApi.js";
import { actionLabel, formatDateTime, statusTone } from "../../utils/clinicalDisplay.js";
import {
  auditActor,
  auditPatientId,
  auditProvider,
  auditStatus,
} from "../../utils/historyDisplay.js";

export default function AuditLogTable() {
  const { data } = useApi(() => auditApi.logs({ page: 1, page_size: 25 }), []);
  return (
    <Table
      rows={data?.items || []}
      columns={[
        { key: "timestamp", label: "Time", render: (row) => formatDateTime(row.timestamp) },
        { key: "action", label: "Action", render: (row) => actionLabel(row.action) },
        { key: "user_display_name", label: "User", render: (row) => auditActor(row) },
        { key: "patient_id", label: "Patient", render: (row) => auditPatientId(row) },
        { key: "provider", label: "Provider", render: (row) => auditProvider(row) },
        { key: "status", label: "Status", render: (row) => <Badge tone={statusTone(auditStatus(row))}>{auditStatus(row)}</Badge> },
        { key: "resource_type", label: "Resource" },
      ]}
    />
  );
}
