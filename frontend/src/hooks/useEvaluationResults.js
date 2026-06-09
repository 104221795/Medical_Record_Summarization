import { evaluationApi } from "../services/evaluationApi.js";
import { useApi } from "./useApi.js";

export function useEvaluationResults(benchmarkType = null) {
  return useApi(() => evaluationApi.benchmarkResults(benchmarkType), [benchmarkType]);
}
