const state = {
  result: null,
  selectedSentence: null,
  documentId: "citation-source-note",
  patientId: "patient-demo",
};

const sample = `CHIEF COMPLAINT:
Weak urinary stream and nocturia for three months.

HISTORY OF PRESENT ILLNESS:
Patient reports waking twice each night to void. Denies fever or hematuria.

ASSESSMENT:
Lower urinary tract symptoms, suspected benign prostatic hyperplasia.

PLAN:
Start tamsulosin 0.4 mg once nightly. Refer to urology follow-up in four weeks.

FINDINGS:
Heart size is normal. No focal consolidation. No pulmonary edema.

IMPRESSION:
No acute cardiopulmonary findings.`;

const sourceInput = document.querySelector("#source-input");
const sourcePreview = document.querySelector("#source-preview");
const runButton = document.querySelector("#run");
const summaryList = document.querySelector("#summary-list");
const summaryEmpty = document.querySelector("#summary-empty");
const message = document.querySelector("#message");
const coverage = document.querySelector("#coverage");

function renderSource(ranges = []) {
  const text = sourceInput.value;
  sourcePreview.replaceChildren();
  const sorted = ranges
    .filter((item) => item.document_id === state.documentId)
    .map((item) => ({ start: item.char_start, end: item.char_end }))
    .filter((item) => item.start >= 0 && item.end <= text.length && item.end > item.start)
    .sort((left, right) => left.start - right.start);
  const usable = sorted.reduce((merged, item) => {
    const last = merged[merged.length - 1];
    if (last && item.start <= last.end) {
      last.end = Math.max(last.end, item.end);
    } else {
      merged.push({ ...item });
    }
    return merged;
  }, []);
  let position = 0;
  usable.forEach((range) => {
    if (range.start > position) sourcePreview.append(document.createTextNode(text.slice(position, range.start)));
    const highlight = document.createElement("mark");
    highlight.className = "active";
    highlight.textContent = text.slice(range.start, range.end);
    sourcePreview.append(highlight);
    position = Math.max(position, range.end);
  });
  if (position < text.length) sourcePreview.append(document.createTextNode(text.slice(position)));
}

function selectSentence(index) {
  state.selectedSentence = index;
  summaryList.querySelectorAll(".sentence").forEach((node, itemIndex) => {
    node.classList.toggle("selected", itemIndex === index);
  });
  renderSource(state.result.sentences[index].source_chunks);
}

function renderSummary(result) {
  summaryList.replaceChildren();
  state.result = result;
  if (result.status !== "accepted") {
    summaryEmpty.classList.add("hidden");
    summaryList.classList.add("hidden");
    message.classList.remove("hidden");
    message.textContent = "Summary đã bị guardrail chặn vì thiếu bằng chứng hoặc có mâu thuẫn.";
    renderSource();
    return;
  }
  message.classList.add("hidden");
  summaryEmpty.classList.add("hidden");
  summaryList.classList.remove("hidden");
  coverage.classList.remove("hidden");
  coverage.textContent = `${result.guardrail.citation_coverage}% cited`;
  result.sentences.forEach((sentence, index) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "sentence";
    card.append(document.createTextNode(sentence.summary_sentence));
    const citations = document.createElement("span");
    citations.className = "citation-row";
    sentence.citations.forEach((id) => {
      const chip = document.createElement("span");
      chip.className = "citation";
      chip.textContent = id.slice(0, 12);
      chip.title = id;
      citations.append(chip);
    });
    card.append(citations);
    card.addEventListener("mouseenter", () => renderSource(sentence.source_chunks));
    card.addEventListener("mouseleave", () => {
      if (state.selectedSentence === null) renderSource();
      else renderSource(result.sentences[state.selectedSentence].source_chunks);
    });
    card.addEventListener("click", () => selectSentence(index));
    summaryList.append(card);
  });
  if (result.sentences.length) selectSentence(0);
}

async function runCitationSummary() {
  if (!sourceInput.value.trim()) return;
  runButton.disabled = true;
  runButton.textContent = "Processing...";
  message.classList.add("hidden");
  state.selectedSentence = null;
  const headers = {
    "Content-Type": "application/json",
    "X-Tenant-ID": "vinmec-sandbox",
    "X-User-ID": "clinician-demo",
  };
  try {
    const ingest = await fetch(`/api/v1/patients/${state.patientId}/records:ingest`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        replace_patient_index: true,
        documents: [{
          document_id: state.documentId,
          document_type: "clinical-note",
          title: "Citation review source note",
          text: sourceInput.value,
        }],
      }),
    });
    if (!ingest.ok) throw new Error("Không thể index hồ sơ nguồn.");
    const summary = await fetch(`/api/v1/patients/${state.patientId}/summaries:generate-cited`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        clinical_question: document.querySelector("#question").value,
        workflow: document.querySelector("#workflow").value,
        top_k: 6,
      }),
    });
    const result = await summary.json();
    if (!summary.ok) throw new Error(result.detail || "Không thể sinh tóm tắt.");
    renderSummary(result);
  } catch (error) {
    message.textContent = error.message;
    message.classList.remove("hidden");
  } finally {
    runButton.disabled = false;
    runButton.textContent = "Index and summarize";
  }
}

document.querySelector("#load-sample").addEventListener("click", () => {
  sourceInput.value = sample;
  renderSource();
});
sourceInput.addEventListener("input", () => {
  state.selectedSentence = null;
  renderSource();
});
runButton.addEventListener("click", runCitationSummary);
sourceInput.value = sample;
renderSource();
