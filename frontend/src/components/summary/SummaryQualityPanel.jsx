import Badge from "../common/Badge.jsx";
import Card from "../common/Card.jsx";

const REQUIRED_DOMAINS = [
  { key: "diagnosis", label: "Diagnosis", types: ["diagnosis"] },
  { key: "medication", label: "Medication", types: ["medication"] },
  { key: "timeline", label: "Timeline", types: ["timeline_event", "encounter_context", "procedure"] },
];

export default function SummaryQualityPanel({ summary }) {
  const claims = extractClaims(summary);
  const unsupported = claims.filter((claim) => claim.support_status !== "supported");
  const missingDomains = missingRequiredDomains(claims);
  const citationCoverage = numeric(summary?.citation_coverage);
  const gate = summary?.retrieval_quality_gate || {};
  const reasons = flagReasons(summary, unsupported, missingDomains, citationCoverage, gate);

  return (
    <Card
      title="Evidence Quality Gate"
      className="summary-quality-panel"
      actions={<Badge tone={reasons.length ? "warning" : "success"}>{reasons.length ? "review required" : "evidence aligned"}</Badge>}
    >
      <div className="quality-metric-grid">
        <QualityMetric label="Citation coverage" value={citationCoverage == null ? "n/a" : citationCoverage.toFixed(2)} tone={citationCoverage >= 0.9 ? "success" : "warning"} />
        <QualityMetric label="Unsupported claims" value={unsupported.length} tone={unsupported.length ? "danger" : "success"} />
        <QualityMetric label="Conflicts" value={summary?.conflict_count ?? 0} tone={Number(summary?.conflict_count || 0) ? "danger" : "success"} />
        <QualityMetric label="Retrieval gate" value={gate.status || "n/a"} tone={gateTone(gate.status)} />
        <QualityMetric label="Provider" value={summary?.model_provider || "n/a"} tone="info" />
        <QualityMetric label="Review status" value={summary?.status || "not loaded"} tone={summary?.status === "approved" ? "success" : "warning"} />
      </div>
      <div className="quality-badge-row">
        {REQUIRED_DOMAINS.map((domain) => {
          const missing = missingDomains.includes(domain.key);
          return (
            <Badge key={domain.key} tone={missing ? "danger" : "success"}>
              {missing ? `missing ${domain.label.toLowerCase()}` : `${domain.label} cited`}
            </Badge>
          );
        })}
      </div>
      <div className="why-flagged-panel">
        <strong>Why this summary was flagged</strong>
        {reasons.length ? (
          <ul>
            {reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        ) : (
          <p>No blocking evidence issue detected by the proxy gate. Clinician review is still required.</p>
        )}
      </div>
    </Card>
  );
}

function QualityMetric({ label, value, tone }) {
  return (
    <div className="quality-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <Badge tone={tone}>{tone}</Badge>
    </div>
  );
}

function extractClaims(summary) {
  return summary?.sections?.flatMap((section) => section.claims || []) || [];
}

function missingRequiredDomains(claims) {
  const supportedTypes = new Set(
    claims
      .filter((claim) => claim.support_status === "supported" && Number(claim.citation_count || claim.citations?.length || 0) > 0)
      .map((claim) => claim.claim_type),
  );
  return REQUIRED_DOMAINS
    .filter((domain) => !domain.types.some((type) => supportedTypes.has(type)))
    .map((domain) => domain.key);
}

function flagReasons(summary, unsupported, missingDomains, citationCoverage, gate = {}) {
  const reasons = [];
  if (gate.status && gate.status !== "pass") {
    reasons.push(`Retrieval quality gate status is ${gate.status}; review retrieved evidence before approval.`);
  }
  (gate.missing_required_sections || []).forEach((section) => {
    reasons.push(`${section.toLowerCase()} retrieval evidence is missing from the RAG context.`);
  });
  (gate.missing_optional_sections || []).forEach((section) => {
    reasons.push(`${section.toLowerCase()} retrieval evidence was weak or absent.`);
  });
  (gate.scope_errors || []).slice(0, 2).forEach((issue) => {
    reasons.push(issue);
  });
  if ((gate.conflict_evidence || []).length) {
    reasons.push(`${gate.conflict_evidence.length} possible conflict evidence item(s) were retrieved.`);
  }
  if (citationCoverage != null && citationCoverage < 0.9) {
    reasons.push(`Citation coverage is ${citationCoverage.toFixed(2)}, below the 0.90 doctor-review target.`);
  }
  if (unsupported.length) {
    reasons.push(`${unsupported.length} claim(s) are unsupported, conflicting, or have insufficient evidence.`);
  }
  if (Number(summary?.conflict_count || 0) > 0) {
    reasons.push(`${summary.conflict_count} conflicting evidence item(s) need manual resolution.`);
  }
  missingDomains.forEach((domain) => {
    reasons.push(`${domain} evidence is missing or not cited in the generated draft.`);
  });
  return reasons;
}

function gateTone(status = "") {
  if (status === "pass") return "success";
  if (status === "fail") return "danger";
  if (status === "warning") return "warning";
  return "info";
}

function numeric(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
