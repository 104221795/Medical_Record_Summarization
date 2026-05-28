const API_PREFIX = "/api/v1";
const REQUIRED_SECTIONS = [
  "Patient Snapshot",
  "Active Problems",
  "Recent Clinical Course",
  "Medications",
  "Labs and Imaging Highlights",
  "Needs Clinician Review",
];

const state = {
  session: null,
  patients: [],
  selectedPatient: null,
  encounters: [],
  documents: [],
  selectedEncounterId: null,
  summary: null,
  selectedCitation: null,
  reviews: [],
  editing: false,
};

const nodes = {
  loginView: document.querySelector("#login-view"),
  appView: document.querySelector("#app-view"),
  sessionLabel: document.querySelector("#session-label"),
  logoutButton: document.querySelector("#logout-button"),
  loginButton: document.querySelector("#login-button"),
  roleSelect: document.querySelector("#role-select"),
  userIdInput: document.querySelector("#user-id-input"),
  tenantIdInput: document.querySelector("#tenant-id-input"),
  patientSearch: document.querySelector("#patient-search"),
  refreshPatients: document.querySelector("#refresh-patients"),
  seedDemoData: document.querySelector("#seed-demo-data"),
  patientTableBody: document.querySelector("#patient-table-body"),
  patientListState: document.querySelector("#patient-list-state"),
  patientDetailState: document.querySelector("#patient-detail-state"),
  patientTitle: document.querySelector("#patient-title"),
  patientHeader: document.querySelector("#patient-header"),
  encounterList: document.querySelector("#encounter-list"),
  documentList: document.querySelector("#document-list"),
  openSummaryWorkspace: document.querySelector("#open-summary-workspace"),
  backToPatients: document.querySelector("#back-to-patients"),
  patientListView: document.querySelector("#patient-list-view"),
  patientDetailView: document.querySelector("#patient-detail-view"),
  summaryView: document.querySelector("#summary-view"),
  tabPatients: document.querySelector("#tab-patients"),
  tabDetail: document.querySelector("#tab-detail"),
  tabSummary: document.querySelector("#tab-summary"),
  workspacePatientContext: document.querySelector("#workspace-patient-context"),
  summaryEncounter: document.querySelector("#summary-encounter"),
  summaryType: document.querySelector("#summary-type"),
  generateSummary: document.querySelector("#generate-summary"),
  regenerateSummary: document.querySelector("#regenerate-summary"),
  startReview: document.querySelector("#start-review"),
  editSummary: document.querySelector("#edit-summary"),
  approveSummary: document.querySelector("#approve-summary"),
  rejectSummary: document.querySelector("#reject-summary"),
  reviewHistory: document.querySelector("#review-history"),
  editPanel: document.querySelector("#edit-panel"),
  editSummaryText: document.querySelector("#edit-summary-text"),
  editComment: document.querySelector("#edit-comment"),
  saveEdit: document.querySelector("#save-edit"),
  cancelEdit: document.querySelector("#cancel-edit"),
  summaryState: document.querySelector("#summary-state"),
  summaryEmpty: document.querySelector("#summary-empty"),
  summarySections: document.querySelector("#summary-sections"),
  evidenceEmpty: document.querySelector("#evidence-empty"),
  evidenceContent: document.querySelector("#evidence-content"),
  safetyContent: document.querySelector("#safety-content"),
  reviewHistoryContent: document.querySelector("#review-history-content"),
  approveModal: document.querySelector("#approve-modal"),
  approvalComment: document.querySelector("#approval-comment"),
  confirmApprove: document.querySelector("#confirm-approve"),
  cancelApprove: document.querySelector("#cancel-approve"),
  rejectModal: document.querySelector("#reject-modal"),
  rejectionReason: document.querySelector("#rejection-reason"),
  rejectionComment: document.querySelector("#rejection-comment"),
  rejectError: document.querySelector("#reject-error"),
  confirmReject: document.querySelector("#confirm-reject"),
  cancelReject: document.querySelector("#cancel-reject"),
};

