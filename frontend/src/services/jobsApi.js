import { apiClient } from "./apiClient.js";

export const jobsApi = {
  readiness: ({ includeSmoke = false } = {}) => (
    apiClient(`/jobs/readiness?include_smoke=${includeSmoke ? "true" : "false"}`)
  ),
  list: () => apiClient("/jobs"),
  get: (jobId) => apiClient(`/jobs/${encodeURIComponent(jobId)}`),
  enqueue: (payload) => apiClient("/jobs", { method: "POST", body: JSON.stringify(payload) }),
  warmupDefaults: ({ timeoutSeconds = 900 } = {}) => (
    apiClient(`/jobs/warmup-defaults?timeout_seconds=${encodeURIComponent(String(timeoutSeconds))}`, {
      method: "POST",
      body: "{}",
    })
  ),
  cancel: (jobId) => apiClient(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST", body: "{}" }),
};
