import { apiClient } from "./apiClient.js";

export const evaluationApi = {
  status: () => apiClient("/evaluation/status"),
  benchmarkStatus: () => apiClient("/evaluation/benchmark/status"),
  benchmarkResults: () => apiClient("/evaluation/benchmark/results"),
  humanSummary: () => apiClient("/evaluation/human/summary"),
  runFunctional: () => apiClient("/evaluation/functional/run", { method: "POST", body: "{}" }),
};
