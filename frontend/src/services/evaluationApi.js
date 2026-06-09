import { apiClient } from "./apiClient.js";

export const evaluationApi = {
  status: () => apiClient("/evaluation/status"),
  benchmarkStatus: () => apiClient("/evaluation/benchmark/status"),
  benchmarkResults: (benchmarkType) => {
    const query = benchmarkType ? `?benchmark_type=${encodeURIComponent(benchmarkType)}` : "";
    return apiClient(`/evaluation/benchmark/results${query}`);
  },
  humanSummary: () => apiClient("/evaluation/human/summary"),
  runFunctional: () => apiClient("/evaluation/functional/run", { method: "POST", body: "{}" }),
};
