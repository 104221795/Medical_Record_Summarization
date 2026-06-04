import { patientApi } from "../services/patientApi.js";
import { useApi } from "./useApi.js";

export function usePatients() {
  return useApi(() => patientApi.list(), []);
}

export function usePatientContext(patientId) {
  return useApi(async () => {
    if (!patientId) return null;
    const [patient, encounters, documents] = await Promise.all([
      patientApi.detail(patientId),
      patientApi.encounters(patientId),
      patientApi.documents(patientId),
    ]);
    return { patient, encounters: encounters.items || [], documents: documents.items || [] };
  }, [patientId]);
}
