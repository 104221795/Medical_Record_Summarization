export function getActiveNavKey(pathname) {
  const cleanPath = normalizePath(pathname);

  if (cleanPath === "/doctor" || cleanPath === "/doctor/dashboard") return "doctor-dashboard";
  if (cleanPath === "/doctor/generate-summary" || /\/doctor\/patients\/[^/]+\/generate-summary$/.test(cleanPath)) return "doctor-generate-summary";
  if (cleanPath === "/doctor/review" || cleanPath.startsWith("/doctor/review/")) return "doctor-review-evidence";
  if (cleanPath === "/doctor/patient-history") return "doctor-patient-history";
  if (cleanPath === "/doctor/audit-history" || cleanPath === "/doctor/audit") return "doctor-audit-history";
  if (cleanPath === "/doctor/user-guide" || cleanPath === "/doctor/guide") return "doctor-user-guide";
  if (isSummaryWorkspacePath(cleanPath)) return "doctor-review-evidence";
  if (cleanPath === "/doctor/patients" || cleanPath.startsWith("/doctor/patients/")) return "doctor-patients";

  if (cleanPath === "/admin" || cleanPath === "/admin/dashboard") return "admin-dashboard";
  if (cleanPath === "/admin/datasets") return "admin-datasets";
  if (cleanPath === "/admin/evaluation/benchmark") return "admin-benchmark";
  if (cleanPath === "/admin/evaluation/rag-best-models") return "admin-rag-best-models";
  if (cleanPath === "/admin/evaluation/flow-comparison") return "admin-flow-comparison";
  if (cleanPath === "/admin/evaluation") return "admin-evaluation";
  if (cleanPath === "/admin/audit") return "admin-audit";
  if (cleanPath === "/admin/settings") return "admin-settings";
  if (cleanPath === "/admin/guide") return "admin-guide";

  return "";
}

function normalizePath(pathname) {
  const withoutTrailingSlash = pathname.replace(/\/+$/, "");
  return withoutTrailingSlash || "/";
}

function isSummaryWorkspacePath(pathname) {
  return (
    pathname === "/doctor/summary-workspace" ||
    /\/doctor\/patients\/[^/]+\/(summary-workspace|review)$/.test(pathname)
  );
}
