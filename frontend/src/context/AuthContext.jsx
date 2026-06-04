import { createContext, useContext, useEffect, useMemo, useState } from "react";

const AuthContext = createContext(null);
const API_PREFIX = import.meta.env.VITE_API_PREFIX || "/api/v1";
const SESSION_KEY = "clinSummReactSession";
const LEGACY_ROLE_KEY = "clinSummRole";

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => {
    try {
      return normalizeSession(JSON.parse(localStorage.getItem(SESSION_KEY)));
    } catch {
      return defaultSession;
    }
  });
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    let alive = true;
    const restore = async () => {
      const current = getStoredSessionValue();
      if (!current.token) {
        if (alive) setAuthReady(true);
        return;
      }
      try {
        const response = await fetch(`${API_PREFIX}/auth/me`, {
          headers: {
            "Content-Type": "application/json",
            "X-Tenant-ID": current.tenantId || "sandbox",
            "X-User-ID": current.userId || current.email || "doctor-demo",
            "X-Role-Code": roleCode(current.role),
            Authorization: `Bearer ${current.token}`,
          },
        });
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        const body = await response.json();
        if (alive) storeSession(sessionFromAuthResponse(body));
      } catch {
        clearAuthStorage();
        if (alive) setSession(defaultSession);
      } finally {
        if (alive) setAuthReady(true);
      }
    };
    restore();
    return () => { alive = false; };
  }, []);

  const updateSession = (next) => {
    const merged = { ...session, ...next };
    storeSession(merged);
  };

  const login = ({ role, userId, tenantId, fullName, email, token }) => {
    const nextSession = {
      tenantId: tenantId || "sandbox",
      userId: userId || (role === "admin" ? "admin-demo" : "doctor-demo"),
      fullName: fullName || userId || (role === "admin" ? "Admin Demo" : "Doctor Demo"),
      email: email || "",
      role: role || "doctor",
      token: token || "",
      authenticated: true,
    };
    storeSession(nextSession);
  };

  const logout = () => {
    setSession(defaultSession);
    clearAuthStorage();
  };

  const storeSession = (nextSession) => {
    const normalized = normalizeSession(nextSession);
    setSession(normalized);
    localStorage.setItem(SESSION_KEY, JSON.stringify(normalized));
    localStorage.removeItem(LEGACY_ROLE_KEY);
  };

  const value = useMemo(
    () => ({
      session,
      role: session.role || "doctor",
      updateSession,
      login,
      logout,
      authReady,
      isAuthenticated: Boolean(session.authenticated),
    }),
    [session, authReady],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

const defaultSession = {
  tenantId: "sandbox",
  userId: "doctor-demo",
  fullName: "",
  email: "",
  role: "",
  token: "",
  authenticated: false,
};

function normalizeSession(value) {
  return {
    ...defaultSession,
    ...(value || {}),
    role: value?.role || "",
    authenticated: Boolean(value?.authenticated && value?.token),
  };
}

function sessionFromAuthResponse(response) {
  return {
    tenantId: response.tenant_id || "sandbox",
    userId: response.user_id || response.email || "doctor-demo",
    fullName: response.full_name || response.user_id || response.email || "",
    email: response.email || "",
    role: response.role || "doctor",
    token: response.token || "",
    authenticated: Boolean(response.authenticated && response.token),
  };
}

function getStoredSessionValue() {
  try {
    return normalizeSession(JSON.parse(localStorage.getItem(SESSION_KEY)));
  } catch {
    return defaultSession;
  }
}

function clearAuthStorage() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(LEGACY_ROLE_KEY);
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(LEGACY_ROLE_KEY);
}

function roleCode(role) {
  return role === "admin" ? "clinical_admin" : "doctor";
}
