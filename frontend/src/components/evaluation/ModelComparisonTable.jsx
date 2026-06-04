import Badge from "../common/Badge.jsx";
import Table from "../common/Table.jsx";
import { formatLatency, formatScore, providerLabel, statusTone } from "./BenchmarkVisuals.jsx";

export default function ModelComparisonTable({ rows = [], bestModel }) {
  return (
    <Table
      rows={rows}
      columns={[
        {
          key: "model_provider",
          label: "Provider",
          render: (row) => (
            <div className="provider-table-cell">
              <strong>{providerLabel(row.model_provider)}</strong>
              <span>{row.model_provider}</span>
              {row.model_provider === bestModel && <Badge tone="success">best</Badge>}
            </div>
          ),
        },
        { key: "checkpoint", label: "Checkpoint", render: (row) => row.checkpoint || row.model_name || "not available" },
        { key: "stage_name", label: "Stage", render: (row) => row.stage_name || "not available" },
        { key: "domain_fit", label: "Domain fit", render: (row) => row.domain_fit || "not available" },
        { key: "status", label: "Status", render: (row) => <Badge tone={statusTone(row.status)}>{row.status || "unknown"}</Badge> },
        { key: "completed_count", label: "Records", render: (row) => `${row.completed_count}/${row.record_count}` },
        { key: "rouge1", label: "ROUGE-1", render: (row) => formatScore(row.rouge1) },
        { key: "rouge2", label: "ROUGE-2", render: (row) => formatScore(row.rouge2) },
        { key: "rougeL", label: "ROUGE-L", render: (row) => formatScore(row.rougeL) },
        { key: "average_latency_ms", label: "Avg latency", render: (row) => formatLatency(row.average_latency_ms) },
        { key: "total_runtime_seconds", label: "Runtime", render: (row) => row.total_runtime_seconds ? `${Number(row.total_runtime_seconds).toFixed(1)} s` : "n/a" },
      ]}
    />
  );
}