function headers() {
  return {
    "Content-Type": "application/json",
    "X-Tenant-ID": state.session?.tenantId || "sandbox",
    "X-User-ID": state.session?.userId || "doctor-demo",
    "X-Role-Code": state.session?.role || "doctor",
  };
}

async function api(path, options = {}) {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) },
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" ? body.detail || JSON.stringify(body) : body;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return body;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function show(node) { node.classList.remove("hidden"); }
function hide(node) { node.classList.add("hidden"); }

function setMessage(node, text, kind = "") {
  node.textContent = text;
  node.className = `message ${kind}`.trim();
  if (text) show(node);
  else hide(node);
}

function formatDate(value) {
  if (!value) return "Not available";
  return new Date(value).toLocaleString();
}

function patientDisplay(patient) {
  return patient.external_patient_id || patient.patient_hash || patient.patient_id;
}

function ageFromDob(dateOfBirth) {
  if (!dateOfBirth) return null;
  const dob = new Date(`${dateOfBirth}T00:00:00`);
  const now = new Date();
  let age = now.getFullYear() - dob.getFullYear();
  const beforeBirthday = now.getMonth() < dob.getMonth()
    || (now.getMonth() === dob.getMonth() && now.getDate() < dob.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

function normalizeCoverage(value) {
  if (value === null || value === undefined) return "Not calculated";
  const number = Number(value);
  if (Number.isNaN(number)) return value;
  return `${Math.round(number * 100)}%`;
}

function setActiveTab(name) {
  const map = {
    patients: [nodes.patientListView, nodes.tabPatients],
    detail: [nodes.patientDetailView, nodes.tabDetail],
    summary: [nodes.summaryView, nodes.tabSummary],
  };
  Object.values(map).forEach(([panel, tab]) => {
    hide(panel);
    tab.classList.remove("active");
  });
  show(map[name][0]);
  map[name][1].classList.add("active");
}

function loadSession() {
  const raw = localStorage.getItem("doctorGoldenPathSession");
  if (!raw) return;
  try {
    state.session = JSON.parse(raw);
  } catch {
    localStorage.removeItem("doctorGoldenPathSession");
  }
}

function renderSession() {
  if (!state.session) {
    nodes.sessionLabel.textContent = "Not signed in";
    hide(nodes.logoutButton);
    show(nodes.loginView);
    hide(nodes.appView);
    return;
  }
  nodes.sessionLabel.textContent = `${state.session.role} | ${state.session.userId} | tenant ${state.session.tenantId}`;
  show(nodes.logoutButton);
  hide(nodes.loginView);
  show(nodes.appView);
}

async function login() {
  state.session = {
    role: nodes.roleSelect.value,
    userId: nodes.userIdInput.value.trim() || "doctor-demo",
    tenantId: nodes.tenantIdInput.value.trim() || "sandbox",
  };
  localStorage.setItem("doctorGoldenPathSession", JSON.stringify(state.session));
  renderSession();
  await loadPatients();
}

function logout() {
  localStorage.removeItem("doctorGoldenPathSession");
  state.session = null;
  state.patients = [];
  state.selectedPatient = null;
  state.summary = null;
  state.reviews = [];
  state.editing = false;
  renderSession();
}

async function loadPatients() {
  setMessage(nodes.patientListState, "Loading patients...");
  nodes.patientTableBody.replaceChildren();
  try {
    const query = nodes.patientSearch.value.trim();
    const params = new URLSearchParams({ page: "1", page_size: "50" });
    if (query) params.set("q", query);
    const result = await api(`/patients?${params}`);
    const basePatients = result.items || [];
    state.patients = await Promise.all(basePatients.map(enrichPatientRow));
    renderPatientTable();
    setMessage(
      nodes.patientListState,
      state.patients.length
        ? "Patient list loaded from the database APIs."
        : "No patients found. Click Create demo data to initialize a de-identified local fixture.",
      state.patients.length ? "ok" : "",
    );
  } catch (error) {
    setMessage(
      nodes.patientListState,
      `${error.message} Click Create demo data to initialize local tables and de-identified seed records.`,
      "error",
    );
  }
}

async function seedDemoData() {
  nodes.seedDemoData.disabled = true;
  setMessage(nodes.patientListState, "Creating de-identified demo data...");
  try {
    const result = await api("/demo/seed", { method: "POST", body: "{}" });
    setMessage(nodes.patientListState, result.message, "ok");
    await loadPatients();
  } catch (error) {
    setMessage(nodes.patientListState, error.message, "error");
  } finally {
    nodes.seedDemoData.disabled = false;
  }
}

async function enrichPatientRow(patient) {
  const enriched = { ...patient, detail: null, encounters: [] };
  try {
    enriched.detail = await api(`/patients/${patient.patient_id}`);
  } catch {
    enriched.detail = null;
  }
  try {
    const encounters = await api(`/patients/${patient.patient_id}/encounters`);
    enriched.encounters = encounters.items || [];
  } catch {
    enriched.encounters = [];
  }
  return enriched;
}

function renderPatientTable() {
  nodes.patientTableBody.replaceChildren();
  if (!state.patients.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="6" class="empty">No patient records are available.</td>`;
    nodes.patientTableBody.append(row);
    return;
  }
  state.patients.forEach((patient) => {
    const detail = patient.detail || {};
    const encounter = patient.encounters[0];
    const age = ageFromDob(detail.date_of_birth);
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <span class="patient-id">${escapeHtml(patientDisplay(patient))}</span>
        <span class="subtle">${escapeHtml(patient.patient_id)}</span>
      </td>
      <td>${escapeHtml(detail.date_of_birth || "Not in list API")}
        <span class="subtle">${age === null ? "Age unavailable" : `${age} years`}</span>
      </td>
      <td>${escapeHtml(patient.gender || detail.gender || "Unknown")}</td>
      <td>${encounter ? escapeHtml(encounter.encounter_type || encounter.status || encounter.encounter_id) : "No encounter exposed"}</td>
      <td><span class="api-gap">API gap: summary list not exposed</span></td>
      <td><button type="button" data-open-patient="${patient.patient_id}">Open</button></td>
    `;
    nodes.patientTableBody.append(row);
  });
}

async function openPatient(patientId) {
  setActiveTab("detail");
  setMessage(nodes.patientDetailState, "Loading patient context...");
  nodes.patientHeader.replaceChildren();
  nodes.encounterList.replaceChildren();
  nodes.documentList.replaceChildren();
  state.summary = null;
  state.reviews = [];
  state.editing = false;
  hide(nodes.editPanel);
  nodes.reviewHistoryContent.innerHTML = "Review actions will appear here after Start Review, Edit, Approve, or Reject.";
  nodes.reviewHistoryContent.className = "empty";
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
    renderPatientDetail();
    renderWorkspaceContext();
    setMessage(nodes.patientDetailState, "");
  } catch (error) {
    setMessage(nodes.patientDetailState, error.message, "error");
  }
}

