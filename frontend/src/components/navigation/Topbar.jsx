import { LogOut, UserRound } from "lucide-react";
import { useRole } from "../../hooks/useRole.js";
import Button from "../common/Button.jsx";
import { authApi } from "../../services/authApi.js";

export default function Topbar() {
  const { role, session, logout } = useRole();
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">{role === "admin" ? "Administration" : "Doctor Workspace"}</p>
        <h1>Medical Record Summarization</h1>
      </div>
      <div className="topbar-actions">
        <div className="profile-chip">
          <UserRound aria-hidden="true" className="ui-icon profile-icon" size={18} strokeWidth={2.2} />
          <strong>{session.fullName || session.userId}</strong>
          <span>{role === "admin" ? "Admin" : "Doctor"}</span>
        </div>
        <Button
          variant="secondary"
          icon={LogOut}
          onClick={async () => {
            try {
              await authApi.logout();
            } catch {
              // Client-side session cleanup is still authoritative for the demo UI.
            }
            logout();
            window.location.href = "/login";
          }}
        >
          Logout
        </Button>
      </div>
    </header>
  );
}
