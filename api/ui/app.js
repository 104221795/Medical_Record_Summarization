const state = {
  config: null,
  workflow: "record",
  inputType: "text",
  response: null,
  activeTab: "summary",
};

const input = document.querySelector("#clinical-input");
const workflowPicker = document.querySelector("#workflow-picker");
const count = document.querySelector("#character-count");
const summarizeButton = document.querySelector("#summarize");
const emptyResult = document.querySelector("#empty-result");
const reviewStatus = document.querySelector("#review-status");
const tabs = document.querySelectorAll(".tab");

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function updateCount() {
  const max = state.config?.max_input_chars;
  const length = input.value.length;
  count.textContent = max
    ? `${length.toLocaleString()} / ${max.toLocaleString()} characters`
    : `${length.toLocaleString()} characters`;
}

function renderCapabilities() {
  const host = document.querySelector("#capabilities");
  const captions = [
    "Always-current chart view",
    "Claims linked to evidence",
    "Citation coverage checks",
    "Standards-based interchange",
  ];
  state.config.capabilities.forEach((label, index) => {
    const card = element("article", "capability");
    card.append(element("strong", "", label), element("span", "", captions[index]));
    host.appendChild(card);
  });
}

function setWorkflow(workflow) {
  state.workflow = workflow;
  workflowPicker.querySelectorAll("button").forEach((button) => {
    const selected = button.dataset.workflow === workflow;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-checked", String(selected));
  });
}

function renderWorkflows() {
  Object.entries(state.config.workflows).forEach(([key, workflow]) => {
    const button = element("button", "workflow-option");
    button.type = "button";
    button.dataset.workflow = key;
    button.setAttribute("role", "radio");
    button.append(element("strong", "", workflow.label), element("span", "", workflow.description));
    button.addEventListener("click", () => setWorkflow(key));
    workflowPicker.appendChild(button);
  });
  setWorkflow(state.workflow);
}

function setInputType(inputType) {
  state.inputType = inputType;
  document.querySelectorAll(".source-toggle").forEach((button) => {
    button.classList.toggle("active", button.dataset.inputType === inputType);
  });
  const isFhir = inputType === "fhir";
  document.querySelector("#source-label").textContent = isFhir
    ? "FHIR R4 Bundle JSON"
    : "De-identified clinical text";
  input.placeholder = isFhir
    ? "Paste a FHIR Bundle or load the sample integration payload..."
    : "Paste a de-identified clinical record or load a sample...";
  input.value = "";
  updateCount();
}

async function loadSample() {
  if (state.inputType === "fhir") {
    const response = await fetch("/api/examples/fhir");
    input.value = JSON.stringify(await response.json(), null, 2);
  } else {
    input.value = state.config.workflows[state.workflow].example;
  }
  updateCount();
  input.focus();
}

function setTab(tabName) {
  state.activeTab = tabName;
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === tabName));
  ["summary", "safety", "integration"].forEach((tab) => {
    document.querySelector(`#${tab}-tab`).classList.toggle("hidden", tab !== tabName || !state.response);
  });
}

function claimsText(summary) {
  const labels = {
    clinical_overview: "Clinical overview",
    active_problems: "Active problems",
    key_findings: "Key findings",
    treatments_and_plan: "Treatments and plan",
    follow_up: "Follow-up / pending actions",
    uncertainties: "Uncertainties",
  };
  return Object.entries(labels)
    .map(([key, label]) => `${label.toUpperCase()}\n${summary[key].map((claim) => `- ${claim}`).join("\n")}`)
    .join("\n\n");
}

function renderSummary(data) {
  const host = document.querySelector("#summary-sections");
  host.replaceChildren();
  const labels = {
    clinical_overview: "Clinical overview",
    active_problems: "Active problems",
    key_findings: "Key findings",
    treatments_and_plan: "Treatments and plan",
    follow_up: "Follow-up / pending actions",
    uncertainties: "Uncertainties",
  };
  Object.entries(labels).forEach(([key, label]) => {
    const section = element("section", "summary-group");
    section.appendChild(element("h3", "", label));
    const list = element("ul", "");
    (data.summary[key] || []).forEach((claim) => list.appendChild(element("li", "", claim)));
    section.appendChild(list);
    host.appendChild(section);
  });
  document.querySelector("#result-model").textContent =
    `${data.model} | ${new Date(data.generated_at).toLocaleString()} | Request ${data.request_id}`;
}