function renderPatientDetail() {
  const patient = state.selectedPatient;
  const display = patientDisplay(patient);
  const age = ageFromDob(patient.date_of_birth);
  nodes.patientTitle.textContent = `Patient ${display}`;
  nodes.patientHeader.innerHTML = `
    <dt>Patient ID</dt><dd>${escapeHtml(patient.patient_id)}</dd>
    <dt>External ID</dt><dd>${escapeHtml(patient.external_patient_id || "Not available")}</dd>
    <dt>FHIR ID</dt><dd>${escapeHtml(patient.fhir_patient_id || "Not available")}</dd>
    <dt>Date of birth</dt><dd>${escapeHtml(patient.date_of_birth || "Not available")}</dd>
    <dt>Age</dt><dd>${age === null ? "Not available" : `${age} years`}</dd>
    <dt>Gender</dt><dd>${escapeHtml(patient.gender || "Unknown")}</dd>
    <dt>Source system</dt><dd>${escapeHtml(patient.source_system || "Unknown")}</dd>
    <dt>Data mode</dt><dd>${patient.is_deidentified ? "De-identified/mock" : "Identifiable data"}</dd>
  `;
  renderEncounters();
  renderDocuments();
}

function renderEncounters() {
  nodes.encounterList.replaceChildren();
  if (!state.encounters.length) {
    nodes.encounterList.innerHTML = `<div class="empty">No encounters available for this patient.</div>`;
    return;
  }
  state.encounters.forEach((encounter) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `list-item ${encounter.encounter_id === state.selectedEncounterId ? "selected" : ""}`;
    item.innerHTML = `
      <strong>${escapeHtml(encounter.encounter_type || "Encounter")}</strong>
      <span class="subtle">${escapeHtml(encounter.status || "status unknown")} | ${formatDate(encounter.start_time)}</span>
      <span class="subtle">${escapeHtml(encounter.reason_for_visit || "No reason for visit recorded")}</span>
    `;
    item.addEventListener("click", () => {
      state.selectedEncounterId = encounter.encounter_id;
      renderEncounters();
      renderWorkspaceContext();
    });
    nodes.encounterList.append(item);
  });
}

