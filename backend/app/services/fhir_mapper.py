import html
import uuid
from datetime import UTC, datetime

from ..config import Settings
from ..fhir_models import (
    BundleEntry,
    BundleRequest,
    ClinicalImpression,
    ClinicalImpressionFinding,
    Composition,
    CompositionSection,
    Condition,
    ConditionEvidence,
    FhirCodeableConcept,
    FhirCoding,
    FhirIdentifier,
    FhirNarrative,
    FhirReference,
    FhirTransactionBundle,
)
from ..fhir_schemas import (
    ConditionMappingInput,
    FhirMappingRequest,
    FhirMappingResponse,
    FhirMockPushResponse,
)
from .medical_guardrail import (
    ContradictionDetector,
    MedicalGuardrail,
    MedicalGuardrailResult,
    OnnxNliContradictionDetector,
)


CLINICAL_STATUS_SYSTEM = "http://terminology.hl7.org/CodeSystem/condition-clinical"
VERIFICATION_STATUS_SYSTEM = "http://terminology.hl7.org/CodeSystem/condition-ver-status"
CONDITION_CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/condition-category"
LOINC_SYSTEM = "http://loinc.org"


class FhirMappingError(ValueError):
    pass


class FhirSafetyValidationError(FhirMappingError):
    def __init__(self, report: MedicalGuardrailResult):
        super().__init__("Medical guardrail blocked FHIR/EMR writeback.")
        self.report = report


