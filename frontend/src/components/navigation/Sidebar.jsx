import { Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  BrainCircuit,
  Activity,
  ClipboardCheck,
  FileClock,
  Gauge,
  GitCompareArrows,
  History,
  LayoutDashboard,
  NotebookTabs,
  ScrollText,
  Settings,
  ShieldCheck,
  Stethoscope,
  Users,
} from "lucide-react";
import { useRole } from "../../hooks/useRole.js";
import { brandAssets } from "../../assets/branding.js";
import { getActiveNavKey } from "../../utils/navigation.js";

const doctorNav = [
  { key: "doctor-dashboard", label: "Dashboard", path: "/doctor", icon: LayoutDashboard },
  { key: "doctor-patients", label: "Patients", path: "/doctor/patients", icon: Users },
  { key: "doctor-generate-summary", label: "Generate Summary", path: "/doctor/generate-summary", icon: Stethoscope },
  { key: "doctor-review-evidence", label: "Review & Evidence", path: "/doctor/review", icon: ClipboardCheck },
  { key: "doctor-patient-history", label: "Patient History", path: "/doctor/patient-history", icon: FileClock },
  { key: "doctor-audit-history", label: "Audit History", path: "/doctor/audit-history", icon: History },
  { key: "doctor-user-guide", label: "User Guide", path: "/doctor/user-guide", icon: NotebookTabs },
];

const adminNav = [
  { key: "admin-dashboard", label: "Dashboard", path: "/admin", icon: LayoutDashboard },
  { key: "admin-datasets", label: "Dataset Governance", path: "/admin/datasets", icon: ShieldCheck },
  { key: "admin-evaluation", label: "Evaluation", path: "/admin/evaluation", icon: BarChart3 },
  { key: "admin-benchmark", label: "Benchmark Results", path: "/admin/evaluation/benchmark", icon: Gauge },
  { key: "admin-rag-best-models", label: "RAG Best Models", path: "/admin/evaluation/rag-best-models", icon: BrainCircuit },
  { key: "admin-flow-comparison", label: "Flow Comparison", path: "/admin/evaluation/flow-comparison", icon: GitCompareArrows },
  { key: "admin-model-jobs", label: "Model Jobs", path: "/admin/jobs", icon: Activity },
  { key: "admin-audit", label: "Audit Logs", path: "/admin/audit", icon: ScrollText },
  { key: "admin-settings", label: "Settings", path: "/admin/settings", icon: Settings },
  { key: "admin-guide", label: "User Guide", path: "/admin/guide", icon: NotebookTabs },
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
        {nav.map(({ key, label, path, icon: Icon }) => (
          <Link
            key={key}
            to={path}
            className={activeKey === key ? "active" : ""}
            aria-current={activeKey === key ? "page" : undefined}
          >
            <Icon aria-hidden="true" className="ui-icon nav-icon" size={18} strokeWidth={2.25} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}