function renderDocuments() {
  nodes.documentList.replaceChildren();
  if (!state.documents.length) {
    nodes.documentList.innerHTML = `<div class="empty">No clinical documents are available.</div>`;
    return;
  }
  state.documents.forEach((documentItem) => {
    const item = document.createElement("div");
    item.className = "list-item";
    item.innerHTML = `
      <strong>${escapeHtml(documentItem.document_title || documentItem.document_type)}</strong>
      <span class="subtle">${escapeHtml(documentItem.document_type)} | ${formatDate(documentItem.document_datetime)}</span>
      <span class="subtle">${escapeHtml(documentItem.source_system || "source unknown")}</span>
    `;
    nodes.documentList.append(item);
  });
}

function renderWorkspaceContext() {
  const patient = state.selectedPatient;
  if (!patient) {
    nodes.workspacePatientContext.textContent = "Select a patient to begin.";
    return;
  }
  nodes.workspacePatientContext.textContent = `Patient ${patientDisplay(patient)} | ${state.encounters.length} encounter(s) | ${state.documents.length} document(s)`;
  nodes.summaryEncounter.replaceChildren();
  if (!state.encounters.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No encounter";
    nodes.summaryEncounter.append(option);
    return;
  }
  state.encounters.forEach((encounter) => {
    const option = document.createElement("option");
    option.value = encounter.encounter_id;
    option.textContent = `${encounter.encounter_type || "encounter"} | ${encounter.status || "status unknown"}`;
    option.selected = encounter.encounter_id === state.selectedEncounterId;
    nodes.summaryEncounter.append(option);
  });
}

async function generateSummary() {
  if (!state.selectedPatient) return;
  setActiveTab("summary");
  setMessage(nodes.summaryState, "Generating deterministic draft summary from persisted evidence...");
  nodes.generateSummary.disabled = true;
  try {
    const generated = await api(`/patients/${state.selectedPatient.patient_id}/summaries/generate`, {
      method: "POST",
      body: JSON.stringify({
        encounter_id: nodes.summaryEncounter.value || null,
        summary_type: nodes.summaryType.value,
        language: "vi",
        options: { require_citations: true, include_safety_check: true },
      }),
    });
    state.reviews = [];
    state.editing = false;
    await loadSummary(generated.summary_id);
    setMessage(nodes.summaryState, "Draft summary generated. Review citations and safety warnings before use.", "ok");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  } finally {
    nodes.generateSummary.disabled = false;
  }
}

