import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";
import MetricCard from "../common/MetricCard.jsx";
import PageHeader from "../common/PageHeader.jsx";

const datasetLayers = [
  {
    name: "Synthea / SyntheticMass",
    purpose: "Backend ingestion and FHIR validation",
    records: "FHIR bundles / synthetic patients",
    readiness: 76,
    tone: "info",
    status: "ingestion validation",
    detail: "Validates Patient, Encounter, Condition, Observation, Medication, and persistence flows.",
  },
  {
    name: "MultiClinSum Full",
    purpose: "Main proxy summarization benchmark",
    records: "25,902 benchmark-ready records",
    readiness: 92,
    tone: "success",
    status: "benchmark-ready",
    detail: "Uses data/processed/governance/benchmark_set.jsonl for governed proxy benchmarking.",
  },
  {
    name: "MTS-Dialog / MEDIQA-Sum",
    purpose: "Future cross-dataset proxy benchmark",
    records: "planned",
    readiness: 42,
    tone: "warning",
    status: "planned",
    detail: "Use for robustness checks across open clinical summarization tasks.",
  },
  {
    name: "MIMIC-IV-Note / MIMIC-IV-BHC",
    purpose: "Future real EHR benchmark",
    records: "credentialed access required",
    readiness: 18,
    tone: "danger",
    status: "governance pending",
    detail: "Requires credentialed access, governance approval, and strict clinical data handling.",
  },
];

export default function DatasetStatusPanel() {
  return (
    <div className="stack admin-analytics-page">
      <PageHeader
        eyebrow="Dataset governance"
        title="Dataset Readiness"
        description="Governed dataset layers for ingestion validation, proxy summarization benchmarking, cross-dataset checks, and future real EHR evaluation."
      />
      <div className="metric-grid">
        <MetricCard label="Benchmark-ready records" value="25,902" detail="MultiClinSum governed set" />
        <MetricCard label="Benchmark set" value="available" detail="data/processed/governance/benchmark_set.jsonl" />
        <MetricCard label="Warning records" value="governed" detail="Excluded unless manually reviewed" />
        <MetricCard label="Rejected records" value="blocked" detail="Not allowed into model evaluation" />
      </div>
      <div className="dataset-card-grid">
        {datasetLayers.map((layer) => (
          <Card key={layer.name} title={layer.name} actions={<Badge tone={layer.tone}>{layer.status}</Badge>}>
            <p className="dataset-purpose">{layer.purpose}</p>
            <strong>{layer.records}</strong>
            <div className="readiness-bar" aria-label={`${layer.readiness}% readiness`}>
              <span style={{ width: `${layer.readiness}%` }} />
            </div>
            <p className="muted">{layer.detail}</p>
          </Card>
        ))}
      </div>
      <Card title="Dataset Layer Purpose">
        <div className="dataset-layers">
          <section><h3>A. Synthea / SyntheticMass</h3><p>Backend ingestion, FHIR validation, schema mapping, and database persistence validation.</p></section>
          <section><h3>B. MultiClinSum Full</h3><p>Main proxy summarization benchmark at <code>data/processed/governance/benchmark_set.jsonl</code>.</p></section>
          <section><h3>C. MTS-Dialog / MEDIQA-Sum</h3><p>Future cross-dataset proxy benchmarks for robustness across dialogue and medical QA summarization.</p></section>
          <section><h3>D. MIMIC-IV-Note / MIMIC-IV-BHC</h3><p>Future real EHR benchmark requiring credentialed access and governance approval.</p></section>
        </div>
      </Card>
      <Card title="Proxy Evaluation Notice">
        <p className="warning-line">
          Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes.
        </p>
      </Card>
    </div>
  );
}