class FhirMapperService:
    """Maps approved, evidence-grounded content into a scoped FHIR R4 transaction."""

    def __init__(
        self,
        settings: Settings,
        nli_detector: ContradictionDetector | None = None,
    ):
        self.settings = settings
        self.nli_detector = nli_detector or self._build_nli_detector(settings)

    def map_to_transaction(
        self,
        tenant_id: str,
        request: FhirMappingRequest,
    ) -> FhirMappingResponse:
        guardrail_report = self.validate_for_writeback(
            "\n\n".join(item.text for item in request.source_documents),
            request.summary,
        )
        if not guardrail_report.allow_emr_writeback:
            raise FhirSafetyValidationError(guardrail_report)
        created_at = datetime.now(UTC)
        patient_ref = FhirReference(reference=f"Patient/{request.patient_id}")
        encounter_ref = (
            FhirReference(reference=f"Encounter/{request.encounter_id}")
            if request.encounter_id
            else None
        )
        document_ids = {item.document_id for item in request.source_documents}
        for condition in request.conditions:
            unknown = set(condition.evidence_document_ids) - document_ids
            if unknown:
                raise FhirMappingError(
                    "Condition evidence_document_ids must refer to submitted source documents: "
                    + ", ".join(sorted(unknown))
                )

        composition_id = request.composition_id or self._stable_id(
            tenant_id, request.patient_id, "composition"
        )
        impression_id = request.clinical_impression_id or self._stable_id(
            tenant_id, request.patient_id, "clinical-impression"
        )
        composition_urn = self._urn("Composition", composition_id)
        impression_urn = self._urn("ClinicalImpression", impression_id)

        condition_entries: list[BundleEntry] = []
        condition_refs: list[FhirReference] = []
        for item in request.conditions:
            resource = self._condition(item, patient_ref, encounter_ref, created_at)
            urn = self._urn("Condition", item.condition_id)
            condition_refs.append(FhirReference(reference=urn, display=item.display))
            condition_entries.append(self._entry(urn, resource, f"Condition/{item.condition_id}"))

        impression = self._clinical_impression(
            request, impression_id, patient_ref, encounter_ref, composition_urn, condition_refs, created_at
        )
        composition = self._composition(
            request,
            composition_id,
            patient_ref,
            encounter_ref,
            impression_urn,
            condition_refs,
            created_at,
        )
        entries = [
            self._entry(composition_urn, composition, f"Composition/{composition.id}"),
            self._entry(impression_urn, impression, f"ClinicalImpression/{impression.id}"),
            *condition_entries,
        ]
        bundle = FhirTransactionBundle(
            id=self._stable_id(tenant_id, request.patient_id, "transaction"),
            timestamp=created_at,
            entry=entries,
        )
        return FhirMappingResponse(
            tenant_id=tenant_id,
            patient_id=request.patient_id,
            generated_at=created_at,
            medical_guardrail=guardrail_report,
            bundle=bundle,
        )

    def validate_for_writeback(
        self,
        raw_clinical_text: str,
        ai_summary_json,
    ) -> MedicalGuardrailResult:
        return MedicalGuardrail(
            raw_clinical_text,
            ai_summary_json,
            nli_detector=self.nli_detector,
            require_nli=self.settings.medical_nli_required_for_writeback,
        ).validate()

    def mock_push(
        self,
        destination_base_url: str | None,
        bundle: FhirTransactionBundle,
    ) -> FhirMockPushResponse:
        destination = destination_base_url or self.settings.fhir_mock_base_url.rstrip("/")
        resource_types = [entry.resource.resource_type for entry in bundle.entry]
        return FhirMockPushResponse(
            status="accepted-for-mock-delivery",
            destination_base_url=destination,
            transaction_id=bundle.id,
            resources_received=len(bundle.entry),
            resource_types=resource_types,
            persisted=False,
            message=(
                "Mock only: FHIR R4 transaction validated locally and was not transmitted "
                "to an external HIS/FHIR server."
            ),
        )

    def _composition(
        self,
        request: FhirMappingRequest,
        composition_id: str,
        patient: FhirReference,
        encounter: FhirReference | None,
        impression_urn: str,
        condition_refs: list[FhirReference],
        created_at: datetime,
    ) -> Composition:
        claim_items = "".join(
            f"<li>{html.escape(claim.text).replace(chr(10), '<br/>')} "
            f"<small>Evidence: {html.escape(', '.join(claim.evidence_ids))}</small></li>"
            for claim in request.summary.claims
        )
        evidence_items = "".join(
            f"<li><strong>{html.escape(item.title or item.document_id)}</strong>: "
            f"{html.escape(item.text).replace(chr(10), '<br/>')}</li>"
            for item in request.source_documents
        )
        summary_section = CompositionSection(
            title="AI-assisted clinical summary - pending clinician attestation",
            code=self._concept("AI-assisted clinical summary"),
            text=self._narrative(f"<ol>{claim_items}</ol>"),
            entry=[FhirReference(reference=impression_urn)],
        )
        source_section = CompositionSection(
            title="Source clinical text",
            text=self._narrative(f"<ul>{evidence_items}</ul>"),
        )
        sections = [summary_section, source_section]
        if condition_refs:
            sections.append(
                CompositionSection(
                    title="Submitted conditions",
                    text=self._narrative(
                        "<p>Structured conditions submitted by the calling clinical workflow.</p>"
                    ),
                    entry=condition_refs,
                )
            )
        return Composition(
            id=composition_id,
            identifier=FhirIdentifier(
                system="https://clinical-intelligence.local/fhir/identifier/composition",
                value=composition_id,
            ),
            status="preliminary",
            type=FhirCodeableConcept(
                coding=[FhirCoding(system=LOINC_SYSTEM, code="18842-5", display="Discharge summary")],
                text="AI-assisted medical record summary draft",
            ),
            subject=patient,
            encounter=encounter,
            date=created_at,
            author=[
                FhirReference(
                    reference=request.author_reference or self.settings.fhir_mapper_device_reference,
                    display="Clinical Summarization Service",
                )
            ],
            title="AI-assisted Medical Record Summary - Clinician Review Required",
            text=self._narrative("<p>Preliminary AI draft. Clinician attestation is required.</p>"),
            section=sections,
        )

    def _clinical_impression(
        self,
        request: FhirMappingRequest,
        impression_id: str,
        patient: FhirReference,
        encounter: FhirReference | None,
        composition_urn: str,
        condition_refs: list[FhirReference],
        created_at: datetime,
    ) -> ClinicalImpression:
        summary_text = " ".join(claim.text for claim in request.summary.claims)
        findings = [
            ClinicalImpressionFinding(
                itemCodeableConcept=self._concept(claim.text),
                basis=f"Retrieved evidence chunks: {', '.join(claim.evidence_ids)}",
            )
            for claim in request.summary.claims
        ]
        supporting = [FhirReference(reference=composition_urn), *condition_refs]
        return ClinicalImpression(
            id=impression_id,
            status="completed",
            description="AI-assisted grounded assessment draft pending clinician attestation.",
            subject=patient,
            encounter=encounter,
            date=created_at,
            assessor=FhirReference(reference=self.settings.fhir_mapper_device_reference),
            supportingInfo=supporting,
            summary=summary_text,
            finding=findings,
            note=[{"text": "AI-generated draft validated for evidence citations; not a signed diagnosis."}],
        )

    def _condition(
        self,
        item: ConditionMappingInput,
        patient: FhirReference,
        encounter: FhirReference | None,
        created_at: datetime,
    ) -> Condition:
        code = FhirCodeableConcept(
            coding=(
                [FhirCoding(system=item.code_system, code=item.code, display=item.display)]
                if item.code
                else []
            ),
            text=item.display,
        )
        return Condition(
            id=item.condition_id,
            clinicalStatus=FhirCodeableConcept(
                coding=[FhirCoding(system=CLINICAL_STATUS_SYSTEM, code=item.clinical_status)]
            )
            if item.verification_status != "entered-in-error"
            else None,
            verificationStatus=FhirCodeableConcept(
                coding=[FhirCoding(system=VERIFICATION_STATUS_SYSTEM, code=item.verification_status)]
            ),
            category=[
                FhirCodeableConcept(
                    coding=[FhirCoding(system=CONDITION_CATEGORY_SYSTEM, code=item.category)]
                )
            ],
            code=code,
            subject=patient,
            encounter=encounter,
            recordedDate=created_at,
            evidence=[
                ConditionEvidence(
                    detail=[
                        FhirReference(reference=f"DocumentReference/{document_id}")
                        for document_id in item.evidence_document_ids
                    ]
                )
            ]
            if item.evidence_document_ids
            else [],
            note=[{"text": "Condition provided as structured clinical input; not inferred by AI."}],
        )

    @staticmethod
    def _concept(text: str) -> FhirCodeableConcept:
        return FhirCodeableConcept(text=text)

    @staticmethod
    def _narrative(inner_xhtml: str) -> FhirNarrative:
        return FhirNarrative(div=f'<div xmlns="http://www.w3.org/1999/xhtml">{inner_xhtml}</div>')

    @staticmethod
    def _stable_id(tenant_id: str, patient_id: str, kind: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant_id}/{patient_id}/{kind}"))

    @staticmethod
    def _urn(resource_type: str, resource_id: str) -> str:
        value = uuid.uuid5(uuid.NAMESPACE_URL, f"{resource_type}/{resource_id}")
        return f"urn:uuid:{value}"

    @staticmethod
    def _entry(full_url: str, resource, url: str) -> BundleEntry:
        return BundleEntry(
            fullUrl=full_url,
            resource=resource,
            request=BundleRequest(method="PUT", url=url),
        )

    @staticmethod
    def _build_nli_detector(settings: Settings) -> ContradictionDetector | None:
        if settings.medical_nli_model_path is None:
            return None
        return OnnxNliContradictionDetector(
            settings.medical_nli_model_path,
            settings.ort_execution_provider,
            settings.medical_nli_contradiction_threshold,
        )
