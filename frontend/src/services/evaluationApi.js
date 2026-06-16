import { apiClient } from "./apiClient.js";

export const evaluationApi = {
  status: () => apiClient("/evaluation/status"),
  benchmarkStatus: () => apiClient("/evaluation/benchmark/status"),
  benchmarkResults: (benchmarkType) => {
    const query = benchmarkType ? `?benchmark_type=${encodeURIComponent(benchmarkType)}` : "";
    return apiClient(`/evaluation/benchmark/results${query}`);
  },
  benchmarkFlowComparison: ({ limit = 12, provider = "" } = {}) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (provider) params.set("provider", provider);
    return apiClient(`/evaluation/benchmark/flow-comparison?${params.toString()}`);
  },
  humanSummary: () => apiClient("/evaluation/human/summary"),
  humanRubric: () => apiClient("/evaluation/human/rubric"),
  humanAnalytics: () => apiClient("/evaluation/human/analytics"),
  humanExport: ({ includeText = false, limit = 500 } = {}) => {
    const params = new URLSearchParams({ include_text: String(includeText), limit: String(limit) });
    return apiClient(`/evaluation/human/export?${params.toString()}`);
  },
  runFunctional: () => apiClient("/evaluation/functional/run", { method: "POST", body: "{}" }),
};