async function regenerateSummary() {
  if (!state.summary) return;
  setMessage(nodes.summaryState, "Regenerating a new draft version...");
  nodes.regenerateSummary.disabled = true;
  try {
    const result = await api(`/summaries/${state.summary.summary_id}/regenerate`, {
      method: "POST",
      body: JSON.stringify({
        reason: "Doctor requested regeneration from golden path UI",
        options: { require_citations: true, include_safety_check: true },
      }),
    });
    await loadSummary(result.new_summary_id);
    setMessage(nodes.summaryState, `New draft version ${result.version_number} created.`, "ok");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  } finally {
    nodes.regenerateSummary.disabled = !state.summary;
  }
}

async function loadSummary(summaryId) {
  state.summary = await api(`/summaries/${summaryId}`);
  renderSummary();
  nodes.regenerateSummary.disabled = false;
  nodes.reviewHistory.disabled = false;
}

function renderSummary() {
  const summary = state.summary;
  nodes.summarySections.replaceChildren();
  hide(nodes.summaryEmpty);
  show(nodes.summarySections);
  REQUIRED_SECTIONS.forEach((title) => {
    const section = summary.sections.find((item) => item.section_title === title);
    if (!section) return;
    const sectionNode = document.createElement("article");
    sectionNode.className = "summary-section";
    const claims = section.claims.map(renderClaim).join("");
    sectionNode.innerHTML = `<h3>${escapeHtml(section.section_title)}</h3>${claims || `<div class="empty">No claims in this section.</div>`}`;
    nodes.summarySections.append(sectionNode);
  });
  renderSafetyPanel();
  renderReviewHistory();
  updateReviewActions();
  resetEvidencePanel();
}

function renderClaim(claim) {
  const citations = claim.citations || [];
  const citationButtons = citations.map((citation, index) => `
    <button class="citation-badge" type="button" data-citation-id="${escapeHtml(citation.citation_id)}">
      [${index + 1}] ${escapeHtml(citation.source_type)}
    </button>
  `).join("");
  const missing = citations.length
    ? ""
    : `<span class="missing-badge">Missing citation</span>`;
  return `
    <div class="claim ${escapeHtml(claim.support_status)}">
      <div>${escapeHtml(claim.claim_text)}</div>
      <div class="claim-meta">
        <span class="badge">${escapeHtml(claim.claim_type || "general")}</span>
        <span class="badge">${escapeHtml(claim.support_status)}</span>
        <span class="badge">risk: ${escapeHtml(claim.clinical_risk_level || "unknown")}</span>
        ${citationButtons}
        ${missing}
      </div>
    </div>
  `;
}

function statusLabel(status) {
  const labels = {
    draft: "Draft — Cần bác sĩ kiểm duyệt.",
    under_review: "Under Review — Doctor is checking citations and safety flags.",
    edited: "Edited — Clinician changes saved; citation mapping may need revalidation.",
    approved: "Approved — Clinician approved. Locked from normal editing.",
    rejected: "Rejected — Not usable as clinical documentation.",
    archived: "Archived — Historical version only.",
  };
  return labels[status] || status;
}

function summaryTextForEditing() {
  if (!state.summary) return "";
  if (state.summary.latest_edited_summary_text) return state.summary.latest_edited_summary_text;
  return state.summary.summary_text
    || state.summary.sections.map((section) => `${section.section_title}\n${section.section_text}`).join("\n\n");
}

function updateReviewActions() {
  const summary = state.summary;
  const isDoctor = state.session?.role === "doctor";
  const mutable = summary && ["draft", "under_review", "edited"].includes(summary.status);
  const canStart = isDoctor && summary && ["draft", "edited"].includes(summary.status);
  nodes.startReview.disabled = !canStart;
  nodes.editSummary.disabled = !isDoctor || !mutable;
  nodes.approveSummary.disabled = !isDoctor || !mutable;
  nodes.rejectSummary.disabled = !isDoctor || !mutable;
  nodes.regenerateSummary.disabled = !summary;
  nodes.reviewHistory.disabled = !summary || !["doctor", "clinical_admin", "auditor"].includes(state.session?.role);
  if (!mutable) hide(nodes.editPanel);
}

