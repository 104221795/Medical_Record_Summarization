import { useState } from "react";

import Card from "../common/Card.jsx";
import ErrorState from "../common/ErrorState.jsx";
import LoadingState from "../common/LoadingState.jsx";
import Tabs from "../common/Tabs.jsx";
import { useEvaluationResults } from "../../hooks/useEvaluationResults.js";

export const BENCHMARK_FLOWS = [
  {
    key: "summarization_only",
    label: "Flow 1: Raw Summarization",
    title: "Flow 1",
    description: "source note -> summarizer -> ROUGE / clinical proxy metrics",
  },
  {
    key: "clinical_context",
    label: "Flow 1.5: Clinical Context",
    title: "Flow 1.5",
    description: "source note -> sectioned clinical context -> summarizer -> clinical proxy metrics",
  },
  {
    key: "rag_grounded",
    label: "Flow 2: RAG Grounded",
    title: "Flow 2",
    description: "source note -> chunk -> MiniLM -> Qdrant -> evidence -> summarizer -> citation metrics",
  },
];

export default function BenchmarkFlowTabs({ children, loadingLabel = "Loading benchmark artifacts..." }) {
  const [activeFlow, setActiveFlow] = useState("summarization_only");
  const rawFlow = useEvaluationResults("summarization_only");
  const clinicalContextFlow = useEvaluationResults("clinical_context");
  const ragFlow = useEvaluationResults("rag_grounded");
  const flowStateByKey = {
    summarization_only: rawFlow,
    clinical_context: clinicalContextFlow,
    rag_grounded: ragFlow,
  };
  const active = flowStateByKey[activeFlow] || rawFlow;
  const flowMeta = BENCHMARK_FLOWS.find((flow) => flow.key === activeFlow) || BENCHMARK_FLOWS[0];
  const loading = rawFlow.loading && clinicalContextFlow.loading && ragFlow.loading;

  const reloadAll = () => {
    rawFlow.reload();
    clinicalContextFlow.reload();
    ragFlow.reload();
  };

  if (loading) return <LoadingState label={loadingLabel} />;

  return (
    <div className="stack benchmark-flow-shell">
      <Card className="benchmark-flow-card">
        <Tabs tabs={BENCHMARK_FLOWS} active={activeFlow} onChange={setActiveFlow} />
        <div className="benchmark-flow-summary">
          <div>
            <span>{flowMeta.title}</span>
            <p>{flowMeta.description}</p>
          </div>
          <code>{active.data?.selected_output_dir || active.data?.output_dir || "output not available"}</code>
        </div>
      </Card>
      {active.error ? (
        <ErrorState error={active.error} />
      ) : active.loading ? (
        <LoadingState label={`Loading ${flowMeta.label}...`} />
      ) : (
        children({
          data: active.data,
          reload: reloadAll,
          activeFlow,
          flowMeta,
          flowResults: {
            summarization_only: rawFlow.data,
            clinical_context: clinicalContextFlow.data,
            rag_grounded: ragFlow.data,
          },
        })
      )}
    </div>
  );
}
