import Table from "../common/Table.jsx";
import { useApi } from "../../hooks/useApi.js";
import { auditApi } from "../../services/auditApi.js";

export default function AuditLogTable() {
  const { data } = useApi(() => auditApi.logs({ page: 1, page_size: 25 }), []);
  return (
    <Table
      rows={data?.items || []}
      columns={[
        { key: "timestamp", label: "Time" },
        { key: "action", label: "Action" },
        { key: "user_display_name", label: "User" },
        { key: "patient_id", label: "Patient" },
        { key: "provider", label: "Provider", render: (row) => row.action_metadata?.provider || row.metadata?.provider || row.action_metadata?.model_name || "" },
        { key: "status", label: "Status", render: (row) => row.action_metadata?.status || row.metadata?.status || "" },
        { key: "resource_type", label: "Resource" },
      ]}
    />
  );
}
