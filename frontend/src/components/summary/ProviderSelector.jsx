import Badge from "../common/Badge.jsx";

export default function ProviderSelector({ providers = [], value, onChange, loading, error }) {
  return (
    <div className="provider-panel">
      <div className="section-title">
        <h3>Summary Provider</h3>
        {loading && <span className="muted">Checking provider status...</span>}
      </div>
      {error && <p className="warning-line">Provider metadata is unavailable; using local fallback descriptions.</p>}
      <div className="provider-card-list">
        {providers.map((provider) => {
          const active = provider.provider_name === value;
          return (
            <button
              type="button"
              className={`provider-card-option ${active ? "active" : ""}`}
              key={provider.provider_name}
              onClick={() => onChange(provider.provider_name)}
            >
              <span className="provider-card-head">
                <strong>{provider.display_name}</strong>
                <Badge tone={provider.status === "enabled" || provider.status === "available" ? "success" : "info"}>
                  {provider.status || "available"}
                </Badge>
              </span>
              <span className="provider-model">{provider.model_name}</span>
              <span className="provider-domain">{provider.domain_fit || provider.description}</span>
              <span className="provider-kind">{provider.local_model === false || provider.provider_type === "api" ? "API provider" : "Local model"}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
