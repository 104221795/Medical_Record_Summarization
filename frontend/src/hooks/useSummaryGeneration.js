import { useEffect, useMemo, useState } from "react";
import { patientApi } from "../services/patientApi.js";
import { summaryApi } from "../services/summaryApi.js";
import { jobsApi } from "../services/jobsApi.js";
import { useProviders } from "./useProviders.js";

const preferredProviders = [
  "deterministic",
  "qwen2.5",
  "llama3.2",
  "gemini2.5_flash_lite",
  "bart",
  "pegasus",
  "pegasus_pubmed",
  "pegasus_cnn_dailymail",
  "pegasus_xsum",
];

export function useSummaryGeneration(initialPatientId = "") {
  const { providers, loading: providersLoading, error: providersError } = useProviders();
  const [patients, setPatients] = useState([]);
  const [patientsLoading, setPatientsLoading] = useState(true);
  const [patientsError, setPatientsError] = useState(null);
  const [selectedPatientId, setSelectedPatientId] = useState(initialPatientId);
  const [patientContext, setPatientContext] = useState(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState(null);
  const [encounterId, setEncounterId] = useState("");
  const [sourceDocumentId, setSourceDocumentId] = useState("");
  const [provider, setProvider] = useState("deterministic");
  const [generatedSummary, setGeneratedSummary] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [generationStartedAt, setGenerationStartedAt] = useState(null);
  const [generationElapsedSeconds, setGenerationElapsedSeconds] = useState(0);
  const [generationStatus, setGenerationStatus] = useState(null);
  const [generationJob, setGenerationJob] = useState(null);
  const [generationError, setGenerationError] = useState(null);

  useEffect(() => {
    if (!generating || !generationStartedAt) return undefined;
    const timer = window.setInterval(() => {
      const elapsed = Math.max(0, Math.round((Date.now() - generationStartedAt) / 1000));
      setGenerationElapsedSeconds(elapsed);
      setGenerationStatus(buildGenerationStatus(provider, elapsed, "", generationJob));
    }, 750);
    return () => window.clearInterval(timer);
  }, [generating, generationStartedAt, provider, generationJob]);

  useEffect(() => {
    let alive = true;
    setPatientsLoading(true);
    patientApi.list()
      .then((data) => {
        if (!alive) return;
        const items = data?.items || [];
        setPatients(items);
        if (!selectedPatientId && items[0]?.patient_id) setSelectedPatientId(items[0].patient_id);
      })
      .catch((err) => {
        if (alive) setPatientsError(err);
      })
      .finally(() => {
        if (alive) setPatientsLoading(false);
      });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!initialPatientId) return;
    setSelectedPatientId(initialPatientId);
  }, [initialPatientId]);

  useEffect(() => {
    if (!selectedPatientId) {
      setPatientContext(null);
      return;
    }
    let alive = true;
    setEncounterId("");
    setSourceDocumentId("");
    setContextLoading(true);
    setContextError(null);
    Promise.all([
      patientApi.detail(selectedPatientId),
      patientApi.encounters(selectedPatientId),
      patientApi.documents(selectedPatientId),
    ])
      .then(([patient, encounters, documents]) => {
        if (!alive) return;
        const context = {
          patient,
          encounters: encounters?.items || [],
          documents: documents?.items || [],
        };
        setPatientContext(context);
        setEncounterId((current) => current || context.encounters[0]?.encounter_id || "");
        setSourceDocumentId((current) => current || context.documents[0]?.document_id || "");
      })
      .catch((err) => {
        if (alive) setContextError(err);
      })
      .finally(() => {
        if (alive) setContextLoading(false);
      });
    return () => { alive = false; };
  }, [selectedPatientId]);

  const filteredProviders = useMemo(() => (
    preferredProviders
      .map((name) => providers.find((item) => item.provider_name === name) || fallbackProvider(name))
  ), [providers]);

  const selectedProvider = filteredProviders.find((item) => item.provider_name === provider) || filteredProviders[0];
  const selectedPatient = patientContext?.patient || patients.find((item) => item.patient_id === selectedPatientId) || null;
  const selectedEncounter = patientContext?.encounters?.find((item) => item.encounter_id === encounterId) || null;

  const generateDraft = async () => {
    if (!selectedPatientId) throw new Error("Select a patient before generating a summary.");
    setGenerating(true);
    const startedAt = Date.now();
    setGenerationStartedAt(startedAt);
    setGenerationElapsedSeconds(0);
    setGenerationStatus(buildGenerationStatus(provider, 0));
    setGenerationJob(null);
    setGenerationError(null);
    let latestJob = null;
    try {
      const payload = {
        encounter_id: encounterId || null,
        summary_type: "patient_snapshot",
        language: "en",
        model_provider: provider,
      };
      const createdJob = await summaryApi.generateAsync(selectedPatientId, payload);
      latestJob = createdJob;
      setGenerationJob(createdJob);
      setGenerationStatus(buildGenerationStatus(provider, 0, "", createdJob));
      const completedJob = await pollGenerationJob(createdJob.job_id, {
        provider,
        startedAt,
        onUpdate: (job) => {
          latestJob = job;
          setGenerationJob(job);
          const elapsed = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
          setGenerationElapsedSeconds(elapsed);
          setGenerationStatus(buildGenerationStatus(provider, elapsed, "", job));
        },
      });
      const summaryId = completedJob?.result?.summary_id;
      if (!summaryId) {
        throw new Error("Generation job completed without a summary_id.");
      }
      const detail = await summaryApi.detail(summaryId);
      setGeneratedSummary(detail);
      const elapsed = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
      setGenerationElapsedSeconds(elapsed);
      setGenerationStatus(buildGenerationStatus(provider, elapsed, "completed", completedJob));
      return detail;
    } catch (err) {
      setGenerationError(err);
      const elapsed = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
      setGenerationStatus(buildGenerationStatus(provider, elapsed, "failed", latestJob));
      throw err;
    } finally {
      setGenerating(false);
    }
  };

  const cancelGeneration = async () => {
    if (!generationJob?.job_id) return;
    try {
      const cancelled = await jobsApi.cancel(generationJob.job_id);
      setGenerationJob(cancelled);
      setGenerationStatus(buildGenerationStatus(provider, generationElapsedSeconds, "cancelled", cancelled));
      setGenerating(false);
    } catch (err) {
      setGenerationError(err);
    }
  };

  return {
    patients,
    patientsLoading,
    patientsError,
    selectedPatientId,
    setSelectedPatientId,
    selectedPatient,
    patientContext,
    contextLoading,
    contextError,
    encounterId,
    setEncounterId,
    sourceDocumentId,
    setSourceDocumentId,
    selectedEncounter,
    providers: filteredProviders,
    providersLoading,
    providersError,
    provider,
    setProvider,
    selectedProvider,
    generatedSummary,
    generating,
    generationStatus,
    generationElapsedSeconds,
    generationJob,
    generationError,
    generateDraft,
    cancelGeneration,
  };
}

