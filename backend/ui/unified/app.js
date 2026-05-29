const API_PREFIX = "/api/v1";
const DEFAULT_SESSION = {
  tenantId: "sandbox",
  userId: "doctor-demo",
  roleCode: "doctor",
  isAuthenticated: false,
};

const ROLE_PROFILES = {
  doctor: {
    label: "Doctor workspace access",
    userId: "doctor-demo",
    allowedTabs: [
      "setup",
      "patients",
      "encounters",
      "workspace",
      "hitl",
      "citations",
      "evaluation",
      "integration",
    ],
    canReview: true,
  },
  clinical_admin: {
    label: "Clinical quality and operations access",
    userId: "admin-demo",
    allowedTabs: [
      "setup",
      "patients",
      "encounters",
      "admin",
      "audit",
      "evaluation",
      "integration",
    ],
    canReview: false,
  },
  auditor: {
    label: "Read-only audit and evaluation access",
    userId: "auditor-demo",
    allowedTabs: ["setup", "admin", "audit", "evaluation"],
    canReview: false,
  },
  ai_safety_reviewer: {
    label: "AI safety, citations, and evaluation access",
    userId: "safety-demo",
    allowedTabs: ["setup", "patients", "workspace", "citations", "admin", "audit", "evaluation"],
    canReview: false,
  },
  it_admin: {
    label: "Technical monitoring and integration access",
    userId: "it-demo",
    allowedTabs: ["setup", "admin", "audit", "evaluation", "integration"],
    canReview: false,
  },
  nurse: {
    label: "Limited patient context access; no summary approval",
    userId: "nurse-demo",
    allowedTabs: ["setup", "patients", "encounters", "citations"],
    canReview: false,
  },
};

const REQUIRED_SECTIONS = [
  "Patient Snapshot",
  "Active Problems",
  "Recent Clinical Course",
  "Medications",
  "Labs and Imaging Highlights",
  "Needs Clinician Review",
];

const state = {
  session: loadSession(),
  activeTab: "setup",
  patients: [],
  selectedPatient: null,
  encounters: [],
  documents: [],
  selectedEncounterId: null,
  selectedDocumentId: null,
  summary: null,
  reviews: [],
  citationSource: null,
  metrics: {},
  auditLogs: [],
  evaluation: {},
};

const elements = {
  loginScreen: document.querySelector("#loginScreen"),
  appShell: document.querySelector("#appShell"),
  loginForm: document.querySelector("#loginForm"),
  loginTenantInput: document.querySelector("#loginTenantInput"),
  loginUserInput: document.querySelector("#loginUserInput"),
  loginRoleSelect: document.querySelector("#loginRoleSelect"),
  tenantInput: document.querySelector("#tenantInput"),
  userInput: document.querySelector("#userInput"),
  roleSelect: document.querySelector("#roleSelect"),
  saveSessionBtn: document.querySelector("#saveSessionBtn"),
  logoutBtn: document.querySelector("#logoutBtn"),
  sessionLabel: document.querySelector("#sessionLabel"),
  roleAccessLabel: document.querySelector("#roleAccessLabel"),
  globalMessage: document.querySelector("#globalMessage"),
  setupContent: document.querySelector("#setupContent"),
  patientSearchInput: document.querySelector("#patientSearchInput"),
  patientState: document.querySelector("#patientState"),
  patientTableBody: document.querySelector("#patientTableBody"),
  selectedPatientLabel: document.querySelector("#selectedPatientLabel"),
  patientDetailList: document.querySelector("#patientDetailList"),
  encounterList: document.querySelector("#encounterList"),
  documentList: document.querySelector("#documentList"),
  summaryTypeSelect: document.querySelector("#summaryTypeSelect"),
  providerSelect: document.querySelector("#providerSelect"),
  summaryEncounterSelect: document.querySelector("#summaryEncounterSelect"),
  summaryIdInput: document.querySelector("#summaryIdInput"),
  summaryState: document.querySelector("#summaryState"),
  summaryMeta: document.querySelector("#summaryMeta"),
  summarySections: document.querySelector("#summarySections"),
  safetyPanel: document.querySelector("#safetyPanel"),
  editSummaryText: document.querySelector("#editSummaryText"),
  editCommentInput: document.querySelector("#editCommentInput"),
  approvalCommentInput: document.querySelector("#approvalCommentInput"),
  rejectionReasonSelect: document.querySelector("#rejectionReasonSelect"),
  rejectionCommentInput: document.querySelector("#rejectionCommentInput"),
  startReviewBtn: document.querySelector("#startReviewBtn"),
  saveEditBtn: document.querySelector("#saveEditBtn"),
  approveSummaryBtn: document.querySelector("#approveSummaryBtn"),
  rejectSummaryBtn: document.querySelector("#rejectSummaryBtn"),
  reviewHistoryList: document.querySelector("#reviewHistoryList"),
  citationIdInput: document.querySelector("#citationIdInput"),
  citationClaimList: document.querySelector("#citationClaimList"),
  citationSourcePanel: document.querySelector("#citationSourcePanel"),
  adminMetrics: document.querySelector("#adminMetrics"),
  auditActionInput: document.querySelector("#auditActionInput"),
  auditPatientInput: document.querySelector("#auditPatientInput"),
  auditTableBody: document.querySelector("#auditTableBody"),
  auditDetailPanel: document.querySelector("#auditDetailPanel"),
  evaluationStatus: document.querySelector("#evaluationStatus"),
  functionalChecks: document.querySelector("#functionalChecks"),
  humanEvaluationSummary: document.querySelector("#humanEvaluationSummary"),
  integrationStatus: document.querySelector("#integrationStatus"),
  fhirPayloadInput: document.querySelector("#fhirPayloadInput"),
};

init();

function init() {
  hydrateSessionInputs();
  hydrateLoginInputs();
  bindEvents();
  renderEmptyStates();
  renderAuth();
  if (state.session.isAuthenticated) {
    checkReadiness();
  }
}

