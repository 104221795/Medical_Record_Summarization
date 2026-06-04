import { Navigate } from "react-router-dom";
import LoadingState from "../components/common/LoadingState.jsx";
import { useRole } from "../hooks/useRole.js";

export default function ProtectedRoute({ role: requiredRole, children }) {
  const { role, authReady, isAuthenticated } = useRole();
  if (!authReady) {
    return <LoadingState label="Restoring secure session..." />;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (requiredRole && role !== requiredRole) {
    return <Navigate to={role === "admin" ? "/admin" : "/doctor"} replace />;
  }
  return children;
}
