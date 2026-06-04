import { useParams, useSearchParams } from "react-router-dom";
import PageHeader from "../../components/common/PageHeader.jsx";
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
    <div className="doctor-golden-page">
      <PageHeader
        eyebrow="Doctor Golden Path"
        title="Generate Summary"
        description="Create a draft patient snapshot. Evidence review, editing, and approval happen on the Review & Evidence page."
      />
      <div className="generate-summary-layout">
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
        <div className="stack">
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
            generationError={workflow.generationError}
            onGenerate={generateDraft}
          />
          <DraftPreviewCard summary={workflow.generatedSummary} />
        </div>
      </div>
    </div>
  );
}