function bindEvents() {
  document.addEventListener("click", handleDocumentClick);
  elements.loginForm.addEventListener("submit", loginFromForm);
  elements.saveSessionBtn.addEventListener("click", saveSession);
  elements.logoutBtn.addEventListener("click", logout);
  bind("#checkReadinessBtn", "click", checkReadiness);
  bind("#seedDemoBtn", "click", seedDemoData);
  bind("#loadPatientsBtn", "click", loadPatients);
  bind("#loadPatientContextBtn", "click", reloadPatientContext);
  bind("#generateSummaryBtn", "click", generateSummary);
  bind("#loadSummaryBtn", "click", loadSummaryFromInput);
  bind("#startReviewBtn", "click", startReview);
  bind("#saveEditBtn", "click", saveEdit);
  bind("#approveSummaryBtn", "click", approveSummary);
  bind("#rejectSummaryBtn", "click", rejectSummary);
  bind("#loadReviewsBtn", "click", loadReviews);
  bind("#loadCitationBtn", "click", loadCitationFromInput);
  bind("#loadMetricsBtn", "click", loadAdminMetrics);
  bind("#loadAuditBtn", "click", loadAuditLogs);
  bind("#loadEvaluationBtn", "click", loadEvaluation);
  bind("#runFunctionalBtn", "click", runFunctionalValidation);
  bind("#checkHealthBtn", "click", checkHealth);
  bind("#importFhirBtn", "click", importFhirPayload);
  elements.patientSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadPatients();
  });
}

function bind(selector, eventName, handler) {
  document.querySelector(selector)?.addEventListener(eventName, handler);
}

function handleDocumentClick(event) {
  const tab = event.target.closest("[data-tab]");
  if (tab) {
    setActiveTab(tab.dataset.tab);
    return;
  }

  const quickLoginButton = event.target.closest("[data-login-role]");
  if (quickLoginButton) {
    loginWithRole(quickLoginButton.dataset.loginRole, quickLoginButton.dataset.loginUser);
    return;
  }

  const patientButton = event.target.closest("[data-select-patient]");
  if (patientButton) {
    selectPatient(patientButton.dataset.selectPatient);
    return;
  }

  const encounterButton = event.target.closest("[data-select-encounter]");
  if (encounterButton) {
    state.selectedEncounterId = encounterButton.dataset.selectEncounter || null;
    renderEncounters();
    renderSummaryEncounterOptions();
    return;
  }

  const documentButton = event.target.closest("[data-document-id]");
  if (documentButton) {
    loadDocumentChunks(documentButton.dataset.documentId);
    return;
  }

  const citationButton = event.target.closest("[data-citation-id]");
  if (citationButton) {
    openCitation(citationButton.dataset.citationId);
    setActiveTab("citations");
    return;
  }

  const auditRow = event.target.closest("[data-audit-id]");
  if (auditRow) {
    loadAuditDetail(auditRow.dataset.auditId);
  }
}

function loadSession() {
  try {
    const stored = JSON.parse(localStorage.getItem("clinSummUnifiedSession"));
    return normalizeSession(stored || DEFAULT_SESSION);
  } catch (_error) {
    return { ...DEFAULT_SESSION };
  }
}

function hydrateSessionInputs() {
  elements.tenantInput.value = state.session.tenantId;
  elements.userInput.value = state.session.userId;
  elements.roleSelect.value = state.session.roleCode;
}

function hydrateLoginInputs() {
  elements.loginTenantInput.value = state.session.tenantId || DEFAULT_SESSION.tenantId;
  elements.loginUserInput.value = state.session.userId || DEFAULT_SESSION.userId;
  elements.loginRoleSelect.value = state.session.roleCode || DEFAULT_SESSION.roleCode;
}

function normalizeSession(value) {
  const roleCode = value?.roleCode || DEFAULT_SESSION.roleCode;
  const profile = roleProfile(roleCode);
  return {
    tenantId: value?.tenantId || DEFAULT_SESSION.tenantId,
    userId: value?.userId || profile.userId || DEFAULT_SESSION.userId,
    roleCode,
    isAuthenticated: Boolean(value?.isAuthenticated),
  };
}

function loginFromForm(event) {
  event.preventDefault();
  state.session = normalizeSession({
    tenantId: elements.loginTenantInput.value.trim(),
    userId: elements.loginUserInput.value.trim(),
    roleCode: elements.loginRoleSelect.value,
    isAuthenticated: true,
  });
  persistSession();
  hydrateSessionInputs();
  renderAuth();
  checkReadiness();
  showMessage("Logged in with mock role-based demo headers.", "ok");
}

function loginWithRole(roleCode, userId) {
  const profile = roleProfile(roleCode);
  state.session = normalizeSession({
    tenantId: DEFAULT_SESSION.tenantId,
    userId: userId || profile.userId,
    roleCode,
    isAuthenticated: true,
  });
  persistSession();
  hydrateSessionInputs();
  hydrateLoginInputs();
  renderAuth();
  checkReadiness();
  showMessage(`Logged in as ${roleCode}.`, "ok");
}

function saveSession() {
  const roleCode = elements.roleSelect.value || DEFAULT_SESSION.roleCode;
  state.session = {
    tenantId: elements.tenantInput.value.trim() || DEFAULT_SESSION.tenantId,
    userId: elements.userInput.value.trim() || roleProfile(roleCode).userId || DEFAULT_SESSION.userId,
    roleCode,
    isAuthenticated: true,
  };
  persistSession();
  hydrateLoginInputs();
  renderAuth();
  showMessage("Demo session updated. Future API calls include the selected tenant, user, and role.", "ok");
}

function logout() {
  localStorage.removeItem("clinSummUnifiedSession");
  state.session = { ...DEFAULT_SESSION };
  hydrateSessionInputs();
  hydrateLoginInputs();
  renderAuth();
}

function persistSession() {
  localStorage.setItem("clinSummUnifiedSession", JSON.stringify(state.session));
}

function renderAuth() {
  const isAuthenticated = Boolean(state.session.isAuthenticated);
  elements.loginScreen.classList.toggle("hidden", isAuthenticated);
  elements.appShell.classList.toggle("hidden", !isAuthenticated);
  if (!isAuthenticated) {
    return;
  }
  renderSession();
  applyRoleAccess();
}

function renderSession() {
  elements.sessionLabel.textContent = `${state.session.tenantId} | ${state.session.userId} | ${state.session.roleCode}`;
  elements.roleAccessLabel.textContent = roleProfile(state.session.roleCode).label;
}

function setActiveTab(name) {
  if (!canAccessTab(name)) {
    showMessage(`Role ${state.session.roleCode} cannot access this tab in the demo console.`, "warning");
    return;
  }
  state.activeTab = name;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  });
}

