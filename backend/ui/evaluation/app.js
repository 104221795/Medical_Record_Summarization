const API_PREFIX = "/api/v1";
const DEFAULT_SESSION = {
  tenantId: "sandbox",
  userId: "clinical-admin-demo",
  roleCode: "clinical_admin",
};

const state = {
  session: loadSession(),
  readiness: null,
  evaluation: null,
  benchmark: null,
  human: null,
  quality: null,
  usage: null,
  safety: null,
  review: null,
};

const elements = {
  roleSelect: document.querySelector("#roleSelect"),
  userInput: document.querySelector("#userInput"),
  reloadBtn: document.querySelector("#reloadBtn"),
  globalMessage: document.querySelector("#globalMessage"),
  goldenPathStatus: document.querySelector("#goldenPathStatus"),
  providerStatus: document.querySelector("#providerStatus"),
  safetyStatus: document.querySelector("#safetyStatus"),
  reviewStatus: document.querySelector("#reviewStatus"),
  monitoringStatus: document.querySelector("#monitoringStatus"),
  evaluationLayers: document.querySelector("#evaluationLayers"),
  runFunctionalBtn: document.querySelector("#runFunctionalBtn"),
  functionalResult: document.querySelector("#functionalResult"),
  humanEvaluationForm: document.querySelector("#humanEvaluationForm"),
  humanSummary: document.querySelector("#humanSummary"),
  demoChecklist: document.querySelector("#demoChecklist"),
};

init();

function init() {
  elements.roleSelect.value = state.session.roleCode;
  elements.userInput.value = state.session.userId;
  elements.reloadBtn.addEventListener("click", () => {
    state.session = {
      tenantId: DEFAULT_SESSION.tenantId,
      userId: elements.userInput.value.trim() || DEFAULT_SESSION.userId,
      roleCode: elements.roleSelect.value,
    };
    localStorage.setItem("clinSummEvaluationSession", JSON.stringify(state.session));
    loadControlCenter();
  });
  elements.runFunctionalBtn.addEventListener("click", runFunctionalValidation);
  elements.humanEvaluationForm.addEventListener("submit", submitHumanEvaluation);
  loadControlCenter();
}

function loadSession() {
  try {
    return JSON.parse(localStorage.getItem("clinSummEvaluationSession")) || DEFAULT_SESSION;
  } catch (_error) {
    return DEFAULT_SESSION;
  }
}

async function loadControlCenter() {
  showMessage("Loading evaluation and demo readiness...");
  renderLoading();
  try {
    const [readiness, evaluation, benchmark, human, quality, usage, safety, review] = await Promise.all([
      api("/demo/readiness"),
      api("/evaluation/status"),
      api("/evaluation/benchmark/status"),
      api("/evaluation/human/summary"),
      api("/metrics/summary-quality"),
      api("/metrics/usage"),
      api("/metrics/safety"),
      api("/metrics/review"),
    ]);
    Object.assign(state, { readiness, evaluation, benchmark, human, quality, usage, safety, review });
    renderAll();
    hideMessage();
  } catch (error) {
    showMessage(error.message);
  }
}

async function runFunctionalValidation() {
  elements.runFunctionalBtn.disabled = true;
  elements.functionalResult.innerHTML = card("Running", "Functional validation in progress...", "runnable");
  try {
    const result = await api("/evaluation/functional/run", { method: "POST", body: "{}" });
    renderFunctionalResult(result);
    await loadControlCenter();
  } catch (error) {
    elements.functionalResult.innerHTML = card("Failed", error.message, "failed");
  } finally {
    elements.runFunctionalBtn.disabled = false;
  }
}

async function submitHumanEvaluation(event) {
  event.preventDefault();
  const form = new FormData(elements.humanEvaluationForm);
  const payload = {};
  form.forEach((value, key) => {
    const text = String(value).trim();
    if (text) payload[key] = text;
  });
  [
    "factual_correctness_score",
    "completeness_score",
    "conciseness_score",
    "readability_score",
    "citation_usefulness_score",
  ].forEach((key) => {
    payload[key] = Number(payload[key]);
  });
  try {
    await api("/evaluation/human", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    elements.humanEvaluationForm.reset();
    showMessage("Human evaluation submitted.");
    await loadControlCenter();
  } catch (error) {
    showMessage(error.message);
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
      // Keep HTTP status detail.
    }
    throw new Error(detail);
  }
  return response.json();
}

function renderAll() {
  renderGoldenPath();
  renderProviders();
  renderSafety();
  renderReview();
  renderMonitoring();
  renderLayers();
  renderHumanSummary();
  renderChecklist();
}

function renderGoldenPath() {
  elements.goldenPathStatus.innerHTML = (state.readiness.golden_path || [])
    .map((item) => statusCard(item.name, item.status, item.message))
    .join("");
}

function renderProviders() {
  elements.providerStatus.innerHTML = (state.evaluation.provider_readiness || [])
    .map((item) => `
      <div class="card">
        <div class="panel-heading">
          <strong>${escapeHtml(item.provider)}</strong>
          <span class="badge ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>
        </div>
        ${metricRow("Configured", item.configured ? "yes" : "no")}
        ${metricRow("Enabled", item.enabled ? "yes" : "no")}
        ${metricRow("Model", item.model_name || "not available")}
        ${metricRow("Last run", item.last_run_status || "not run")}
        ${metricRow("Latency", item.latency_ms === null || item.latency_ms === undefined ? "not available" : `${item.latency_ms} ms`)}
        <p class="hint">${escapeHtml(item.message || "")}</p>
      </div>
    `)
    .join("");
}

