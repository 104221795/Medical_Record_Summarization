import { apiClient } from "./apiClient.js";

export const patientApi = {
  list: () => apiClient("/patients"),
  detail: (patientId) => apiClient(`/patients/${patientId}`),
  encounters: (patientId) => apiClient(`/patients/${patientId}/encounters`),
  documents: (patientId) => apiClient(`/patients/${patientId}/documents`),
  document: (documentId) => apiClient(`/documents/${documentId}`),
  chunks: (documentId) => apiClient(`/documents/${documentId}/chunks`),
};