function applyRoleAccess() {
  document.querySelectorAll(".tab").forEach((tab) => {
    const allowed = canAccessTab(tab.dataset.tab);
    tab.classList.toggle("restricted", !allowed);
    tab.disabled = !allowed;
    tab.title = allowed ? "" : `Not available for ${state.session.roleCode}`;
  });

  const canReview = roleProfile(state.session.roleCode).canReview;
  [elements.startReviewBtn, elements.saveEditBtn, elements.approveSummaryBtn, elements.rejectSummaryBtn].forEach((button) => {
    if (!button) return;
    button.disabled = !canReview;
    button.title = canReview ? "" : "Only doctor role can perform HITL review actions.";
  });

  if (!canAccessTab(state.activeTab)) {
    const nextTab = roleProfile(state.session.roleCode).allowedTabs[0] || "setup";
    setActiveTab(nextTab);
  } else {
    setActiveTab(state.activeTab);
  }
}

function roleProfile(roleCode) {
  return ROLE_PROFILES[roleCode] || ROLE_PROFILES.doctor;
}

function canAccessTab(tabName) {
  return roleProfile(state.session.roleCode).allowedTabs.includes(tabName);
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
  return parseResponse(response);
}

async function requestWithHeaders(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": state.session.tenantId,
      "X-User-ID": state.session.userId,
      "X-Role-Code": state.session.roleCode,
      ...(options.headers || {}),
    },
  });
  return parseResponse(response);
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" ? body.detail || JSON.stringify(body) : body;
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return body;
}

function renderEmptyStates() {
  elements.setupContent.innerHTML = card("Readiness", "Click Check Readiness or Seed Demo Data.", "not_tested");
  elements.patientTableBody.innerHTML = rowHtml("No patients loaded yet.", 6);
  elements.patientDetailList.innerHTML = emptyState("Select a patient to load demographics.");
  elements.encounterList.innerHTML = emptyState("Select a patient to load encounters.");
  elements.documentList.innerHTML = emptyState("Select a patient to load documents.");
  elements.summaryMeta.innerHTML = emptyState("Generate or load a summary.");
  elements.summarySections.innerHTML = emptyState("No summary loaded.");
  elements.safetyPanel.innerHTML = emptyState("Safety metrics appear after summary generation.");
  elements.reviewHistoryList.innerHTML = emptyState("No summary review history loaded.");
  elements.citationClaimList.innerHTML = emptyState("Claims and citations appear after loading a summary.");
  elements.citationSourcePanel.innerHTML = emptyState("Click a citation badge or paste a citation ID.");
  elements.adminMetrics.innerHTML = card("Admin metrics", "Switch role if access is denied.", "not_tested");
  elements.auditTableBody.innerHTML = rowHtml("No audit logs loaded.", 5);
  elements.auditDetailPanel.innerHTML = emptyState("Click an audit row to inspect safe metadata.");
  elements.evaluationStatus.innerHTML = card("Evaluation", "Load evaluation status to begin.", "not_tested");
  elements.functionalChecks.innerHTML = emptyState("Functional validation checks have not run.");
  elements.humanEvaluationSummary.innerHTML = emptyState("Human evaluation summary not loaded.");
  elements.integrationStatus.innerHTML = metricRow("Import endpoint", "POST /api/v1/ingestion/import");
}

async function checkReadiness() {
  elements.setupContent.innerHTML = card("Loading", "Checking backend, demo readiness, and evaluation status.", "not_tested");
  try {
    const [health, readiness, evaluation, benchmark] = await Promise.allSettled([
      requestWithHeaders("/healthz"),
      api("/demo/readiness"),
      api("/evaluation/status"),
      api("/evaluation/benchmark/status"),
    ]);
    state.evaluation.readiness = valueOrNull(readiness);
    state.evaluation.status = valueOrNull(evaluation);
    state.evaluation.benchmark = valueOrNull(benchmark);
    elements.setupContent.innerHTML = [
      settledCard("Backend health", health, "FastAPI app and core services"),
      settledCard("Demo readiness", readiness, "Golden path, providers, and demo APIs"),
      settledCard("Evaluation status", evaluation, "Functional, benchmark, and human layers"),
      settledCard("Real EHR benchmark", benchmark, "Pending until credentialed dataset exists"),
    ].join("");
  } catch (error) {
    elements.setupContent.innerHTML = card("Readiness error", error.message, "failed");
  }
}