function renderSafety(data) {
  const score = data.safety.citation_coverage;
  document.querySelector("#coverage-score").textContent = `${score}%`;
  document.querySelector("#coverage-meter").style.width = `${score}%`;
  const alerts = document.querySelector("#safety-alerts");
  alerts.replaceChildren();
  data.safety.alerts.forEach((message) => {
    const alert = element("p", score === 100 ? "alert success" : "alert warning", message);
    alerts.appendChild(alert);
  });
  const evidence = document.querySelector("#evidence-list");
  evidence.replaceChildren();
  data.sources.forEach((source) => {
    const card = element("article", "evidence");
    const title = element("div", "evidence-title");
    title.append(element("b", "", `[${source.id}]`), element("span", "", source.label));
    card.append(title, element("p", "", source.text));
    evidence.appendChild(card);
  });
}

function renderResult(data) {
  state.response = data;
  emptyResult.classList.add("hidden");
  reviewStatus.classList.remove("hidden");
  reviewStatus.textContent = "Clinician review required";
  renderSummary(data);
  renderSafety(data);
  setTab("summary");
}

function showError(message) {
  emptyResult.classList.remove("hidden");
  emptyResult.replaceChildren(
    element("h3", "error-title", "Summary could not be generated"),
    element("p", "", message)
  );
  state.response = null;
  reviewStatus.classList.add("hidden");
  setTab("summary");
}

async function generateSummary() {
  const value = input.value.trim();
  if (!value) {
    showError("Enter clinical context or load a sample first.");
    return;
  }
  summarizeButton.disabled = true;
  summarizeButton.classList.add("loading");
  summarizeButton.querySelector(".button-label").textContent = "Generating and checking...";
  try {
    const payload = {
      workflow: state.workflow,
      input_type: state.inputType,
    };
    if (state.inputType === "fhir") payload.fhir_bundle = value;
    else payload.text = value;
    const response = await fetch("/api/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Generation failed.");
    renderResult(result);
  } catch (error) {
    showError(error.message);
  } finally {
    summarizeButton.disabled = false;
    summarizeButton.classList.remove("loading");
    summarizeButton.querySelector(".button-label").textContent = "Generate grounded summary";
  }
}

function downloadFhir() {
  const blob = new Blob([JSON.stringify(state.response.fhir_export, null, 2)], {
    type: "application/fhir+json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `clinical-summary-draft-${state.response.request_id}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function init() {
  const response = await fetch("/api/config");
  state.config = await response.json();
  document.querySelector("#model-name").textContent = state.config.model;
  renderCapabilities();
  renderWorkflows();
  updateCount();
  if (!state.config.configured) {
    showError("Set GEMINI_API_KEY in .env before using the Active Summarizer.");
  }
}

document.querySelector("#load-example").addEventListener("click", loadSample);
document.querySelector("#summarize").addEventListener("click", generateSummary);
document.querySelector("#copy-summary").addEventListener("click", async () => {
  await navigator.clipboard.writeText(claimsText(state.response.summary));
  document.querySelector("#copy-summary").textContent = "Copied";
  setTimeout(() => { document.querySelector("#copy-summary").textContent = "Copy draft"; }, 1200);
});
document.querySelector("#download-fhir").addEventListener("click", downloadFhir);
document.querySelectorAll(".source-toggle").forEach((button) => {
  button.addEventListener("click", () => setInputType(button.dataset.inputType));
});
tabs.forEach((tab) => tab.addEventListener("click", () => setTab(tab.dataset.tab)));
input.addEventListener("input", updateCount);

init().catch(() => showError("Unable to load prototype configuration."));