async function pollGenerationJob(jobId, { provider, startedAt, onUpdate }) {
  let latest = await jobsApi.get(jobId);
  onUpdate(latest);
  while (!["completed", "failed", "cancelled", "timed_out"].includes(latest.status)) {
    await delay(1000);
    latest = await jobsApi.get(jobId);
    onUpdate(latest);
  }
  if (latest.status !== "completed") {
    const reason = latest.error_message || latest.result?.message || `Generation job ${latest.status}.`;
    throw new Error(reason);
  }
  return latest;
}

function delay(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function buildGenerationStatus(providerName, elapsedSeconds, terminalState = "", job = null) {
  const heavyProvider = ["qwen2.5", "llama3.2", "gemini2.5_flash_lite", "bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail", "pegasus_xsum"].includes(providerName);
  const stages = [
    ["scope", "Patient scope", "Locking patient and encounter context"],
    ["retrieve", "Retrieve evidence", "MiniLM + Qdrant section-aware evidence search"],
    ["context", "Build clinical context", "Diagnosis, medications, timeline, diagnostics, assessment, plan"],
    ["provider", "Provider generation", providerLabel(providerName, heavyProvider)],
    ["validate", "Citation validation", "Checking unsupported claims and missing evidence"],
    ["ready", "Draft ready", "Open Review & Evidence before approval"],
  ];
  if (job) {
    const mappedState = terminalState || jobStatusToState(job.status);
    const activeIndex = stageIndexForJob(job);
    const gate = job.result?.retrieval_quality_gate;
    const gateMessage = gate?.status && gate.status !== "pass"
      ? `Retrieval quality gate: ${gate.status}. Missing required: ${(gate.missing_required_sections || []).join(", ") || "none"}.`
      : "";
    const message = job.error_message
      || gateMessage
      || job.result?.message
      || currentStepMessage(job.current_step)
      || "Generation job is running in the background.";
    return { state: mappedState, activeIndex, stages, message, progress: Number(job.progress || 0), jobId: job.job_id };
  }
  if (terminalState === "completed") {
    return { state: "completed", activeIndex: stages.length - 1, stages, message: "Draft generated. Review citations before approval." };
  }
  if (terminalState === "cancelled") {
    return { state: "cancelled", activeIndex: 0, stages, message: "Generation was cancelled. No new draft was created." };
  }
  if (terminalState === "failed") {
    return { state: "failed", activeIndex: Math.min(4, stageIndexForElapsed(elapsedSeconds, heavyProvider)), stages, message: "Generation failed safely. Check provider readiness and evidence gate." };
  }
  const activeIndex = stageIndexForElapsed(elapsedSeconds, heavyProvider);
  const slowMessage = elapsedSeconds >= 30
    ? "Still working. Local/cloud model generation can take longer; the request has not been duplicated."
    : "Generating draft. Keep this page open until the draft appears.";
  return { state: "running", activeIndex, stages, message: slowMessage };
}

function jobStatusToState(status) {
  if (status === "completed") return "completed";
  if (status === "failed" || status === "timed_out") return "failed";
  if (status === "cancelled") return "cancelled";
  return "running";
}

function stageIndexForJob(job) {
  const step = job?.current_step || "";
  const map = {
    queued: 0,
    starting: 0,
    patient_scope: 0,
    retrieval_quality_gate: 1,
    clinical_context_builder: 2,
    provider_generation: 3,
    citation_validation: 4,
    draft_ready: 5,
    completed: 5,
  };
  if (step in map) return map[step];
  const progress = Number(job?.progress || 0);
  if (progress >= 0.9) return 5;
  if (progress >= 0.75) return 4;
  if (progress >= 0.5) return 3;
  if (progress >= 0.3) return 2;
  if (progress >= 0.15) return 1;
  return 0;
}

function currentStepMessage(step) {
  const messages = {
    queued: "Generation job is queued.",
    starting: "Starting background generation job.",
    patient_scope: "Checking patient and encounter scope.",
    retrieval_quality_gate: "Running retrieval quality gate before provider generation.",
    clinical_context_builder: "Building structured clinical context from retrieved evidence.",
    provider_generation: "Calling selected provider. Local/cloud models may take a little longer.",
    citation_validation: "Validating citations and unsupported claims.",
    draft_ready: "Draft is ready. Loading Review & Evidence data.",
  };
  return messages[step] || "";
}

function stageIndexForElapsed(elapsedSeconds, heavyProvider) {
  const thresholds = heavyProvider ? [1, 4, 8, 18, 28] : [1, 2, 3, 4, 5];
  const index = thresholds.findIndex((threshold) => elapsedSeconds < threshold);
  return index === -1 ? 4 : index;
}

function providerLabel(providerName, heavyProvider) {
  if (!heavyProvider) return "Fast deterministic baseline";
  const labels = {
    "qwen2.5": "Qwen2.5 local LLM via Ollama",
    "llama3.2": "Llama3.2 local LLM via Ollama",
    "gemini2.5_flash_lite": "Gemini 2.5 Flash Lite cloud provider",
    bart: "BART local Hugging Face model",
    pegasus: "Pegasus local Hugging Face model",
    pegasus_pubmed: "Pegasus PubMed local Hugging Face model",
    pegasus_cnn_dailymail: "Pegasus CNN/DailyMail local Hugging Face model",
    pegasus_xsum: "Pegasus XSum local Hugging Face model",
  };
  return labels[providerName] || "Selected model provider";
}

function fallbackProvider(providerName) {
  const labels = {
    deterministic: ["Deterministic", "extractive baseline", "Fast extractive baseline"],
    "qwen2.5": ["Qwen2.5", "ollama/qwen2.5:3b", "Testing-only local RAG summarizer"],
    "llama3.2": ["Llama3.2", "ollama/llama3.2:3b", "Testing-only local RAG summarizer"],
    "gemini2.5_flash_lite": ["Gemini 2.5 Flash Lite", "gemini/gemini-2.5-flash-lite", "Testing-only citation-aware gateway provider"],
    bart: ["BART", "facebook/bart-large-cnn", "General summarization baseline"],
    pegasus: ["Pegasus", "google/pegasus-pubmed", "Configurable Pegasus baseline"],
    pegasus_pubmed: ["Pegasus PubMed", "google/pegasus-pubmed", "Better medical/scientific fit"],
    pegasus_cnn_dailymail: ["Pegasus CNN/DailyMail", "google/pegasus-cnn_dailymail", "General baseline"],
    pegasus_xsum: ["Pegasus XSum", "google/pegasus-xsum", "Optional XSum baseline"],
  };
  const [displayName, modelName, description] = labels[providerName] || [providerName, providerName, "Provider metadata unavailable."];
  return {
    provider_name: providerName,
    display_name: displayName,
    model_name: modelName,
    status: "metadata_fallback",
    domain_fit: description,
    provider_type: providerName.includes("gemini") ? "api" : "local",
    local_model: !providerName.includes("gemini"),
    description,
  };
}
