import { useEffect, useMemo, useState } from "react";
import { Activity, Database, Play, RefreshCw, Square, TimerReset } from "lucide-react";

import Badge from "../../components/common/Badge.jsx";
import Card from "../../components/common/Card.jsx";
import ErrorState from "../../components/common/ErrorState.jsx";
import LoadingState from "../../components/common/LoadingState.jsx";
import MetricCard from "../../components/common/MetricCard.jsx";
import PageHeader from "../../components/common/PageHeader.jsx";
import { jobsApi } from "../../services/jobsApi.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled", "timed_out"]);

export default function ModelJobsPage() {
  const [readiness, setReadiness] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);

  const runningJobs = useMemo(
    () => jobs.filter((job) => !TERMINAL_STATUSES.has(job.status)),
    [jobs],
  );
  const readyModels = useMemo(
    () => (readiness?.models || []).filter((model) => model.ready).length,
    [readiness],
  );
  const cDriveWarnings = useMemo(
    () => Object.entries(readiness?.cache_paths || {}).filter(([, item]) => item?.points_to_c_drive),
    [readiness],
  );
  const queueStatus = readiness?.queue_status || {};
  const queueMode = readiness?.queue_backend || queueStatus.backend || "in_process";

  useEffect(() => {
    reload({ initial: true });
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (runningJobs.length > 0) {
        refreshJobs();
      }
    }, 1600);
    return () => window.clearInterval(timer);
  }, [runningJobs.length]);

  async function reload({ includeSmoke = false, initial = false } = {}) {
    try {
      if (initial) setLoading(true);
      setBusy(includeSmoke ? "healthcheck" : "refresh");
      setError(null);
      const [readinessData, jobsData] = await Promise.all([
        jobsApi.readiness({ includeSmoke }),
        jobsApi.list(),
      ]);
      setReadiness(readinessData);
      setJobs(jobsData.jobs || []);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
      setBusy("");
    }
  }

  async function refreshJobs() {
    try {
      const jobsData = await jobsApi.list();
      setJobs(jobsData.jobs || []);
    } catch (caught) {
      setError(caught);
    }
  }

  async function enqueueWarmup(model) {
    await runAction("warmup", async () => {
      await jobsApi.enqueue({
        job_type: "model_warmup",
        model_provider: model.provider,
        model_name: model.model_name,
        timeout_seconds: model.model_kind === "ollama" ? 120 : 900,
        payload: { source: "admin_model_jobs_page" },
      });
      await refreshJobs();
    });
  }

  async function enqueueHealthcheck(model) {
    await runAction("healthcheck", async () => {
      await jobsApi.enqueue({
        job_type: "provider_healthcheck",
        model_provider: model.provider,
        model_name: model.model_name,
        timeout_seconds: 120,
        payload: { source: "admin_model_jobs_page" },
      });
      await refreshJobs();
    });
  }

  async function enqueueDefaultWarmups() {
    await runAction("warmup-defaults", async () => {
      await jobsApi.warmupDefaults({ timeoutSeconds: 900 });
      await refreshJobs();
    });
  }

  async function cancelJob(jobId) {
    await runAction(`cancel-${jobId}`, async () => {
      await jobsApi.cancel(jobId);
      await refreshJobs();
    });
  }

  async function runAction(label, callback) {
    try {
      setBusy(label);
      setError(null);
      await callback();
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy("");
    }
  }

  if (loading) return <LoadingState label="Loading model jobs and cache readiness..." />;
  if (error && !readiness) return <ErrorState error={error} />;

  return (
    <div className="stack admin-analytics-page model-jobs-page">
      <PageHeader
        eyebrow="Priority 6"
        title="Model Jobs & Readiness"
        description="Queue long-running model work, verify cached models, warm local providers, and watch progress without blocking API requests."
        icon={Activity}
        actions={(
          <div className="page-header-actions">
            <button className="btn secondary" type="button" onClick={() => reload()} disabled={Boolean(busy)}>
              <RefreshCw className="ui-icon" size={16} aria-hidden="true" />
              Refresh
            </button>
            <button className="btn ghost" type="button" onClick={() => reload({ includeSmoke: true })} disabled={Boolean(busy)}>
              <Activity className="ui-icon" size={16} aria-hidden="true" />
              Live Health Check
            </button>
            <button className="btn" type="button" onClick={enqueueDefaultWarmups} disabled={Boolean(busy)}>
              <Play className="ui-icon" size={16} aria-hidden="true" />
              Warm Defaults
            </button>
          </div>
        )}
      />

      {error ? <ErrorState error={error} /> : null}

      <div className="metric-grid">
        <MetricCard label="Models ready" value={`${readyModels}/${readiness?.models?.length || 0}`} detail="Cache/config/provider readiness" />
        <MetricCard label="Active jobs" value={runningJobs.length} detail="Queued or running model work" />
        <MetricCard label="Cache warnings" value={cDriveWarnings.length} detail={cDriveWarnings.length ? "One or more cache paths point to C drive" : "No C-drive cache paths detected"} />
        <MetricCard
          label="Queue mode"
          value={queueMode === "rq" ? "Redis/RQ" : "in-process"}
          detail={
            queueMode === "rq"
              ? queueStatus.redis_reachable
                ? `${readiness?.queue_name || "queue"} reachable, ${queueStatus.worker_count ?? 0} worker(s)`
                : queueStatus.message || "Redis/RQ configured but not reachable"
              : "Local development mode; set RAG_JOB_BACKEND=rq for durable workers"
          }
        />
      </div>

      <Card title="Cache Status" actions={<Badge tone={cDriveWarnings.length ? "danger" : "success"}>{cDriveWarnings.length ? "attention" : "clean"}</Badge>}>
        <div className="job-cache-grid">
          {Object.entries(readiness?.cache_paths || {}).map(([key, item]) => (
            <div className="job-cache-row" key={key}>
              <div>
                <strong>{key}</strong>
                <span>{item?.value || "not configured"}</span>
              </div>
              <Badge tone={item?.points_to_c_drive ? "danger" : item?.exists ? "success" : "warning"}>
                {item?.points_to_c_drive ? "C drive" : item?.exists ? "exists" : "missing"}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Model Readiness" actions={<Badge tone="info">{busy || "idle"}</Badge>}>
        <div className="job-model-grid">
          {(readiness?.models || []).map((model) => (
            <ModelReadinessCard
              key={`${model.provider}-${model.model_name}`}
              model={model}
              busy={Boolean(busy)}
              onWarmup={() => enqueueWarmup(model)}
              onHealthcheck={() => enqueueHealthcheck(model)}
            />
          ))}
        </div>
      </Card>

      <Card title="Job Queue" actions={<Badge tone={runningJobs.length ? "warning" : "success"}>{runningJobs.length ? "running" : "idle"}</Badge>}>
        <div className="job-list">
          {jobs.length ? jobs.map((job) => (
            <JobRow key={job.job_id} job={job} busy={Boolean(busy)} onCancel={() => cancelJob(job.job_id)} />
          )) : (
            <div className="empty-inline">
              <Database className="ui-icon" size={18} aria-hidden="true" />
              <span>No model jobs have been queued yet.</span>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

function ModelReadinessCard({ model, busy, onWarmup, onHealthcheck }) {
  return (
    <div className="job-model-card">
      <div className="job-model-card-header">
        <div>
          <strong>{model.display_name || model.provider}</strong>
          <span>{model.model_name}</span>
        </div>
        <Badge tone={readinessTone(model.status)}>{model.status}</Badge>
      </div>
      <p>{model.message}</p>
      <div className="job-model-meta">
        <span>{model.model_kind}</span>
        <span>{model.cached ? "cached/configured" : "not cached"}</span>
        {model.external ? <span>external</span> : null}
      </div>
      {model.cache_dir ? <code>{model.cache_dir}</code> : null}
      <div className="job-model-actions">
        <button className="btn ghost" type="button" onClick={onHealthcheck} disabled={busy}>
          <Activity className="ui-icon" size={15} aria-hidden="true" />
          Check
        </button>
        {model.warmup_supported ? (
          <button className="btn secondary" type="button" onClick={onWarmup} disabled={busy}>
            <Play className="ui-icon" size={15} aria-hidden="true" />
            Warm
          </button>
        ) : null}
      </div>
    </div>
  );
}

function JobRow({ job, busy, onCancel }) {
  const progress = Math.round(Number(job.progress || 0) * 100);
  const canCancel = !TERMINAL_STATUSES.has(job.status);
  return (
    <div className="job-row">
      <div className="job-row-main">
        <div>
          <strong>{job.model_provider}</strong>
          <span>{job.job_type} · {job.model_name}</span>
        </div>
        <Badge tone={jobTone(job.status)}>{job.status}</Badge>
      </div>
      <div className="job-progress" aria-label={`${progress}% complete`}>
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className="job-row-footer">
        <span><TimerReset className="ui-icon" size={14} aria-hidden="true" /> timeout {job.timeout_seconds}s</span>
        <span>{job.error_message || job.result?.message || job.job_id}</span>
        {canCancel ? (
          <button className="btn danger" type="button" onClick={onCancel} disabled={busy}>
            <Square className="ui-icon" size={14} aria-hidden="true" />
            Cancel
          </button>
        ) : null}
      </div>
    </div>
  );
}

function readinessTone(status) {
  if (status === "ready") return "success";
  if (["missing_from_cache", "missing_from_ollama", "configuration_required"].includes(status)) return "warning";
  if (["cache_on_c_drive", "ollama_offline"].includes(status)) return "danger";
  return "neutral";
}

function jobTone(status) {
  if (status === "completed") return "success";
  if (status === "running" || status === "queued") return "info";
  if (status === "cancelled") return "warning";
  if (status === "failed" || status === "timed_out") return "danger";
  return "neutral";
}
