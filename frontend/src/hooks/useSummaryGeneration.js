import { useEffect, useMemo, useState } from "react";
import { patientApi } from "../services/patientApi.js";
import { summaryApi } from "../services/summaryApi.js";
import { useProviders } from "./useProviders.js";

const preferredProviders = [
  "deterministic",
  "gemini",
  "bart",
  "pegasus_pubmed",
  "pegasus_cnn_dailymail",
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
  const [generationError, setGenerationError] = useState(null);

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
    setGenerationError(null);
    try {
      const created = await summaryApi.generate(selectedPatientId, {
        encounter_id: encounterId || null,
        summary_type: "patient_snapshot",
        language: "vi",
        model_provider: provider,
      });
      const detail = await summaryApi.detail(created.summary_id);
      setGeneratedSummary(detail);
      return detail;
    } catch (err) {
      setGenerationError(err);
      throw err;
    } finally {
      setGenerating(false);
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
    generationError,
    generateDraft,
  };
}

function fallbackProvider(providerName) {
  const labels = {
    deterministic: ["Deterministic", "extractive baseline", "Fast extractive baseline"],
    gemini: ["Gemini", "API LLM provider", "External API LLM provider"],
    bart: ["BART", "facebook/bart-large-cnn", "General summarization baseline"],
    pegasus_pubmed: ["Pegasus PubMed", "google/pegasus-pubmed", "Better medical/scientific fit"],
    pegasus_cnn_dailymail: ["Pegasus CNN/DailyMail", "google/pegasus-cnn_dailymail", "General baseline"],
  };
  const [displayName, modelName, description] = labels[providerName] || [providerName, providerName, "Provider metadata unavailable."];
  return {
    provider_name: providerName,
    display_name: displayName,
    model_name: modelName,
    status: "metadata_fallback",
    domain_fit: description,
    provider_type: providerName === "gemini" ? "api" : "local",
    local_model: providerName !== "gemini",
    description,
  };
}