function renderSafetyPanel() {
  const summary = state.summary;
  const unsupported = summary.sections
    .flatMap((section) => section.claims)
    .filter((claim) => ["unsupported", "insufficient_evidence", "conflicting"].includes(claim.support_status));
  const warnings = unsupported.length
    ? unsupported.map((claim) => `
      <div class="warning-item">
        <strong>${escapeHtml(claim.support_status)}</strong>: ${escapeHtml(claim.claim_text)}
      </div>
    `).join("")
    : `<div class="warning-item">No unsupported or conflicting claims reported by the backend.</div>`;
  nodes.safetyContent.className = "";
  nodes.safetyContent.innerHTML = `
    <div class="message">
      <span class="status-chip ${escapeHtml(summary.status)}">${escapeHtml(summary.status)}</span>
      ${escapeHtml(statusLabel(summary.status))}
    </div>
    <div class="safety-grid">
      <div class="metric"><span>Status</span><strong>${escapeHtml(summary.status)}</strong></div>
      <div class="metric"><span>Citation coverage</span><strong>${normalizeCoverage(summary.citation_coverage)}</strong></div>
      <div class="metric"><span>Unsupported claims</span><strong>${summary.unsupported_claim_count}</strong></div>
      <div class="metric"><span>Conflicts</span><strong>${summary.conflict_count}</strong></div>
    </div>
    <div class="message">
      ${summary.status === "approved"
        ? "This AI-assisted summary was explicitly approved by a doctor. Source citations remain available for audit."
        : "This is an AI-generated Draft. It is not approved, not official, and requires doctor review before clinical use."}
    </div>
    ${summary.unsupported_claim_count > 0 ? `<div class="message error">Unsupported or insufficient-evidence claims remain visible. Approval may be blocked for critical unsupported claims.</div>` : ""}
    ${summary.citation_revalidation_required ? `<div class="message error">Edited text may differ from the original claim-to-citation mapping and requires clinician revalidation.</div>` : ""}
    ${summary.rejection_reason ? `<div class="message error">Rejected reason: ${escapeHtml(summary.rejection_reason)}${summary.latest_review_comment ? ` — ${escapeHtml(summary.latest_review_comment)}` : ""}</div>` : ""}
    <div class="warning-list">${warnings}</div>
  `;
}

async function startReview() {
  if (!state.summary) return;
  setMessage(nodes.summaryState, "Starting clinician review...");
  nodes.startReview.disabled = true;
  try {
    await api(`/summaries/${state.summary.summary_id}/review/start`, { method: "POST", body: "{}" });
    await loadSummary(state.summary.summary_id);
    await loadReviewHistory();
    setMessage(nodes.summaryState, "Summary is now under review.", "ok");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  } finally {
    updateReviewActions();
  }
}

function enterEditMode() {
  if (!state.summary) return;
  nodes.editSummaryText.value = summaryTextForEditing();
  nodes.editComment.value = "";
  state.editing = true;
  show(nodes.editPanel);
}

function cancelEdit() {
  state.editing = false;
  hide(nodes.editPanel);
}

async function saveEdit() {
  if (!state.summary) return;
  const editedText = nodes.editSummaryText.value.trim();
  if (!editedText) {
    setMessage(nodes.summaryState, "Edited summary text is required.", "error");
    return;
  }
  nodes.saveEdit.disabled = true;
  setMessage(nodes.summaryState, "Saving clinician edit...");
  try {
    await api(`/summaries/${state.summary.summary_id}/edit`, {
      method: "PATCH",
      body: JSON.stringify({
        edited_summary_text: editedText,
        edit_comment: nodes.editComment.value.trim() || null,
      }),
    });
    cancelEdit();
    await loadSummary(state.summary.summary_id);
    await loadReviewHistory();
    setMessage(nodes.summaryState, "Edited summary saved. Citation mapping requires clinician revalidation.", "ok");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  } finally {
    nodes.saveEdit.disabled = false;
    updateReviewActions();
  }
}

