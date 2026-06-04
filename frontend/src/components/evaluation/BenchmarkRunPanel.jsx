import Card from "../common/Card.jsx";

export default function BenchmarkRunPanel({ result }) {
  return (
    <Card title="Benchmark Run">
      <div className="metric-list">
        <div><span>Output directory</span><strong>{result?.output_dir || "not available"}</strong></div>
        <div><span>Report</span><strong>{result?.report_exists ? "available" : "missing"}</strong></div>
        <div><span>Failure analysis</span><strong>{result?.failure_analysis_exists ? "available" : "missing"}</strong></div>
      </div>
    </Card>
  );
}
