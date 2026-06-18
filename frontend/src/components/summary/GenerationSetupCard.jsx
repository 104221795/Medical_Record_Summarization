import { AlertTriangle, CheckCircle2, Circle, Clock3, LoaderCircle } from "lucide-react";
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
  generationStatus,
  generationElapsedSeconds,
  generationJob,
  generationError,
  jobReadiness,
  jobReadinessError,
  onGenerate,
  onCancelGeneration,
}) {
  const queueStatus = jobReadiness?.queue_status;
  const workerRequired = jobReadiness?.queue_backend === "rq";
  const workerAvailable = !workerRequired
    || (queueStatus?.redis_reachable && Number(queueStatus?.worker_count || 0) > 0);
  const canGenerate = Boolean(selectedPatient?.patient_id)
    && Boolean(selectedProvider?.selectable)
    && workerAvailable
    && !generating;
  return (
    <Card title="Provider" className="golden-card compact-generation-panel">
      <div className="generation-setup">
        <ProviderSelector
          providers={providers}
          loading={providersLoading}
          error={providersError}
          value={provider}
          onChange={setProvider}
          collapseAfterGeneration={Boolean(generationJob)}
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
            <Badge tone="success">RAG MiniLM + Qdrant</Badge>
          </div>
        </div>
        <div className="generate-sticky-action">
          <p className="muted">Draft only. Review evidence before approval.</p>
          <div className="generation-readiness-row">
            <Badge tone={selectedProvider?.selectable ? "success" : "danger"}>
              Provider {selectedProvider?.selectable ? "ready" : "unavailable"}
            </Badge>
            <Badge tone={workerAvailable ? "success" : "danger"}>
              Worker {workerAvailable ? "ready" : "unavailable"}
            </Badge>
          </div>
          {jobReadinessError && (
            <p className="warning-line">Worker readiness could not be verified.</p>
          )}
          {!workerAvailable && (
            <p className="warning-line">
              {queueStatus?.redis_reachable
                ? "Redis is reachable, but no background worker is available."
                : "Redis is unavailable. Generation is temporarily disabled."}
            </p>
          )}
          {!selectedProvider?.selectable && (
            <p className="warning-line">
              {selectedProvider?.disabled_reason || "Selected provider is unavailable."}
            </p>
          )}
          <GenerationProgress
            generating={generating}
            status={generationStatus}
            elapsedSeconds={generationElapsedSeconds}
            job={generationJob}
            onCancel={onCancelGeneration}
          />
          {generationError && <p className="warning-line">{generationError.message || String(generationError)}</p>}
          <Button disabled={!canGenerate} onClick={onGenerate}>
            {generating ? "Generating Draft..." : "Generate Draft"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function GenerationProgress({ generating, status, elapsedSeconds, job, onCancel }) {
  if (!generating && !status) return null;
  const activeIndex = Number(status?.activeIndex || 0);
  const stages = status?.stages || [];
  const state = status?.state || (generating ? "running" : "idle");
  return (
    <div className={`generation-progress-panel ${state}`}>
      <div className="generation-progress-header">
        <div>
          <Clock3 className="ui-icon" size={15} aria-hidden="true" />
          <strong>{state === "completed" ? "Draft generated" : state === "failed" ? "Generation stopped" : "Generating draft"}</strong>
        </div>
        <Badge tone={state === "completed" ? "success" : state === "failed" ? "danger" : state === "cancelled" ? "warning" : "info"}>
          {formatElapsed(elapsedSeconds)}
        </Badge>
      </div>
      {job?.job_id && (
        <div className="generation-job-row">
          <span>Job {compactId(job.job_id)}</span>
          <span>{job.current_step || job.status}</span>
        </div>
      )}
      <p>{status?.message || "Preparing the clinical draft."}</p>
      <div className="generation-stage-list">
        {stages.map(([key, label, detail], index) => {
          const stageState = index < activeIndex || state === "completed" ? "done" : index === activeIndex ? state : "pending";
          const Icon = stageState === "done" ? CheckCircle2 : stageState === "failed" ? AlertTriangle : stageState === "running" ? LoaderCircle : Circle;
          return (
            <div className={`generation-stage ${stageState}`} key={key}>
              <Icon className={`ui-icon ${stageState === "running" ? "loading-spinner" : ""}`} size={15} aria-hidden="true" />
              <div>
                <strong>{label}</strong>
                <span>{detail}</span>
              </div>
            </div>
          );
        })}
      </div>
      {generating && job?.job_id && onCancel && (
        <button className="btn danger generation-cancel-btn" type="button" onClick={onCancel}>
          Cancel Generation
        </button>
      )}
    </div>
  );
}

function formatElapsed(seconds = 0) {
  const safe = Math.max(0, Number(seconds || 0));
  if (safe < 60) return `${safe}s`;
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
}

function compactId(value = "") {
  const text = String(value || "");
  return text.length > 16 ? `${text.slice(0, 8)}...${text.slice(-4)}` : text;
}