function showApproveModal() {
  if (!state.summary) return;
  nodes.approvalComment.value = "Reviewed and approved for clinician workflow use.";
  show(nodes.approveModal);
}

function hideApproveModal() {
  hide(nodes.approveModal);
}

async function confirmApprove() {
  if (!state.summary) return;
  nodes.confirmApprove.disabled = true;
  setMessage(nodes.summaryState, "Approving summary...");
  try {
    await api(`/summaries/${state.summary.summary_id}/approve`, {
      method: "POST",
      body: JSON.stringify({ approval_comment: nodes.approvalComment.value.trim() || null }),
    });
    hideApproveModal();
    await loadSummary(state.summary.summary_id);
    await loadReviewHistory();
    setMessage(nodes.summaryState, "Summary approved and locked from normal editing.", "ok");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  } finally {
    nodes.confirmApprove.disabled = false;
    updateReviewActions();
  }
}

function showRejectModal() {
  if (!state.summary) return;
  nodes.rejectionReason.value = "";
  nodes.rejectionComment.value = "";
  setMessage(nodes.rejectError, "");
  show(nodes.rejectModal);
}

function hideRejectModal() {
  hide(nodes.rejectModal);
}

async function confirmReject() {
  if (!state.summary) return;
  const rejectionReason = nodes.rejectionReason.value;
  const rejectionComment = nodes.rejectionComment.value.trim();
  if (!rejectionReason || !rejectionComment) {
    setMessage(nodes.rejectError, "Rejection reason and comment are required.", "error");
    return;
  }
  nodes.confirmReject.disabled = true;
  setMessage(nodes.summaryState, "Rejecting summary...");
  try {
    await api(`/summaries/${state.summary.summary_id}/reject`, {
      method: "POST",
      body: JSON.stringify({
        rejection_reason: rejectionReason,
        rejection_comment: rejectionComment,
      }),
    });
    hideRejectModal();
    await loadSummary(state.summary.summary_id);
    await loadReviewHistory();
    setMessage(nodes.summaryState, "Summary rejected with review feedback.", "ok");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  } finally {
    nodes.confirmReject.disabled = false;
    updateReviewActions();
  }
}

async function loadReviewHistory() {
  if (!state.summary) return;
  setMessage(nodes.summaryState, "Loading review history...");
  try {
    const result = await api(`/summaries/${state.summary.summary_id}/reviews`);
    state.reviews = result.reviews || [];
    renderReviewHistory();
    setMessage(nodes.summaryState, "");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  }
}

function renderReviewHistory() {
  if (!state.reviews.length) {
    nodes.reviewHistoryContent.className = "empty";
    nodes.reviewHistoryContent.textContent = state.summary
      ? "No review actions recorded yet."
      : "Review actions will appear here after Start Review, Edit, Approve, or Reject.";
    return;
  }
  nodes.reviewHistoryContent.className = "";
  nodes.reviewHistoryContent.innerHTML = state.reviews.map((review) => `
    <div class="history-item">
      <strong>${escapeHtml(review.review_action)}</strong>
      <span class="subtle">${formatDate(review.reviewed_at)} | reviewer ${escapeHtml(review.reviewer_id)}</span>
      <span class="subtle">Status: ${escapeHtml(review.previous_status || "unknown")} -> ${escapeHtml(review.resulting_status || "unknown")}</span>
      ${review.rejection_reason ? `<span class="subtle">Reason: ${escapeHtml(review.rejection_reason)}</span>` : ""}
      ${review.edit_distance_score !== null && review.edit_distance_score !== undefined ? `<span class="subtle">Edit distance: ${escapeHtml(review.edit_distance_score)}</span>` : ""}
      ${review.comment ? `<div>${escapeHtml(review.comment)}</div>` : ""}
    </div>
  `).join("");
}

