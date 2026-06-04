import { apiClient } from "./apiClient.js";

export const authApi = {
  config: () => apiClient("/auth/config"),
  login: (payload) => apiClient("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  googleLogin: (payload) => apiClient("/auth/google", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  signup: (payload) => apiClient("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  logout: () => apiClient("/auth/logout", { method: "POST", body: "{}" }),
  me: () => apiClient("/auth/me"),
};
