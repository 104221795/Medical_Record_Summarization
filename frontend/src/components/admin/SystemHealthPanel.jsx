import Card from "../common/Card.jsx";
import { useApi } from "../../hooks/useApi.js";
import { evaluationApi } from "../../services/evaluationApi.js";

export default function SystemHealthPanel() {
  const { data } = useApi(() => evaluationApi.status(), []);
  return (
    <Card title="System Health">
      <div className="stack">{(data?.provider_readiness || []).map((item) => <div className="metric-row" key={item.provider}><span>{item.provider}</span><strong>{item.status}</strong></div>)}</div>
    </Card>
  );
}
