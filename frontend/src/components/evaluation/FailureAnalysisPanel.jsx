import Card from "../common/Card.jsx";

export default function FailureAnalysisPanel({ result }) {
  return (
    <Card title="Failure Analysis">
      <p className="muted">{result?.failure_analysis_exists ? "Failure analysis is available." : "Failure analysis file has not been generated yet."}</p>
      <code>{result?.failure_analysis_path || "not available"}</code>
    </Card>
  );
}
