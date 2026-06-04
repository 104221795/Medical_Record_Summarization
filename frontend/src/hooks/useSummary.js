import { useState } from "react";
import { summaryApi } from "../services/summaryApi.js";

export function useSummary() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generate = async (patientId, payload) => {
    setLoading(true);
    setError(null);
    try {
      const created = await summaryApi.generate(patientId, payload);
      const detail = await summaryApi.detail(created.summary_id);
      setSummary(detail);
      return detail;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const load = async (summaryId) => {
    const detail = await summaryApi.detail(summaryId);
    setSummary(detail);
    return detail;
  };

  return { summary, setSummary, generate, load, loading, error };
}
