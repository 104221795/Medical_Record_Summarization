import { evaluationApi } from "../services/evaluationApi.js";
import { useApi } from "./useApi.js";

export function useEvaluationResults() {
  return useApi(() => evaluationApi.benchmarkResults(), []);
}
