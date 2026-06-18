import { useParams, useSearchParams } from "react-router-dom";
import PageHeader from "../../components/common/PageHeader.jsx";
import Badge from "../../components/common/Badge.jsx";
import DraftPreviewCard from "../../components/summary/DraftPreviewCard.jsx";
import GenerationSetupCard from "../../components/summary/GenerationSetupCard.jsx";
import PatientGenerationSelector from "../../components/summary/PatientGenerationSelector.jsx";
import { useSummaryGeneration } from "../../hooks/useSummaryGeneration.js";

export default function DoctorGenerateSummaryPage() {
  const [searchParams] = useSearchParams();
  const { patientId } = useParams();
  const workflow = useSummaryGeneration(searchParams.get("patientId") || patientId || "");

  const generateDraft = async () => {
    await workflow.generateDraft();
  };

  return (
    <div className="doctor-golden-page compact-generate-page">
      <PageHeader
        eyebrow="Doctor Golden Path"
        title="Generate Summary"
        description="Create a draft patient snapshot. Evidence review, editing, and approval happen on the Review & Evidence page."
      />
      <section className="clinical-notice-card compact generate-flow-strip">
        <Badge tone="success">Flow 2 / RAG evidence-first</Badge>
        <div>
          <strong>Doctor generation now uses patient-scoped MiniLM + Qdrant retrieval before provider inference.</strong>
          <p>Notes are chunked, embedded, retrieved by clinical section, checked by a quality gate, then sent to the selected provider as cited context.</p>
        </div>
      </section>
      <div className="generate-compact-workspace">
        <div className="generate-left-panel">
          <PatientGenerationSelector
            patients={workflow.patients}
            loading={workflow.patientsLoading}
            error={workflow.patientsError}
            selectedPatientId={workflow.selectedPatientId}
            onSelectPatient={workflow.setSelectedPatientId}
            patientContext={workflow.patientContext}
            contextLoading={workflow.contextLoading}
            encounterId={workflow.encounterId}
            setEncounterId={workflow.setEncounterId}
            sourceDocumentId={workflow.sourceDocumentId}
            setSourceDocumentId={workflow.setSourceDocumentId}
          />
        </div>
        <div className="generate-right-panel">
          <GenerationSetupCard
            providers={workflow.providers}
            providersLoading={workflow.providersLoading}
            providersError={workflow.providersError}
            provider={workflow.provider}
            setProvider={workflow.setProvider}
            selectedProvider={workflow.selectedProvider}
            selectedPatient={workflow.selectedPatient}
            selectedEncounter={workflow.selectedEncounter}
            generating={workflow.generating}
            generationStatus={workflow.generationStatus}
            generationElapsedSeconds={workflow.generationElapsedSeconds}
            generationJob={workflow.generationJob}
            generationError={workflow.generationError}
            jobReadiness={workflow.jobReadiness}
            jobReadinessError={workflow.jobReadinessError}
            onGenerate={generateDraft}
            onCancelGeneration={workflow.cancelGeneration}
          />
        </div>
        <div className="generate-preview-panel">
          <DraftPreviewCard summary={workflow.generatedSummary} />
        </div>
      </div>
    </div>
  );
}
