import { GitCompareArrows } from "lucide-react";

import PageHeader from "../../components/common/PageHeader.jsx";
import FlowComparisonDashboard from "../../components/evaluation/FlowComparisonDashboard.jsx";

export default function FlowComparisonPage() {
  return (
    <div className="stack admin-analytics-page flow-comparison-page">
      <PageHeader
        eyebrow="Why RAG?"
        title="Three-Flow Comparison"
        description="Compare raw summarization, clinical context, and RAG-grounded generation on the same record and same model. Use this page to explain when retrieval improves clinical completeness and when evidence retrieval needs review."
        icon={GitCompareArrows}
      />
      <FlowComparisonDashboard />
    </div>
  );
}
