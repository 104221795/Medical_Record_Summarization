import { apiClient } from "./apiClient.js";

export const SUMMARY_PROVIDERS = [
  "deterministic",
  "gemini",
  "qwen2.5",
  "llama3.2",
  "gemini2.5_flash_lite",
  "bart",
  "pegasus",
  "pegasus_pubmed",
  "pegasus_cnn_dailymail",
  "pegasus_xsum",
];

export const summaryApi = {
  providers: () => apiClient("/providers"),
  generate: (patientId, payload) => apiClient(`/patients/${patientId}/summaries/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  detail: (summaryId) => apiClient(`/summaries/${summaryId}`),
  startReview: (summaryId) => apiClient(`/summaries/${summaryId}/review/start`, { method: "POST", body: "{}" }),
  edit: (summaryId, payload) => apiClient(`/summaries/${summaryId}/edit`, { method: "PATCH", body: JSON.stringify(payload) }),
  approve: (summaryId, payload) => apiClient(`/summaries/${summaryId}/approve`, { method: "POST", body: JSON.stringify(payload) }),
  reject: (summaryId, payload) => apiClient(`/summaries/${summaryId}/reject`, { method: "POST", body: JSON.stringify(payload) }),
  reviews: (summaryId) => apiClient(`/summaries/${summaryId}/reviews`),
  citationSource: (citationId) => apiClient(`/citations/${citationId}/source`),
};
