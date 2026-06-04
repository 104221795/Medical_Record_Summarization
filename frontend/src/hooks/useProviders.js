import { useEffect, useState } from "react";
import { SUMMARY_PROVIDERS, summaryApi } from "../services/summaryApi.js";

const fallbackProviders = SUMMARY_PROVIDERS.map((provider) => ({
  provider_name: provider,
  display_name: provider,
  model_name: provider,
  status: "fallback",
  domain_fit: "Unknown",
  description: "Backend provider metadata is unavailable.",
}));

export function useProviders() {
  const [providers, setProviders] = useState(fallbackProviders);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    summaryApi.providers()
      .then((data) => {
        if (alive) setProviders(data.providers || fallbackProviders);
      })
      .catch((err) => {
        if (alive) setError(err);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => { alive = false; };
  }, []);

  return { providers, loading, error };
}
