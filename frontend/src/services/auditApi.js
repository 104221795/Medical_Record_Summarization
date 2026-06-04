import { apiClient } from "./apiClient.js";

export const auditApi = {
  logs: (params = {}) => {
    const query = new URLSearchParams(params);
    return apiClient(`/audit/logs${query.size ? `?${query}` : ""}`);
  },
  detail: (auditId) => apiClient(`/audit/logs/${auditId}`),
};
