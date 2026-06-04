import { useAuth } from "../context/AuthContext.jsx";
import { useRoleContext } from "../context/RoleContext.jsx";

export function useRole() {
  const auth = useAuth();
  const role = useRoleContext();
  return { ...auth, ...role };
}

export function getStoredRole() {
  return getStoredSession().role || "doctor";
}

export function getStoredSession() {
  try {
    return JSON.parse(localStorage.getItem("clinSummReactSession")) || {
      tenantId: "sandbox",
      userId: "doctor-demo",
      fullName: "",
      email: "",
      role: "",
      token: "",
      authenticated: false,
    };
  } catch {
    return { tenantId: "sandbox", userId: "doctor-demo", fullName: "", email: "", role: "", token: "", authenticated: false };
  }
}
