import { createContext, useContext, useMemo } from "react";
import { useAuth } from "./AuthContext.jsx";

const RoleContext = createContext(null);

export function RoleProvider({ children }) {
  const { session } = useAuth();
  const role = session.role || "doctor";
  const switchRole = () => {
    // Role is owned by authenticated backend session data. Kept for legacy callers.
  };
  const value = useMemo(() => ({ role, switchRole, isAdmin: role === "admin", isDoctor: role === "doctor" }), [role]);
  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRoleContext() {
  return useContext(RoleContext);
}
