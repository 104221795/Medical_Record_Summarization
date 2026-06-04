import Card from "../common/Card.jsx";

export default function EvaluationReportViewer({ result }) {
  return (
    <Card title="Evaluation Report">
      <p>{result?.proxy_warning}</p>
      <code>{result?.report_path || "not available"}</code>
    </Card>
  );
}
