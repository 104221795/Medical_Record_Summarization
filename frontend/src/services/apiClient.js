import { getStoredSession, getStoredRole } from "../hooks/useRole.js";

const API_PREFIX = import.meta.env.VITE_API_PREFIX || "/api/v1";

export async function apiClient(path, options = {}) {
  const session = getStoredSession();
  const role = getStoredRole();
  const userId = String(session.userId || session.email || "doctor-demo").trim();
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": session.tenantId,
      "X-User-ID": userId,
      "X-Role-Code": role === "admin" ? "clinical_admin" : "doctor",
      ...(session.token ? { Authorization: `Bearer ${session.token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep status detail.
    }
    throw new Error(detail);
  }
  return response.json();
}