async function seedDemoData() {
  showMessage("Seeding de-identified demo data...");
  try {
    const result = await api("/demo/seed", { method: "POST", body: "{}" });
    showMessage(result.message || "Demo data is ready.", "ok");
    await loadPatients();
    if (result.patient_id) {
      await selectPatient(result.patient_id);
    }
    if (result.summary_id) {
      await loadSummary(result.summary_id);
    }
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function loadPatients() {
  setPatientMessage("Loading patients...");
  try {
    const params = new URLSearchParams({ page: "1", page_size: "50" });
    const query = elements.patientSearchInput.value.trim();
    if (query) params.set("q", query);
    const result = await api(`/patients?${params.toString()}`);
    state.patients = result.items || [];
    renderPatientTable();
    setPatientMessage(
      state.patients.length
        ? "Patient registry loaded from persisted APIs."
        : "No patients found. Use Demo Setup to seed mock/de-identified data.",
      state.patients.length ? "ok" : "warning",
    );
  } catch (error) {
    setPatientMessage(`${error.message} Use Demo Setup to seed local tables and demo data.`, "error");
  }
}

function renderPatientTable() {
  if (!state.patients.length) {
    elements.patientTableBody.innerHTML = rowHtml("No patient records are available.", 6);
    return;
  }
  elements.patientTableBody.innerHTML = state.patients.map((patient) => `
    <tr data-patient-id="${escapeHtml(patient.patient_id)}">
      <td>
        <strong>${escapeHtml(patient.external_patient_id || patient.patient_hash || patient.patient_id)}</strong>
        <div class="subtle">${escapeHtml(patient.patient_id)}</div>
      </td>
      <td>${escapeHtml(patient.gender || "unknown")}</td>
      <td>${escapeHtml(patient.fhir_patient_id || "not available")}</td>
      <td>${escapeHtml(patient.source_system || "unknown")}</td>
      <td>${patient.is_deidentified ? "mock/de-identified" : "restricted data"}</td>
      <td><button type="button" data-select-patient="${escapeHtml(patient.patient_id)}">Open</button></td>
    </tr>
  `).join("");
}

async function selectPatient(patientId) {
  setActiveTab("encounters");
  elements.selectedPatientLabel.textContent = `Loading patient ${patientId}...`;
  try {
    const [patient, encounters, documents] = await Promise.all([
      api(`/patients/${patientId}`),
      api(`/patients/${patientId}/encounters`),
      api(`/patients/${patientId}/documents`),
    ]);
    state.selectedPatient = patient;
    state.encounters = encounters.items || [];
    state.documents = documents.items || [];
    state.selectedEncounterId = state.encounters[0]?.encounter_id || null;
    state.selectedDocumentId = null;
    renderPatientContext();
  } catch (error) {
    elements.selectedPatientLabel.textContent = error.message;
    elements.patientDetailList.innerHTML = emptyState("Could not load patient detail.");
  }
}

async function reloadPatientContext() {
  if (!state.selectedPatient) {
    showMessage("Select a patient before reloading context.", "warning");
    return;
  }
  await selectPatient(state.selectedPatient.patient_id);
}

function renderPatientContext() {
  const patient = state.selectedPatient;
  const displayId = patient.external_patient_id || patient.patient_hash || patient.patient_id;
  elements.selectedPatientLabel.textContent =
    `Selected patient ${displayId}. Data is shown as demo/de-identified where marked.`;
  elements.patientDetailList.innerHTML = [
    definitionRow("Patient ID", patient.patient_id),
    definitionRow("External ID", patient.external_patient_id || "not available"),
    definitionRow("FHIR Patient ID", patient.fhir_patient_id || "not available"),
    definitionRow("Date of birth", patient.date_of_birth || "not available"),
    definitionRow("Gender", patient.gender || "unknown"),
    definitionRow("Source system", patient.source_system || "unknown"),
    definitionRow("Demo data", patient.is_deidentified ? "mock/de-identified" : "restricted data"),
  ].join("");
  renderEncounters();
  renderDocuments();
  renderSummaryEncounterOptions();
}

function renderEncounters() {
  if (!state.encounters.length) {
    elements.encounterList.innerHTML = emptyState("No encounters available for this patient.");
    return;
  }
  elements.encounterList.innerHTML = state.encounters.map((encounter) => `
    <button
      type="button"
      class="list-item ${encounter.encounter_id === state.selectedEncounterId ? "selected" : ""}"
      data-select-encounter="${escapeHtml(encounter.encounter_id)}"
    >
      <strong>${escapeHtml(encounter.encounter_type || "Encounter")}</strong>
      <span class="subtle">${escapeHtml(encounter.status || "status unknown")} | ${formatDate(encounter.start_time)}</span>
      <span class="subtle">${escapeHtml(encounter.reason_for_visit || "No reason recorded")}</span>
    </button>
  `).join("");
}

function renderDocuments() {
  if (!state.documents.length) {
    elements.documentList.innerHTML = emptyState("No clinical documents available for this patient.");
    return;
  }
  elements.documentList.innerHTML = state.documents.map((documentItem) => `
    <button type="button" class="list-item" data-document-id="${escapeHtml(documentItem.document_id)}">
      <strong>${escapeHtml(documentItem.document_title || documentItem.document_type)}</strong>
      <span class="subtle">${escapeHtml(documentItem.document_type)} | ${formatDate(documentItem.document_datetime)}</span>
      <span class="subtle">Source: ${escapeHtml(documentItem.source_system || "unknown")}</span>
      <span class="subtle">Click to inspect chunks</span>
    </button>
  `).join("");
}

async function loadDocumentChunks(documentId) {
  state.selectedDocumentId = documentId;
  try {
    const [detail, chunks] = await Promise.all([
      api(`/documents/${documentId}`),
      api(`/documents/${documentId}/chunks`),
    ]);
    elements.documentList.innerHTML = `
      <div class="panel-card">
        <h3>${escapeHtml(detail.document_title || detail.document_type)}</h3>
        <div class="metric-list">
          ${metricRow("Document ID", detail.document_id)}
          ${metricRow("Type", detail.document_type)}
          ${metricRow("Timestamp", formatDate(detail.document_datetime))}
          ${metricRow("Chunks", chunks.items?.length || 0)}
        </div>
        <div class="context">${escapeHtml((detail.raw_text || "").slice(0, 1600))}</div>
      </div>
      ${(chunks.items || []).map((chunk) => `
        <div class="list-item">
          <strong>Chunk ${chunk.chunk_index}${chunk.section_name ? ` - ${escapeHtml(chunk.section_name)}` : ""}</strong>
          <span class="subtle">chars ${displayValue(chunk.char_start)} to ${displayValue(chunk.char_end)}</span>
          <div>${escapeHtml(chunk.chunk_text)}</div>
        </div>
      `).join("")}
      <button type="button" class="secondary" id="restoreDocumentsBtn">Back to document list</button>
    `;
    document.querySelector("#restoreDocumentsBtn")?.addEventListener("click", renderDocuments);
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function renderSummaryEncounterOptions() {
  elements.summaryEncounterSelect.innerHTML = "";
  if (!state.encounters.length) {
    elements.summaryEncounterSelect.innerHTML = '<option value="">No encounter selected</option>';
    return;
  }
  state.encounters.forEach((encounter) => {
    const option = document.createElement("option");
    option.value = encounter.encounter_id;
    option.textContent = `${encounter.encounter_type || "encounter"} | ${encounter.status || "status unknown"}`;
    option.selected = encounter.encounter_id === state.selectedEncounterId;
    elements.summaryEncounterSelect.append(option);
  });
}

async function generateSummary() {
  if (!state.selectedPatient) {
    setSummaryMessage("Select a patient before generating a summary.", "warning");
    return;
  }
  setActiveTab("workspace");
  const provider = elements.providerSelect.value;
  setSummaryMessage(`Generating ${provider} draft summary. External providers must be explicitly enabled on the backend.`);
  try {
    const result = await api(`/patients/${state.selectedPatient.patient_id}/summaries/generate`, {
      method: "POST",
      body: JSON.stringify({
        encounter_id: elements.summaryEncounterSelect.value || null,
        summary_type: elements.summaryTypeSelect.value,
        language: "vi",
        model_provider: provider,
        options: {
          require_citations: true,
          include_safety_check: true,
        },
      }),
    });
    await loadSummary(result.summary_id);
    setSummaryMessage("Draft summary generated. Review citations and safety flags before use.", "ok");
  } catch (error) {
    setSummaryMessage(error.message, "error");
  }
}

async function loadSummaryFromInput() {
  const summaryId = elements.summaryIdInput.value.trim();
  if (!summaryId) {
    setSummaryMessage("Enter a summary ID to load.", "warning");
    return;
  }
  await loadSummary(summaryId);
}

async function loadSummary(summaryId) {
  setActiveTab("workspace");
  setSummaryMessage("Loading summary...");
  try {
    const summary = await api(`/summaries/${summaryId}`);
    state.summary = summary;
    elements.summaryIdInput.value = summary.summary_id;
    renderSummary();
    await loadReviews({ quiet: true });
    setSummaryMessage("Summary loaded.", "ok");
  } catch (error) {
    setSummaryMessage(error.message, "error");
  }
}

function renderSummary() {
  if (!state.summary) {
    elements.summaryMeta.innerHTML = emptyState("No summary loaded.");
    elements.summarySections.innerHTML = emptyState("No summary loaded.");
    return;
  }
  const summary = state.summary;
  elements.editSummaryText.value = summary.latest_edited_summary_text || summary.summary_text || "";
  elements.summaryMeta.innerHTML = [
    metricRow("Summary ID", summary.summary_id),
    metricRow("Status", summary.status),
    metricRow("Provider", summary.model_provider || "not available"),
    metricRow("Model", summary.model_name || "not available"),
    metricRow("Latency", summary.latency_ms === null || summary.latency_ms === undefined ? "not available" : `${summary.latency_ms} ms`),
    metricRow("Version", summary.version_number),
    metricRow("Generated", formatDate(summary.generated_at)),
  ].join("");

  const sectionOrder = new Map(REQUIRED_SECTIONS.map((title, index) => [title, index]));
  const sections = [...(summary.sections || [])].sort((a, b) => {
    const aOrder = sectionOrder.has(a.section_title) ? sectionOrder.get(a.section_title) : 99 + a.section_order;
    const bOrder = sectionOrder.has(b.section_title) ? sectionOrder.get(b.section_title) : 99 + b.section_order;
    return aOrder - bOrder;
  });
  elements.summarySections.innerHTML = sections.length
    ? sections.map(renderSection).join("")
    : emptyState("No sections returned by the backend.");
  renderSafetyPanel();
  renderCitationClaimList();
}

function renderSection(section) {
  const claims = section.claims?.length
    ? section.claims.map(renderClaim).join("")
    : emptyState("No atomic claims in this section.");
  return `
    <section class="summary-section">
      <h4>${escapeHtml(section.section_title)}</h4>
      <p class="section-text">${escapeHtml(section.section_text || "")}</p>
      ${claims}
    </section>
  `;
}

function renderClaim(claim) {
  const citations = claim.citations || [];
  const citationButtons = citations.map((citation, index) => `
    <button
      class="citation-badge"
      type="button"
      data-citation-id="${escapeHtml(citation.citation_id)}"
      title="Open citation source"
    >[${index + 1}] ${escapeHtml(citation.source_type)}</button>
  `).join("");
  return `
    <div class="claim ${escapeHtml(claim.support_status || "unchecked")}">
      <div>${escapeHtml(claim.claim_text)}</div>
      <div class="claim-meta">
        <span class="badge">${escapeHtml(claim.claim_type || "general")}</span>
        <span class="badge ${escapeHtml(claim.support_status || "unchecked")}">${escapeHtml(claim.support_status || "unchecked")}</span>
        <span class="badge">risk: ${escapeHtml(claim.clinical_risk_level || "unknown")}</span>
        ${citationButtons || '<span class="missing-badge">No citation</span>'}
      </div>
    </div>
  `;
}

function renderSafetyPanel() {
  const summary = state.summary;
  const unsupportedClaims = (summary.sections || [])
    .flatMap((section) => section.claims || [])
    .filter((claim) => ["unsupported", "insufficient_evidence", "conflicting"].includes(claim.support_status));
  const citationCoverage = Number(summary.citation_coverage || 0);
  const unsupportedCount = Number(summary.unsupported_claim_count || unsupportedClaims.length || 0);
  const conflictCount = Number(summary.conflict_count || 0);
  const gateClass = summary.status === "approved" ? "approved" : unsupportedCount || conflictCount ? "warning" : "ready";
  const gateTitle = summary.status === "approved"
    ? "Approved after human review"
    : unsupportedCount || conflictCount
      ? "Doctor review required"
      : "Ready for clinician review";
  const gateMessage = summary.status === "approved"
    ? "This summary has been approved by a human reviewer. Citations remain available for traceability."
    : unsupportedCount || conflictCount
      ? "There are unsupported or conflicting claims. Review the queue below before approval."
      : "No unsupported or conflicting claims were reported, but this is still a draft until doctor approval.";
  elements.safetyPanel.innerHTML = `
    <section class="safety-gate ${gateClass}">
      <div>
        <span class="safety-kicker">Approval Gate</span>
        <h4>${escapeHtml(gateTitle)}</h4>
        <p>${escapeHtml(gateMessage)}</p>
      </div>
      <span class="status-chip ${escapeHtml(summary.status)}">${escapeHtml(summary.status || "draft")}</span>
    </section>
    <div class="safety-section">
      <div class="safety-section-title">
        <span>Clinical Safety Metrics</span>
        <small>Evidence and risk overview</small>
      </div>
      <div class="safety-grid">
        ${safetyMetricCard("Citation coverage", percent(citationCoverage), citationCoverage >= 0.9 ? "ok" : "warning", "Supported claims with linked evidence")}
        ${safetyMetricCard("Unsupported", displayValue(unsupportedCount), unsupportedCount ? "warning" : "ok", "Claims needing review")}
        ${safetyMetricCard("Conflicts", displayValue(conflictCount), conflictCount ? "danger" : "ok", "Potential evidence conflicts")}
        ${safetyMetricCard("Total claims", displayValue(summary.safety_summary?.total_claim_count), "info", "Atomic clinical statements")}
        ${safetyMetricCard("Supported", displayValue(summary.safety_summary?.supported_claim_count), "ok", "Claims with valid citations")}
        ${safetyMetricCard("Draft status", escapeHtml(summary.status || "draft"), summary.status === "approved" ? "ok" : "warning", "Never official until approved")}
      </div>
    </div>
    <div class="safety-section">
      <div class="safety-section-title">
        <span>Review Queue</span>
        <small>Resolve before approval</small>
      </div>
      ${renderSafetyReviewQueue(unsupportedClaims)}
    </div>
    ${summary.citation_revalidation_required ? '<div class="message warning">Edited text may differ from original claim-to-citation mapping. Revalidate before approval.</div>' : ""}
    ${summary.rejection_reason ? `<div class="message error">Rejected: ${escapeHtml(summary.rejection_reason)} ${escapeHtml(summary.latest_review_comment || "")}</div>` : ""}
  `;
}

function safetyMetricCard(label, value, tone, hint) {
  return `
    <div class="safety-metric ${escapeHtml(tone)}">
      <span>${escapeHtml(label)}</span>
      <strong>${value}</strong>
      <small>${escapeHtml(hint)}</small>
    </div>
  `;
}

function renderSafetyReviewQueue(claims) {
  if (!claims.length) {
    return `
      <div class="review-empty">
        <strong>No unsupported or conflicting claims reported.</strong>
        <span>Doctor review is still required because the summary is AI-generated draft documentation.</span>
      </div>
    `;
  }
  return `
    <div class="review-queue">
      ${claims.map((claim, index) => `
        <article class="review-claim ${escapeHtml(claim.support_status || "unchecked")}">
          <div class="review-claim-top">
            <span class="review-index">#${index + 1}</span>
            <span class="badge ${escapeHtml(claim.support_status || "unchecked")}">${escapeHtml(claim.support_status || "unchecked")}</span>
            <span class="badge">risk: ${escapeHtml(claim.clinical_risk_level || "unknown")}</span>
          </div>
          <p>${escapeHtml(claim.claim_text || "No claim text returned.")}</p>
          <small>Action: verify source evidence, edit wording, or reject/regenerate the summary.</small>
        </article>
      `).join("")}
    </div>
  `;
}

function renderCitationClaimList() {
  if (!state.summary) {
    elements.citationClaimList.innerHTML = emptyState("Load a summary to view claims and citations.");
    return;
  }
  elements.citationClaimList.innerHTML = (state.summary.sections || [])
    .map((section) => `
      <section class="summary-section">
        <h4>${escapeHtml(section.section_title)}</h4>
        ${(section.claims || []).map(renderClaim).join("") || emptyState("No claims.")}
      </section>
    `)
    .join("") || emptyState("No claims returned by the backend.");
}

async function openCitation(citationId) {
  elements.citationIdInput.value = citationId;
  elements.citationSourcePanel.innerHTML = emptyState("Loading citation source...");
  try {
    const source = await api(`/citations/${citationId}/source`);
    state.citationSource = source;
    renderCitationSource(source);
  } catch (error) {
    elements.citationSourcePanel.innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
  }
}

async function loadCitationFromInput() {
  const citationId = elements.citationIdInput.value.trim();
  if (!citationId) {
    elements.citationSourcePanel.innerHTML = '<div class="message warning">Enter a citation ID or click a citation badge.</div>';
    return;
  }
  await openCitation(citationId);
}

function renderCitationSource(source) {
  const highlightedText = source.highlighted_span?.text || "";
  const context = source.surrounding_context || "No surrounding context available.";
  elements.citationSourcePanel.innerHTML = `
    ${metricRow("Citation ID", source.citation_id)}
    ${metricRow("Claim ID", source.claim_id)}
    ${metricRow("Patient ID", source.patient_id)}
    ${metricRow("Source type", source.source_type)}
    ${source.document ? [
      metricRow("Document", source.document.document_title || source.document.document_id),
      metricRow("Document type", source.document.document_type || "not available"),
      metricRow("Source time", formatDate(source.document.document_datetime)),
    ].join("") : ""}
    <div>
      <span>Highlighted source span</span>
      <div class="highlight">${escapeHtml(source.highlighted_span?.text || "No exact span available.")}</div>
    </div>
    <div>
      <span>Surrounding context</span>
      <div class="context">${renderHighlightedContext(context, highlightedText)}</div>
    </div>
  `;
}

function renderHighlightedContext(context, highlightedText) {
  if (!highlightedText) return escapeHtml(context);
  const start = context.toLowerCase().indexOf(highlightedText.toLowerCase());
  if (start < 0) return escapeHtml(context);
  const end = start + highlightedText.length;
  return [
    escapeHtml(context.slice(0, start)),
    `<mark class="inline-highlight">${escapeHtml(context.slice(start, end))}</mark>`,
    escapeHtml(context.slice(end)),
  ].join("");
}

async function startReview() {
  if (!ensureSummary()) return;
  try {
    await api(`/summaries/${state.summary.summary_id}/review/start`, { method: "POST", body: "{}" });
    await loadSummary(state.summary.summary_id);
    showMessage("Review started. Status changed to under_review.", "ok");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function saveEdit() {
  if (!ensureSummary()) return;
  const editedSummaryText = elements.editSummaryText.value.trim();
  if (!editedSummaryText) {
    showMessage("Edited summary text is required.", "warning");
    return;
  }
  try {
    await api(`/summaries/${state.summary.summary_id}/edit`, {
      method: "PATCH",
      body: JSON.stringify({
        edited_summary_text: editedSummaryText,
        edit_comment: elements.editCommentInput.value.trim() || null,
      }),
    });
    await loadSummary(state.summary.summary_id);
    showMessage("Clinician edit saved. Citation mapping may require revalidation.", "ok");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function approveSummary() {
  if (!ensureSummary()) return;
  const confirmed = window.confirm(
    "Ban xac nhan da kiem tra ban tom tat va cac citation lien quan truoc khi phe duyet?",
  );
  if (!confirmed) return;
  try {
    await api(`/summaries/${state.summary.summary_id}/approve`, {
      method: "POST",
      body: JSON.stringify({
        approval_comment: elements.approvalCommentInput.value.trim() || null,
      }),
    });
    await loadSummary(state.summary.summary_id);
    showMessage("Summary approved after doctor review.", "ok");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function rejectSummary() {
  if (!ensureSummary()) return;
  const rejectionComment = elements.rejectionCommentInput.value.trim();
  if (!rejectionComment) {
    showMessage("Rejection comment is required.", "warning");
    return;
  }
  try {
    await api(`/summaries/${state.summary.summary_id}/reject`, {
      method: "POST",
      body: JSON.stringify({
        rejection_reason: elements.rejectionReasonSelect.value,
        rejection_comment: rejectionComment,
      }),
    });
    await loadSummary(state.summary.summary_id);
    showMessage("Summary rejected with reason and comment.", "ok");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function loadReviews(options = {}) {
  if (!state.summary) {
    if (!options.quiet) showMessage("Load a summary before requesting review history.", "warning");
    return;
  }
  try {
    const result = await api(`/summaries/${state.summary.summary_id}/reviews`);
    state.reviews = result.reviews || [];
    renderReviewHistory();
  } catch (error) {
    if (!options.quiet) showMessage(error.message, "error");
    elements.reviewHistoryList.innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
  }
}

function renderReviewHistory() {
  if (!state.reviews.length) {
    elements.reviewHistoryList.innerHTML = emptyState("No review actions recorded for this summary.");
    return;
  }
  elements.reviewHistoryList.innerHTML = state.reviews.map((review) => `
    <div class="history-item">
      <strong>${escapeHtml(review.review_action)}</strong>
      <span class="subtle">${formatDate(review.reviewed_at)} | reviewer ${escapeHtml(review.reviewer_id)}</span>
      <span class="subtle">Status: ${escapeHtml(review.previous_status || "unknown")} -> ${escapeHtml(review.resulting_status || "unknown")}</span>
      ${review.rejection_reason ? `<span class="subtle">Reason: ${escapeHtml(review.rejection_reason)}</span>` : ""}
      ${review.comment ? `<div>${escapeHtml(review.comment)}</div>` : ""}
    </div>
  `).join("");
}

async function loadAdminMetrics() {
  elements.adminMetrics.innerHTML = card("Loading", "Fetching quality, usage, safety, and review metrics.", "not_tested");
  try {
    const [quality, usage, safety, review] = await Promise.all([
      api("/metrics/summary-quality"),
      api("/metrics/usage"),
      api("/metrics/safety"),
      api("/metrics/review"),
    ]);
    state.metrics = { quality, usage, safety, review };
    elements.adminMetrics.innerHTML = [
      card("Total summaries", quality.total_summaries, "ready"),
      card("Approval rate", percent(quality.approval_rate), "ready"),
      card("Rejection rate", percent(quality.rejection_rate), "ready"),
      card("Avg citation coverage", percent(quality.average_citation_coverage), "ready"),
      card("Patients", usage.total_patients, "ready"),
      card("Documents", usage.total_documents, "ready"),
      card("Model runs", usage.model_run_count, "ready"),
      card("Unsupported claims", safety.unsupported_claim_total, "warning"),
      card("Conflicts", safety.conflicting_claim_total, "warning"),
      card("Safety gate", safety.safety_gate_status?.mvp_readiness_status || "not available", safety.safety_gate_status?.mvp_readiness_status || "not_available"),
      card("Total reviews", review.total_reviews, "ready"),
      card("Edits", review.edits, "ready"),
    ].join("");
  } catch (error) {
    elements.adminMetrics.innerHTML = card("Metrics unavailable", `${error.message}. Try clinical_admin, auditor, it_admin, or ai_safety_reviewer role.`, "failed");
  }
}

async function loadAuditLogs() {
  elements.auditTableBody.innerHTML = rowHtml("Loading audit logs...", 5);
  const params = new URLSearchParams({ page: "1", page_size: "25" });
  const action = elements.auditActionInput.value.trim();
  const patientId = elements.auditPatientInput.value.trim();
  if (action) params.set("action", action);
  if (patientId) params.set("patient_id", patientId);
  try {
    const result = await api(`/audit/logs?${params.toString()}`);
    state.auditLogs = result.items || [];
    renderAuditLogs();
  } catch (error) {
    elements.auditTableBody.innerHTML = rowHtml(`${error.message}. Try auditor or clinical_admin role.`, 5);
  }
}

function renderAuditLogs() {
  if (!state.auditLogs.length) {
    elements.auditTableBody.innerHTML = rowHtml("No audit events match the current filters.", 5);
    return;
  }
  elements.auditTableBody.innerHTML = state.auditLogs.map((item) => `
    <tr data-audit-id="${escapeHtml(item.audit_id)}">
      <td>${formatDate(item.created_at || item.timestamp)}</td>
      <td><strong>${escapeHtml(item.action)}</strong></td>
      <td>${escapeHtml(item.user_display_name || item.user_id || "not available")}</td>
      <td>${escapeHtml(item.patient_id || "not available")}</td>
      <td>${escapeHtml(item.resource_type || "not available")}<br /><span class="subtle">${escapeHtml(item.resource_id || "")}</span></td>
    </tr>
  `).join("");
}

async function loadAuditDetail(auditId) {
  elements.auditDetailPanel.innerHTML = emptyState("Loading audit detail...");
  try {
    const detail = await api(`/audit/logs/${auditId}`);
    elements.auditDetailPanel.innerHTML = [
      metricRow("Audit ID", detail.audit_id),
      metricRow("Action", detail.action),
      metricRow("User", detail.user_display_name || detail.user_id || "not available"),
      metricRow("Patient", detail.patient_id || "not available"),
      metricRow("Resource", `${detail.resource_type || "not available"} / ${detail.resource_id || ""}`),
      metricRow("Created", formatDate(detail.created_at || detail.timestamp)),
      `<div><span>Safe metadata</span><pre>${escapeHtml(JSON.stringify(detail.action_metadata || detail.metadata || {}, null, 2))}</pre></div>`,
    ].join("");
  } catch (error) {
    elements.auditDetailPanel.innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
  }
}

async function loadEvaluation() {
  elements.evaluationStatus.innerHTML = card("Loading", "Fetching evaluation status.", "not_tested");
  try {
    const [status, functional, benchmark, human] = await Promise.all([
      api("/evaluation/status"),
      api("/evaluation/functional/status"),
      api("/evaluation/benchmark/status"),
      api("/evaluation/human/summary"),
    ]);
    state.evaluation = { status, functional, benchmark, human };
    renderEvaluation();
  } catch (error) {
    elements.evaluationStatus.innerHTML = card("Evaluation unavailable", error.message, "failed");
  }
}

function renderEvaluation() {
  const { status, functional, benchmark, human } = state.evaluation;
  const layers = status.evaluation_layers || [];
  elements.evaluationStatus.innerHTML = [
    card("Functional validation", functional.status, functional.status),
    card("Real EHR benchmark", benchmark.status, benchmark.status),
    card("Human evaluation", `${human.total_evaluations} submitted`, "ready"),
    ...(status.provider_readiness || []).map((provider) =>
      card(`${provider.provider} provider`, `${provider.status} | ${provider.model_name || "model not available"}`, provider.status),
    ),
    ...layers.map((layer) => card(layer.layer, `${layer.status}: ${layer.message}`, layer.status)),
  ].join("");
  renderFunctionalChecks(functional);
  renderHumanSummary(human);
}

async function runFunctionalValidation() {
  elements.functionalChecks.innerHTML = emptyState("Running functional validation...");
  try {
    const result = await api("/evaluation/functional/run", { method: "POST", body: "{}" });
    state.evaluation.functional = result;
    renderFunctionalChecks(result);
    showMessage("Functional validation completed. Mock data results are not real EHR benchmark performance.", "ok");
  } catch (error) {
    elements.functionalChecks.innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
  }
}

function renderFunctionalChecks(result) {
  elements.functionalChecks.innerHTML = (result.checks || []).map((check) => `
    <div class="status-card">
      <div class="panel-heading">
        <strong>${escapeHtml(check.name)}</strong>
        <span class="badge ${escapeHtml(check.status)}">${escapeHtml(check.status)}</span>
      </div>
      <p class="hint">${escapeHtml(check.message)}</p>
    </div>
  `).join("") || emptyState("No functional checks available.");
}

function renderHumanSummary(human) {
  elements.humanEvaluationSummary.innerHTML = [
    metricRow("Total evaluations", human.total_evaluations),
    metricRow("Avg factual correctness", displayValue(human.average_factual_correctness_score)),
    metricRow("Avg completeness", displayValue(human.average_completeness_score)),
    metricRow("Avg conciseness", displayValue(human.average_conciseness_score)),
    metricRow("Avg readability", displayValue(human.average_readability_score)),
    metricRow("Avg citation usefulness", displayValue(human.average_citation_usefulness_score)),
    metricRow("Risk distribution", (human.hallucination_risk_distribution || []).map((item) => `${item.key}: ${item.count}`).join(", ") || "not available"),
  ].join("");
}

async function checkHealth() {
  elements.integrationStatus.innerHTML = emptyState("Checking backend health...");
  try {
    const health = await requestWithHeaders("/healthz");
    elements.integrationStatus.innerHTML = [
      metricRow("Status", health.status),
      metricRow("Service", health.service),
      metricRow("Generator provider", health.generator_provider),
      metricRow("FHIR endpoint mode", health.fhir_endpoint_mode),
      metricRow("Import endpoint", "POST /api/v1/ingestion/import"),
    ].join("");
  } catch (error) {
    elements.integrationStatus.innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
  }
}

async function importFhirPayload() {
  const raw = elements.fhirPayloadInput.value.trim();
  if (!raw) {
    elements.integrationStatus.innerHTML = '<div class="message warning">Paste a de-identified FHIR-like JSON payload first.</div>';
    return;
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (error) {
    elements.integrationStatus.innerHTML = `<div class="message error">Invalid JSON: ${escapeHtml(error.message)}</div>`;
    return;
  }
  try {
    const result = await api("/ingestion/import", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    elements.integrationStatus.innerHTML = [
      metricRow("Status", result.status),
      metricRow("Accepted records", result.accepted_records),
      metricRow("Skipped duplicates", result.skipped_duplicates),
      metricRow("Chunks created", result.chunks_created),
      metricRow("Batch ID", result.ingestion_batch_id),
    ].join("");
  } catch (error) {
    elements.integrationStatus.innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
  }
}

function ensureSummary() {
  if (!state.summary) {
    showMessage("Generate or load a summary first.", "warning");
    return false;
  }
  return true;
}

function setPatientMessage(message, kind = "") {
  elements.patientState.textContent = message;
  elements.patientState.className = `message ${kind}`.trim();
  elements.patientState.classList.toggle("hidden", !message);
}

function setSummaryMessage(message, kind = "") {
  elements.summaryState.textContent = message;
  elements.summaryState.className = `message ${kind}`.trim();
  elements.summaryState.classList.toggle("hidden", !message);
}

function showMessage(message, kind = "") {
  elements.globalMessage.textContent = message;
  elements.globalMessage.className = `message ${kind}`.trim();
  elements.globalMessage.classList.toggle("hidden", !message);
}

function valueOrNull(settled) {
  return settled.status === "fulfilled" ? settled.value : null;
}

function settledCard(title, settled, fallback) {
  if (settled.status === "fulfilled") {
    const value = settled.value;
    const status = value.status || value.golden_path_readiness || "ready";
    const message = value.message || fallback;
    return card(title, message, String(status).split(" ")[0]);
  }
  return card(title, settled.reason?.message || "Endpoint unavailable.", "failed");
}

function card(title, body, status = "ready") {
  return `
    <div class="card">
      <span>${escapeHtml(title)}</span>
      <strong>${escapeHtml(displayValue(body))}</strong>
      <div class="badge ${escapeHtml(status)}">${escapeHtml(status)}</div>
    </div>
  `;
}

function metricRow(label, value) {
  return `<div class="metric-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(displayValue(value))}</strong></div>`;
}

function definitionRow(label, value) {
  return `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(displayValue(value))}</dd>`;
}

function rowHtml(message, columns) {
  return `<tr><td colspan="${columns}" class="empty">${escapeHtml(message)}</td></tr>`;
}

function emptyState(message) {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}

function percent(value) {
  if (value === null || value === undefined || value === "not_available") return "not available";
  const number = Number(value);
  if (Number.isNaN(number)) return displayValue(value);
  return `${Math.round(number * 1000) / 10}%`;
}

function formatDate(value) {
  if (!value) return "not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "not available";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
  return String(value);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
