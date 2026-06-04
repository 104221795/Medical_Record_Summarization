import Select from "../common/Select.jsx";
import { useProviders } from "../../hooks/useProviders.js";

export default function SummaryProviderSelector({ value, onChange }) {
  const { providers, loading, error } = useProviders();
  const selected = providers.find((provider) => provider.provider_name === value);
  return (
    <div className="provider-select">
      <Select
        label="Provider"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        options={providers.map((provider) => ({
          value: provider.provider_name,
          label: `${provider.display_name} (${provider.status})`,
        }))}
      />
      {loading && <small className="muted">Loading provider status...</small>}
      {error && <small className="warning-line">Provider metadata unavailable; using local fallback list.</small>}
      {selected && (
        <small className="provider-hint">
          <strong>{selected.model_name}</strong> · {selected.domain_fit}. {selected.description}
        </small>
      )}
    </div>
  );
}
