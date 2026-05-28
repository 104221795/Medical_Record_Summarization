from __future__ import annotations

from ..fhir_models import Encounter, FhirClinicalInputBundle, Observation, Patient
from ..fhir_schemas import FhirBundleSummaryRequest, FhirBundleSummaryResponse
from ..schemas import (
    CitationSpan,
    ClinicalDocument,
    ClinicalNotesSummaryRequest,
    ClinicalNotesSummaryResponse,
    GroundedSummarySentence,
    IngestRequest,
    SummaryRequest,
)
from .rag import RagService


class ClinicalDataValidationError(ValueError):
    """Raised when submitted clinical/FHIR data cannot be safely associated."""


class ClinicalSummaryPipelineService:
    """Coordinates validated source ingestion and evidence-grounded summarization."""

    def __init__(self, rag_service: RagService):
        self.rag_service = rag_service

    def summarize_clinical_notes(
        self,
        tenant_id: str,
        request: ClinicalNotesSummaryRequest,
    ) -> ClinicalNotesSummaryResponse:
        document = ClinicalDocument(
            document_id=request.document_id or f"clinical-notes-{request.patient_id}",
            document_type="clinical-note",
            encounter_id=request.encounter_id,
            title="Submitted clinical notes",
            text=request.clinical_notes,
        )
        return self._index_and_summarize(
            tenant_id=tenant_id,
            patient_id=request.patient_id,
            documents=[document],
            question=request.clinical_question,
            workflow=request.workflow,
            top_k=request.top_k,
            replace_patient_index=request.replace_patient_index,
        )

    def summarize_fhir_bundle(
        self,
        tenant_id: str,
        request: FhirBundleSummaryRequest,
    ) -> FhirBundleSummaryResponse:
        patient, encounter, observations = self._validate_bundle_relationships(request.bundle)
        documents = [
            ClinicalDocument(
                document_id=f"clinical-notes-{patient.id}",
                document_type="clinical-note",
                encounter_id=encounter.id,
                title="Submitted clinical notes",
                text=request.clinical_notes,
            ),
            *[self._observation_document(observation, encounter.id) for observation in observations],
        ]
        summary = self._index_and_summarize(
            tenant_id=tenant_id,
            patient_id=patient.id,
            documents=documents,
            question=request.clinical_question,
            workflow=request.workflow,
            top_k=request.top_k,
            replace_patient_index=request.replace_patient_index,
        )
        return FhirBundleSummaryResponse(
            source_bundle_id=request.bundle.id,
            summary=summary,
        )

    def _index_and_summarize(
        self,
        tenant_id: str,
        patient_id: str,
        documents: list[ClinicalDocument],
        question: str,
        workflow: str,
        top_k: int,
        replace_patient_index: bool,
    ) -> ClinicalNotesSummaryResponse:
        ingestion = self.rag_service.ingest(
            tenant_id,
            patient_id,
            IngestRequest(
                documents=documents,
                replace_patient_index=replace_patient_index,
            ),
        )
        cited = self.rag_service.summarize_with_citations(
            tenant_id,
            patient_id,
            SummaryRequest(clinical_question=question, workflow=workflow, top_k=top_k),
        )
        sentences = [
            GroundedSummarySentence(
                summary_sentence=sentence.summary_sentence,
                citations=[
                    CitationSpan(
                        document_id=source.document_id,
                        source_chunk_id=source.citation_id,
                        section=source.section,
                        start_idx=source.char_start,
                        end_idx=source.char_end,
                        source_text=source.text,
                    )
                    for source in sentence.source_chunks
                ],
            )
            for sentence in cited.sentences
        ]
        return ClinicalNotesSummaryResponse(
            tenant_id=cited.tenant_id,
            patient_id=cited.patient_id,
            status=cited.status,
            workflow=cited.workflow,
            ingestion=ingestion,
            sentences=sentences,
            guardrail=cited.guardrail,
        )

    @staticmethod
    def _validate_bundle_relationships(
        bundle: FhirClinicalInputBundle,
    ) -> tuple[Patient, Encounter, list[Observation]]:
        patient = next(
            item.resource for item in bundle.entry if isinstance(item.resource, Patient)
        )
        encounters = [
            item.resource for item in bundle.entry if isinstance(item.resource, Encounter)
        ]
        observations = [
            item.resource for item in bundle.entry if isinstance(item.resource, Observation)
        ]
        patient_ref = f"Patient/{patient.id}"
        if any(item.subject.reference != patient_ref for item in encounters):
            raise ClinicalDataValidationError(
                "Every Encounter in the Bundle must reference the submitted Patient."
            )
        encounter_ids = {item.id for item in encounters}
        if any(item.subject.reference != patient_ref for item in observations):
            raise ClinicalDataValidationError(
                "Every Observation in the Bundle must reference the submitted Patient."
            )
        for observation in observations:
            if observation.encounter and observation.encounter.reference not in {
                f"Encounter/{item_id}" for item_id in encounter_ids
            }:
                raise ClinicalDataValidationError(
                    "Observation encounter reference does not exist in the submitted Bundle."
                )
        return patient, encounters[0], observations

    @staticmethod
    def _observation_document(observation: Observation, default_encounter_id: str) -> ClinicalDocument:
        concept = observation.code.text or next(
            (
                coding.display or coding.code
                for coding in observation.code.coding
                if coding.display or coding.code
            ),
            "Observation",
        )
        values: list[str] = []
        if observation.value_string:
            values.append(observation.value_string)
        if observation.value_quantity:
            quantity = observation.value_quantity
            values.append(f"{quantity.value} {quantity.unit or ''}".rstrip())
        values.extend(note["text"] for note in observation.note if note.get("text"))
        encounter_id = (
            observation.encounter.reference.removeprefix("Encounter/")
            if observation.encounter
            else default_encounter_id
        )
        return ClinicalDocument(
            document_id=f"fhir-observation-{observation.id}",
            document_type="fhir-observation",
            encounter_id=encounter_id,
            title=concept,
            text=f"XET NGHIEM:\n{concept}: {'; '.join(values)}",
            metadata={"fhir_resource_type": "Observation", "fhir_resource_id": observation.id},
        )