async function openCitation(citationId) {
  setMessage(nodes.summaryState, "Loading citation source...");
  try {
    const source = await api(`/citations/${citationId}/source`);
    state.selectedCitation = source;
    renderEvidencePanel(source);
    setMessage(nodes.summaryState, "");
  } catch (error) {
    setMessage(nodes.summaryState, error.message, "error");
  }
}

function resetEvidencePanel() {
  show(nodes.evidenceEmpty);
  hide(nodes.evidenceContent);
  nodes.evidenceContent.replaceChildren();
}

function renderEvidencePanel(source) {
  hide(nodes.evidenceEmpty);
  show(nodes.evidenceContent);
  const documentMeta = source.document
    ? `
      <div class="evidence-row">
        <span class="evidence-label">Document</span>
        <div>${escapeHtml(source.document.document_title || "Untitled source")}</div>
        <span class="subtle">${escapeHtml(source.document.document_type || "unknown type")} | ${formatDate(source.document.document_datetime)}</span>
      </div>
    `
    : "";
  nodes.evidenceContent.innerHTML = `
    <div class="evidence-row">
      <span class="evidence-label">Source type</span>
      <div>${escapeHtml(source.source_type)}</div>
    </div>
    ${documentMeta}
    <div class="evidence-row">
      <span class="evidence-label">Highlighted source span</span>
      <div class="highlight">${escapeHtml(source.highlighted_span?.text || "No exact span available.")}</div>
    </div>
    <div class="evidence-row">
      <span class="evidence-label">Surrounding context</span>
      <div class="context">${escapeHtml(source.surrounding_context || "No surrounding context available.")}</div>
    </div>
    <div class="evidence-row">
      <span class="evidence-label">Source metadata</span>
      <pre class="context">${escapeHtml(JSON.stringify(source.source_metadata || {}, null, 2))}</pre>
    </div>
  `;
}

document.addEventListener("click", (event) => {
  const patientButton = event.target.closest("[data-open-patient]");
  if (patientButton) openPatient(patientButton.dataset.openPatient);
  const citationButton = event.target.closest("[data-citation-id]");
  if (citationButton) openCitation(citationButton.dataset.citationId);
});

nodes.loginButton.addEventListener("click", login);
nodes.logoutButton.addEventListener("click", logout);
nodes.refreshPatients.addEventListener("click", loadPatients);
nodes.seedDemoData.addEventListener("click", seedDemoData);
nodes.patientSearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadPatients();
});
nodes.backToPatients.addEventListener("click", () => setActiveTab("patients"));
nodes.openSummaryWorkspace.addEventListener("click", () => {
  setActiveTab("summary");
  renderWorkspaceContext();
});
nodes.tabPatients.addEventListener("click", () => setActiveTab("patients"));
nodes.tabDetail.addEventListener("click", () => setActiveTab("detail"));
nodes.tabSummary.addEventListener("click", () => {
  setActiveTab("summary");
  renderWorkspaceContext();
});
nodes.generateSummary.addEventListener("click", generateSummary);
nodes.regenerateSummary.addEventListener("click", regenerateSummary);
nodes.startReview.addEventListener("click", startReview);
nodes.editSummary.addEventListener("click", enterEditMode);
nodes.saveEdit.addEventListener("click", saveEdit);
nodes.cancelEdit.addEventListener("click", cancelEdit);
nodes.approveSummary.addEventListener("click", showApproveModal);
nodes.rejectSummary.addEventListener("click", showRejectModal);
nodes.reviewHistory.addEventListener("click", loadReviewHistory);
nodes.confirmApprove.addEventListener("click", confirmApprove);
nodes.cancelApprove.addEventListener("click", hideApproveModal);
nodes.confirmReject.addEventListener("click", confirmReject);
nodes.cancelReject.addEventListener("click", hideRejectModal);

loadSession();
renderSession();
if (state.session) loadPatients();