function renderSafety() {
  const safety = state.safety;
  elements.safetyStatus.innerHTML = [
    metricRow("Citation coverage", percent(safety.citation_coverage_average)),
    metricRow("Unsupported claims", safety.unsupported_claim_total),
    metricRow("Missing citation count", safety.missing_citation_count),
    metricRow("Conflicts", safety.conflicting_claim_total),
    metricRow("Safety gate", safety.safety_gate_status?.mvp_readiness_status || "not available"),
  ].join("");
}

function renderReview() {
  const quality = state.quality;
  const review = state.review;
  elements.reviewStatus.innerHTML = [
    metricRow("Draft", quality.draft_count),
    metricRow("Under review", quality.under_review_count),
    metricRow("Edited", quality.edited_count),
    metricRow("Approved", quality.approved_count),
    metricRow("Rejected", quality.rejected_count),
    metricRow("Recent review actions", review.total_reviews),
  ].join("");
}

function renderMonitoring() {
  const usage = state.usage;
  const quality = state.quality;
  elements.monitoringStatus.innerHTML = [
    metricRow("Patients", usage.total_patients),
    metricRow("Documents", usage.total_documents),
    metricRow("Summaries", quality.total_summaries),
    metricRow("Approval rate", percent(quality.approval_rate)),
    metricRow("Rejection rate", percent(quality.rejection_rate)),
    metricRow("Model runs", usage.model_run_count),
  ].join("");
}

function renderLayers() {
  const layers = state.evaluation.evaluation_layers || [];
  elements.evaluationLayers.innerHTML = layers
    .map((item) => `
      <div class="layer-card">
        <div class="panel-heading">
          <strong>${escapeHtml(item.layer)}</strong>
          <span class="badge ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span>
        </div>
        <p>${escapeHtml(item.message)}</p>
        ${item.expected_path ? `<p class="hint">Expected path: ${escapeHtml(item.expected_path)}</p>` : ""}
        ${item.layer === "real_ehr_benchmark" ? `<button type="button" disabled>${state.benchmark.dataset_exists ? "Runner prepared" : "Dataset missing"}</button>` : ""}
      </div>
    `)
    .join("");
}

function renderFunctionalResult(result) {
  elements.functionalResult.innerHTML = `
    <div class="card">
      <div class="panel-heading">
        <strong>Functional Validation</strong>
        <span class="badge ${escapeHtml(result.status)}">${escapeHtml(result.status)}</span>
      </div>
      <p class="hint">${escapeHtml(result.message)}</p>
    </div>
    ${(result.checks || []).map((item) => statusCard(item.name, item.status, item.message)).join("")}
  `;
}

function renderHumanSummary() {
  const human = state.human;
  elements.humanSummary.innerHTML = [
    metricRow("Total evaluations", human.total_evaluations),
    metricRow("Avg factual correctness", displayValue(human.average_factual_correctness_score)),
    metricRow("Avg completeness", displayValue(human.average_completeness_score)),
    metricRow("Avg conciseness", displayValue(human.average_conciseness_score)),
    metricRow("Avg readability", displayValue(human.average_readability_score)),
    metricRow("Avg citation usefulness", displayValue(human.average_citation_usefulness_score)),
    metricRow(
      "Risk distribution",
      (human.hallucination_risk_distribution || []).map((item) => `${item.key}: ${item.count}`).join(", ") || "not available",
    ),
  ].join("");
}

function renderChecklist() {
  const items = [
    ["Seed demo data", state.readiness.golden_path?.some((item) => item.status === "ready")],
    ["Open Doctor UI", true],
    ["Generate summary", state.quality.total_summaries > 0],
    ["Click citation", state.safety.missing_citation_count !== null],
    ["Show safety warning", true],
    ["Edit summary", state.review.edits > 0],
    ["Approve/reject summary", state.review.approvals + state.review.rejections > 0],
    ["Open dashboard", true],
    ["Show evaluation status", true],
    ["Submit human evaluation", state.human.total_evaluations > 0],
  ];
  elements.demoChecklist.innerHTML = items
    .map(([label, done]) => `
      <div class="check-item">
        <span>${escapeHtml(label)}</span>
        <span class="badge ${done ? "passed" : "not_tested"}">${done ? "ready" : "not tested"}</span>
      </div>
    `)
    .join("");
}

function renderLoading() {
  elements.goldenPathStatus.innerHTML = statusCard("Loading", "not_tested", "Loading readiness...");
  elements.providerStatus.innerHTML = card("Loading", "Provider status...", "not_tested");
  elements.safetyStatus.innerHTML = metricRow("Loading", "Safety status...");
  elements.reviewStatus.innerHTML = metricRow("Loading", "Review status...");
  elements.monitoringStatus.innerHTML = metricRow("Loading", "Monitoring status...");
  elements.evaluationLayers.innerHTML = card("Loading", "Evaluation layers...", "not_tested");
  elements.humanSummary.innerHTML = metricRow("Loading", "Human evaluation summary...");
}

function statusCard(name, status, message) {
  return `
    <div class="status-card">
      <div class="panel-heading">
        <strong>${escapeHtml(name)}</strong>
        <span class="badge ${escapeHtml(status)}">${escapeHtml(status)}</span>
      </div>
      <p class="hint">${escapeHtml(message || "")}</p>
    </div>
  `;
}

function card(title, body, status) {
  return `
    <div class="card">
      <div class="panel-heading">
        <strong>${escapeHtml(title)}</strong>
        <span class="badge ${escapeHtml(status)}">${escapeHtml(status)}</span>
      </div>
      <p>${escapeHtml(body)}</p>
    </div>
  `;
}

function metricRow(label, value) {
  return `<div class="metric-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(displayValue(value))}</strong></div>`;
}

function percent(value) {
  if (value === null || value === undefined || value === "not_available") return "not available";
  return `${Math.round(Number(value) * 1000) / 10}%`;
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "not available";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
  return String(value);
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
