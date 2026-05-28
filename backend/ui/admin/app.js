const API_PREFIX = "/api/v1";
const DEFAULT_SESSION = {
  tenantId: "sandbox",
  userId: "clinical-admin-demo",
  roleCode: "clinical_admin",
};

const state = {
  session: loadSession(),
  quality: null,
  usage: null,
  safety: null,
  review: null,
};

const elements = {
  roleSelect: document.querySelector("#roleSelect"),
  userInput: document.querySelector("#userInput"),
  saveSessionBtn: document.querySelector("#saveSessionBtn"),
  globalMessage: document.querySelector("#globalMessage"),
  readinessBadge: document.querySelector("#readinessBadge"),
  overviewCards: document.querySelector("#overviewCards"),
  statusBreakdown: document.querySelector("#statusBreakdown"),
  usageMetrics: document.querySelector("#usageMetrics"),
  safetyMetrics: document.querySelector("#safetyMetrics"),
  safetyGates: document.querySelector("#safetyGates"),
  reviewMetrics: document.querySelector("#reviewMetrics"),
  rejectionReasons: document.querySelector("#rejectionReasons"),
  auditFilters: document.querySelector("#auditFilters"),
  auditTableBody: document.querySelector("#auditTableBody"),
  auditDetail: document.querySelector("#auditDetail"),
  refreshAuditBtn: document.querySelector("#refreshAuditBtn"),
};

init();

function init() {
  elements.roleSelect.value = state.session.roleCode;
  elements.userInput.value = state.session.userId;
  elements.saveSessionBtn.addEventListener("click", () => {
    state.session = {
      tenantId: DEFAULT_SESSION.tenantId,
      userId: elements.userInput.value.trim() || DEFAULT_SESSION.userId,
      roleCode: elements.roleSelect.value,
    };
    localStorage.setItem("clinSummAdminSession", JSON.stringify(state.session));
    loadDashboard();
  });
  elements.auditFilters.addEventListener("submit", (event) => {
    event.preventDefault();
    loadAuditLogs();
  });
  elements.refreshAuditBtn.addEventListener("click", loadAuditLogs);
  loadDashboard();
}

function loadSession() {
  try {
    return JSON.parse(localStorage.getItem("clinSummAdminSession")) || DEFAULT_SESSION;
  } catch (_error) {
    return DEFAULT_SESSION;
  }
}

async function loadDashboard() {
  showMessage("Loading dashboard metrics...");
  clearDashboard();
  try {
    const [quality, usage, safety, review] = await Promise.all([
      api("/metrics/summary-quality"),
      api("/metrics/usage"),
      api("/metrics/safety"),
      api("/metrics/review"),
    ]);
    state.quality = quality;
    state.usage = usage;
    state.safety = safety;
    state.review = review;
    renderDashboard();
    await loadAuditLogs();
    hideMessage();
  } catch (error) {
    showMessage(error.message);
  }
}

async function loadAuditLogs() {
  elements.auditTableBody.innerHTML = rowHtml("Loading audit logs...", 5);
  const params = new URLSearchParams({ page_size: "20" });
  new FormData(elements.auditFilters).forEach((value, key) => {
    const text = String(value).trim();
    if (text) params.set(key, text);
  });
  try {
    const logs = await api(`/audit/logs?${params.toString()}`);
    renderAuditLogs(logs.items || []);
  } catch (error) {
    elements.auditTableBody.innerHTML = rowHtml(error.message, 5);
  }
}

async function showAuditDetail(auditId) {
  elements.auditDetail.innerHTML = "<h3>Audit detail</h3><p>Loading detail...</p>";
  try {
    const detail = await api(`/audit/logs/${auditId}`);
    elements.auditDetail.innerHTML = `
      <h3>Audit detail</h3>
      <div class="metric-list">
        ${metricRow("Audit ID", detail.audit_id)}
        ${metricRow("Action", detail.action)}
        ${metricRow("User", detail.user_display_name || detail.user_id || "not available")}
        ${metricRow("Patient ID", detail.patient_id || "not available")}
        ${metricRow("Resource", `${detail.resource_type || "not available"} / ${detail.resource_id || "not available"}`)}
        ${metricRow("Created", formatDate(detail.created_at))}
      </div>
      <h3>Safe metadata</h3>
      <pre>${escapeHtml(JSON.stringify(detail.action_metadata || {}, null, 2))}</pre>
    `;
  } catch (error) {
    elements.auditDetail.innerHTML = `<h3>Audit detail</h3><p class="message">${escapeHtml(error.message)}</p>`;
  }
}

async function api(path, options = {}) {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": state.session.tenantId,
      "X-User-ID": state.session.userId,
      "X-Role-Code": state.session.roleCode,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_error) {
      // Keep the HTTP detail string.
    }
    throw new Error(detail);
  }
  return response.json();
}

