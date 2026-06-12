import { useState } from "react";
import Badge from "../common/Badge.jsx";

export default function ProviderSelector({ providers = [], value, onChange, loading, error }) {
  const [showDisabled, setShowDisabled] = useState(false);
  const groups = groupProviders(providers);
  return (
    <div className="provider-panel">
      <div className="section-title">
        <h3>Summary Provider</h3>
        {loading && <span className="muted">Checking provider status...</span>}
      </div>
      {error && <p className="warning-line">Provider metadata is unavailable; using local fallback descriptions.</p>}
      <div className="provider-group-list">
        {groups.map((group) => (
          <section className="provider-group" key={group.key}>
            <div className="provider-group-title">
              <strong>{group.title}</strong>
              <span>{group.description}</span>
            </div>
            <div className="provider-radio-list">
              {visibleProviders(group, showDisabled).map((provider) => {
                const active = provider.provider_name === value;
                return (
                  <button
                    type="button"
                    className={`provider-radio-option ${active ? "active" : ""} ${isDisabledProvider(provider) ? "disabled-provider" : ""}`}
                    key={provider.provider_name}
                    onClick={() => onChange(provider.provider_name)}
                  >
                    <span className="provider-radio-dot" aria-hidden="true" />
                    <span className="provider-card-head">
                      <strong>{provider.display_name}</strong>
                      <Badge tone={providerTone(provider.status)}>{readableStatus(provider.status)}</Badge>
                    </span>
                    <span className="provider-domain">{provider.domain_fit || provider.description}</span>
                    <span className="provider-kind">{providerKind(provider)} - <code>{provider.provider_name}</code></span>
                  </button>
                );
              })}
            </div>
            {group.items.some(isDisabledProvider) && (
              <button type="button" className="provider-collapse-button" onClick={() => setShowDisabled((value) => !value)}>
                {showDisabled ? "Hide disabled baselines" : `Show ${group.items.filter(isDisabledProvider).length} disabled baseline(s)`}
              </button>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}

function providerTone(status = "") {
  const normalized = status.toLowerCase();
  if (normalized === "enabled" || normalized === "available") return "success";
  if (normalized.includes("testing")) return "warning";
  if (normalized.includes("disabled") || normalized.includes("required") || normalized.includes("misconfigured")) return "danger";
  return "info";
}

function readableStatus(status = "") {
  const normalized = status.toLowerCase();
  if (normalized.includes("disabled_until_run_real_baselines")) return "disabled";
  if (normalized.includes("configuration_required")) return "needs config";
  if (normalized.includes("cache_misconfigured")) return "cache issue";
  if (normalized.includes("testing")) return "testing";
  return status.replaceAll("_", " ") || "available";
}

function providerKind(provider) {
  if (provider.provider_name?.includes("qwen") || provider.provider_name?.includes("llama")) return "Local Ollama testing";
  if (provider.provider_name?.includes("gemini")) return "API / governed";
  if (provider.provider_type?.includes("baseline")) return "Baseline";
  if (provider.provider_type?.includes("huggingface")) return "Local Hugging Face";
  return provider.local_model === false || provider.provider_type === "api" ? "API provider" : "Local model";
}

function groupProviders(providers) {
  const groups = [
    {
      key: "recommended",
      title: "Recommended testing providers",
      description: "Best current fit for RAG-based doctor workflow testing.",
      match: (provider) => ["qwen2.5", "llama3.2"].includes(provider.provider_name),
      items: [],
    },
    {
      key: "governed",
      title: "Governed API providers",
      description: "Use only with approved de-identified or governed data.",
      match: (provider) => provider.provider_name?.includes("gemini"),
      items: [],
    },
    {
      key: "baselines",
      title: "Baselines",
      description: "Comparison models. Disabled baselines stay collapsed until needed.",
      match: (provider) => true,
      items: [],
    },
  ];
  providers.forEach((provider) => {
    const target = groups.find((group) => group.match(provider)) || groups[groups.length - 1];
    target.items.push(provider);
  });
  return groups.filter((group) => group.items.length);
}

function visibleProviders(group, showDisabled) {
  if (group.key !== "baselines" || showDisabled) return group.items;
  return group.items.filter((provider) => !isDisabledProvider(provider));
}

function isDisabledProvider(provider) {
  return readableStatus(provider.status).includes("disabled") || readableStatus(provider.status).includes("cache issue");
}
