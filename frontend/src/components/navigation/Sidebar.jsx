import { Link, useLocation } from "react-router-dom";
import { useRole } from "../../hooks/useRole.js";
import { brandAssets } from "../../assets/branding.js";
import { getActiveNavKey } from "../../utils/navigation.js";

const doctorNav = [
  { key: "doctor-dashboard", label: "Dashboard", path: "/doctor" },
  { key: "doctor-patients", label: "Patients", path: "/doctor/patients" },
  { key: "doctor-generate-summary", label: "Generate Summary", path: "/doctor/generate-summary" },
  { key: "doctor-review-evidence", label: "Review & Evidence", path: "/doctor/review" },
  { key: "doctor-patient-history", label: "Patient History", path: "/doctor/patient-history" },
  { key: "doctor-audit-history", label: "Audit History", path: "/doctor/audit-history" },
  { key: "doctor-user-guide", label: "User Guide", path: "/doctor/user-guide" },
];

const adminNav = [
  { key: "admin-dashboard", label: "Dashboard", path: "/admin" },
  { key: "admin-datasets", label: "Dataset Governance", path: "/admin/datasets" },
  { key: "admin-evaluation", label: "Evaluation", path: "/admin/evaluation" },
  { key: "admin-benchmark", label: "Benchmark Results", path: "/admin/evaluation/benchmark" },
  { key: "admin-audit", label: "Audit Logs", path: "/admin/audit" },
  { key: "admin-settings", label: "Settings", path: "/admin/settings" },
  { key: "admin-guide", label: "User Guide", path: "/admin/guide" },
];

export default function Sidebar() {
  const { role } = useRole();
  const location = useLocation();
  const nav = role === "admin" ? adminNav : doctorNav;
  const activeKey = getActiveNavKey(location.pathname);
  return (
    <aside className="sidebar">
      <div className="brand">
        <img className="brand-logo" src={brandAssets.logo} alt="Medical Record Summarization logo" />
        <div><strong>Med Summ</strong><small>Medical Record Summarization</small></div>
      </div>
      <nav>
        {nav.map(({ key, label, path }) => (
          <Link
            key={key}
            to={path}
            className={activeKey === key ? "active" : ""}
            aria-current={activeKey === key ? "page" : undefined}
          >
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