function renderDashboard() {
  const quality = state.quality;
  const usage = state.usage;
  const safety = state.safety;
  const review = state.review;
  const readiness = safety.safety_gate_status?.mvp_readiness_status || "warning";
  elements.readinessBadge.textContent = `MVP readiness: ${readiness}`;
  elements.readinessBadge.className = `badge ${readiness}`;

  elements.overviewCards.innerHTML = [
    card("Total summaries", quality.total_summaries),
    card("Approval rate", percent(quality.approval_rate)),
    card("Rejection rate", percent(quality.rejection_rate)),
    card("Avg citation coverage", percent(quality.average_citation_coverage)),
    card("Unsupported claims", safety.unsupported_claim_total),
    card("Conflicting claims", safety.conflicting_claim_total),
  ].join("");

  elements.statusBreakdown.innerHTML = [
    statusItem("Draft", quality.draft_count),
    statusItem("Under Review", quality.under_review_count),
    statusItem("Edited", quality.edited_count),
    statusItem("Approved", quality.approved_count),
    statusItem("Rejected", quality.rejected_count),
    statusItem("Archived", quality.archived_count),
  ].join("");

  elements.usageMetrics.innerHTML = [
    metricRow("Patients", usage.total_patients),
    metricRow("Encounters", usage.total_encounters),
    metricRow("Documents", usage.total_documents),
    metricRow("Document chunks", usage.total_document_chunks),
    metricRow("Summaries generated today", usage.summaries_generated_today),
    metricRow("Average generation latency", msOrNA(usage.average_generation_latency_ms)),
    metricRow("Model run count", usage.model_run_count),
  ].join("");

  elements.safetyMetrics.innerHTML = [
    metricRow("Citation coverage average", percent(safety.citation_coverage_average)),
    metricRow("Unsupported claim rate", percent(safety.unsupported_claim_rate)),
    metricRow("Weak citation count", safety.weak_citation_count),
    metricRow("Missing citation count", safety.missing_citation_count),
    metricRow("Critical unsupported proxy", safety.critical_hallucination_proxy_count),
    metricRow("Wrong-patient retrieval", safety.wrong_patient_retrieval_count),
  ].join("");

  elements.safetyGates.innerHTML = (safety.safety_gate_status?.gates || [])
    .map((gate) => `
      <div class="gate">
        <span>
          <strong>${escapeHtml(gate.name)}</strong><br />
          <small class="muted">${escapeHtml(gate.explanation || `threshold: ${displayValue(gate.threshold)}`)}</small>
        </span>
        <span class="badge ${gate.status}">${escapeHtml(gate.status)}: ${displayValue(gate.value)}</span>
      </div>
    `)
    .join("") || emptyState("No safety gates available.");

  elements.reviewMetrics.innerHTML = [
    metricRow("Total reviews", review.total_reviews),
    metricRow("Approvals", review.approvals),
    metricRow("Rejections", review.rejections),
    metricRow("Edits", review.edits),
    metricRow("Average edit distance", displayValue(review.average_edit_distance)),
    metricRow("Average time to review", hoursOrNA(review.average_time_to_review_hours)),
  ].join("");

  elements.rejectionReasons.innerHTML = (review.rejection_reasons_distribution || [])
    .map((item) => `<span class="chip">${escapeHtml(item.key)}: <strong>${item.count}</strong></span>`)
    .join("") || emptyState("No rejection reasons yet.");
}

function renderAuditLogs(items) {
  if (!items.length) {
    elements.auditTableBody.innerHTML = rowHtml("No audit events match the current filters.", 5);
    return;
  }
  elements.auditTableBody.innerHTML = items.map((item) => `
    <tr data-audit-id="${escapeHtml(item.audit_id)}">
      <td>${formatDate(item.created_at || item.timestamp)}</td>
      <td><strong>${escapeHtml(item.action)}</strong></td>
      <td>${escapeHtml(item.user_display_name || item.user_id || "not available")}</td>
      <td>${escapeHtml(item.patient_id || "not available")}</td>
      <td>${escapeHtml(item.resource_type || "not available")}<br /><small>${escapeHtml(item.resource_id || "")}</small></td>
    </tr>
  `).join("");
  elements.auditTableBody.querySelectorAll("tr[data-audit-id]").forEach((row) => {
    row.addEventListener("click", () => showAuditDetail(row.dataset.auditId));
  });
}

function clearDashboard() {
  [
    elements.overviewCards,
    elements.statusBreakdown,
    elements.usageMetrics,
    elements.safetyMetrics,
    elements.safetyGates,
    elements.reviewMetrics,
    elements.rejectionReasons,
  ].forEach((element) => {
    element.innerHTML = emptyState("Loading...");
  });
  elements.auditTableBody.innerHTML = rowHtml("Loading audit logs...", 5);
}

function card(label, value) {
  return `<div class="card"><span>${escapeHtml(label)}</span><strong>${displayValue(value)}</strong></div>`;
}

function statusItem(label, value) {
  return `<div class="status-item"><span>${escapeHtml(label)}</span><strong>${displayValue(value)}</strong></div>`;
}

function metricRow(label, value) {
  return `<div class="metric-row"><span>${escapeHtml(label)}</span><strong>${displayValue(value)}</strong></div>`;
}

function emptyState(text) {
  return `<p class="muted">${escapeHtml(text)}</p>`;
}

function rowHtml(text, columns) {
  return `<tr><td colspan="${columns}" class="muted">${escapeHtml(text)}</td></tr>`;
}

function percent(value) {
  if (value === null || value === undefined || value === "not_available") return "not available";
  return `${Math.round(Number(value) * 1000) / 10}%`;
}

function msOrNA(value) {
  return value === null || value === undefined ? "not available" : `${Math.round(value)} ms`;
}

function hoursOrNA(value) {
  return value === null || value === undefined ? "not available" : `${Math.round(value * 10) / 10} h`;
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "not available";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
  return String(value);
}

function formatDate(value) {
  if (!value) return "not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function showMessage(message) {
  elements.globalMessage.textContent = message;
  elements.globalMessage.classList.remove("hidden");
}

function hideMessage() {
  elements.globalMessage.classList.add("hidden");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
