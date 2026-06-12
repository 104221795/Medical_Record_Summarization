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
    <Card title="Provider" className="golden-card compact-generation-panel">
      <div className="generation-setup">
        <ProviderSelector
          providers={providers}
          loading={providersLoading}
          error={providersError}
          value={provider}
          onChange={setProvider}
        />
        <div className="setup-summary compact">
          <div>
            <span>Patient</span>
            <strong>{selectedPatient?.external_patient_id || selectedPatient?.patient_hash || selectedPatient?.patient_id || "None selected"}</strong>
          </div>
          <div>
            <span>Encounter</span>
            <strong>{selectedEncounter?.encounter_type || selectedEncounter?.department || selectedEncounter?.encounter_id || "All encounters"}</strong>
          </div>
          <div>
            <span>Type</span>
            <strong>{selectedProvider?.local_model === false || selectedProvider?.provider_type === "api" ? "API provider" : "Local/model baseline"}</strong>
          </div>
          <div>
            <span>Context mode</span>
            <Badge tone="info">Evidence-first</Badge>
          </div>
        </div>
        <div className="generate-sticky-action">
          <p className="muted">Draft only. Review evidence before approval.</p>
          {generationError && <p className="warning-line">{generationError.message || String(generationError)}</p>}
          <Button disabled={!canGenerate} onClick={onGenerate}>
            {generating ? "Generating Draft..." : "Generate Draft"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
