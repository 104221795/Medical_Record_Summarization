import Card from "../common/Card.jsx";
import MetricCard from "../common/MetricCard.jsx";
import { useApi } from "../../hooks/useApi.js";
import { apiClient } from "../../services/apiClient.js";

export default function AdminOverview() {
  const { data } = useApi(async () => {
    const [usage, quality, safety] = await Promise.all([
      apiClient("/metrics/usage"),
      apiClient("/metrics/summary-quality"),
      apiClient("/metrics/safety"),
    ]);
    return { usage, quality, safety };
  }, []);
  return (
    <Card title="Admin Overview">
      <div className="metric-grid">
        <MetricCard label="Patients" value={data?.usage?.total_patients} />
        <MetricCard label="Documents" value={data?.usage?.total_documents} />
        <MetricCard label="Summaries" value={data?.quality?.total_summaries} />
        <MetricCard label="Unsupported claims" value={data?.safety?.unsupported_claim_total} />
      </div>
    </Card>
  );
}
