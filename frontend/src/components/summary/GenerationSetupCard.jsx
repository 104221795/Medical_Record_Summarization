import Button from "../common/Button.jsx";
import Card from "../common/Card.jsx";
import Badge from "../common/Badge.jsx";
import ProviderSelector from "./ProviderSelector.jsx";

export default function GenerationSetupCard({
  providers,
  providersLoading,
  providersError,
  provider,
  setProvider,
  selectedProvider,
  selectedPatient,
  selectedEncounter,
  generating,
  generationError,
  onGenerate,
}) {
  const canGenerate = Boolean(selectedPatient?.patient_id) && !generating;
  return (
    <Card title="Generation Setup" className="golden-card">
      <div className="generation-setup">
        <ProviderSelector
          providers={providers}
          loading={providersLoading}
          error={providersError}
          value={provider}
          onChange={setProvider}
        />
        <div className="setup-summary">
          <div>
            <span>Selected patient</span>
            <strong>{selectedPatient?.external_patient_id || selectedPatient?.patient_hash || selectedPatient?.patient_id || "None selected"}</strong>
          </div>
          <div>
            <span>Encounter</span>
            <strong>{selectedEncounter?.encounter_type || selectedEncounter?.department || selectedEncounter?.encounter_id || "All encounters"}</strong>
          </div>
          <div>
            <span>Provider type</span>
            <strong>{selectedProvider?.local_model === false || selectedProvider?.provider_type === "api" ? "API provider" : "Local/model baseline"}</strong>
          </div>
          <div>
            <span>Clinical safety</span>
            <Badge tone="warning">Draft only</Badge>
          </div>
        </div>
        <p className="muted">
          This page only creates a draft. Citation and claim checks happen on Review & Evidence.
        </p>
        {generationError && <p className="warning-line">{generationError.message || String(generationError)}</p>}
        <Button disabled={!canGenerate} onClick={onGenerate}>
          {generating ? "Generating Draft..." : "Generate Draft"}
        </Button>
      </div>
    </Card>
  );
}
