from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from ..models import (
    ClinicalDocument,
    Condition,
    DiagnosticReport,
    Encounter,
    Medication,
    Observation,
    Patient,
)
from ..persistence_schemas import (
    FhirConceptIn,
    FhirDiagnosticReportImport,
    FhirDocumentImport,
    FhirLikeImportRequest,
    FhirReferenceIn,
    ImportResponse,
)
from ..repositories import (
    DocumentRepository,
    EncounterRepository,
    IngestionRepository,
    PatientRepository,
)
from .audit_service import AuditService
from .document_service import DocumentService
from .persistence_common import IngestionValidationError


class IngestionService:
    """Normalize a restricted FHIR-like import into persisted source records."""

    def __init__(
        self,
        session: Session,
        patients: PatientRepository,
        encounters: EncounterRepository,
        documents: DocumentRepository,
        structured: IngestionRepository,
        document_service: DocumentService,
        audit_service: AuditService,
    ):
        self.session = session
        self.patients = patients
        self.encounters = encounters
        self.documents = documents
        self.structured = structured
        self.document_service = document_service
        self.audit_service = audit_service

    def import_fhir_like(
        self,
        payload: FhirLikeImportRequest,
        *,
        tenant_id: str,
        actor_external_id: str,
    ) -> ImportResponse:
        resources = payload.resources()
        operation_id = uuid.uuid4()
        accepted = 0
        skipped = 0
        chunks_created = 0
        touched_patient_ids: set[uuid.UUID] = set()
        patient_refs: dict[str, Patient] = {}
        encounter_refs: dict[str, Encounter] = {}

        for incoming in resources.patients:
            if not incoming.is_deidentified:
                raise IngestionValidationError(
                    "Phase 2 ingestion accepts de-identified patient data only."
                )
            external_id = _identifier(incoming.identifier)
            patient = self.patients.find_source_identity(payload.source_system, external_id, incoming.id)
            if patient is None:
                patient = Patient(
                    external_patient_id=external_id,
                    fhir_patient_id=incoming.id,
                    patient_hash=incoming.patient_hash
                    or _deidentified_hash(payload.source_system, external_id),
                    gender=incoming.gender,
                    date_of_birth=incoming.birth_date,
                    source_system=payload.source_system,
                    is_deidentified=True,
                )
                self.patients.add(patient)
                self.session.flush()
                accepted += 1
            else:
                skipped += 1
            touched_patient_ids.add(patient.patient_id)
            if incoming.id:
                patient_refs[f"Patient/{incoming.id}"] = patient

        for incoming in resources.encounters:
            patient = self._resolve_patient(incoming.subject, payload.source_system, patient_refs)
            external_id = _identifier(incoming.identifier)
            encounter = self.encounters.find_source_identity(payload.source_system, external_id, incoming.id)
            if encounter is not None:
                if encounter.patient_id != patient.patient_id:
                    raise IngestionValidationError(
                        "Encounter identifier already belongs to another patient."
                    )
                skipped += 1
            else:
                encounter = Encounter(
                    patient_id=patient.patient_id,
                    external_encounter_id=external_id,
                    fhir_encounter_id=incoming.id,
                    encounter_type=_encounter_type(incoming.class_.code if incoming.class_ else None),
                    department=incoming.department,
                    start_time=incoming.period.start if incoming.period else None,
                    end_time=incoming.period.end if incoming.period else None,
                    status=incoming.status,
                    reason_for_visit=_concept_name(incoming.reason_code),
                    source_system=payload.source_system,
                )
                self.encounters.add(encounter)
                self.session.flush()
                accepted += 1
            touched_patient_ids.add(patient.patient_id)
            if incoming.id:
                encounter_refs[f"Encounter/{incoming.id}"] = encounter

        for incoming in resources.conditions:
            patient = self._resolve_patient(incoming.subject, payload.source_system, patient_refs)
            encounter = self._resolve_optional_encounter(
                incoming.encounter, payload.source_system, encounter_refs, patient.patient_id
            )
            external_id = _optional_identifier(incoming.identifier)
            if self.structured.find_condition(payload.source_system, external_id, incoming.id):
                skipped += 1
                continue
            coding = _first_coding(incoming.code)
            record = Condition(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id if encounter else None,
                external_condition_id=external_id,
                fhir_condition_id=incoming.id,
                condition_code=coding.code if coding else None,
                coding_system=coding.system if coding else None,
                condition_name=_require_concept_name(incoming.code, "Condition"),
                clinical_status=_concept_code(incoming.clinical_status),
                verification_status=_concept_code(incoming.verification_status),
                onset_date=incoming.onset_date_time.date() if incoming.onset_date_time else None,
                recorded_date=incoming.recorded_date,
                source_system=payload.source_system,
            )
            self.structured.add(record)
            accepted += 1
            touched_patient_ids.add(patient.patient_id)

        for incoming in resources.observations:
            patient = self._resolve_patient(incoming.subject, payload.source_system, patient_refs)
            encounter = self._resolve_optional_encounter(
                incoming.encounter, payload.source_system, encounter_refs, patient.patient_id
            )
            external_id = _optional_identifier(incoming.identifier)
            if self.structured.find_observation(payload.source_system, external_id, incoming.id):
                skipped += 1
                continue
            coding = _first_coding(incoming.code)
            record = Observation(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id if encounter else None,
                external_observation_id=external_id,
                fhir_observation_id=incoming.id,
                observation_type=_observation_type(incoming.category),
                observation_code=coding.code if coding else None,
                coding_system=coding.system if coding else None,
                observation_name=_require_concept_name(incoming.code, "Observation"),
                value_text=incoming.value_string,
                value_numeric=incoming.value_quantity.value if incoming.value_quantity else None,
                unit=incoming.value_quantity.unit if incoming.value_quantity else None,
                interpretation=_concept_code(incoming.interpretation[0]) if incoming.interpretation else None,
                observed_at=incoming.effective_date_time,
                source_system=payload.source_system,
            )
            self.structured.add(record)
            accepted += 1
            touched_patient_ids.add(patient.patient_id)

        for incoming in resources.medications:
            patient = self._resolve_patient(incoming.subject, payload.source_system, patient_refs)
            encounter = self._resolve_optional_encounter(
                incoming.encounter, payload.source_system, encounter_refs, patient.patient_id
            )
            external_id = _optional_identifier(incoming.identifier)
            if self.structured.find_medication(payload.source_system, external_id, incoming.id):
                skipped += 1
                continue
            coding = _first_coding(incoming.medication)
            dosage = incoming.dosage_instruction[0] if incoming.dosage_instruction else None
            record = Medication(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id if encounter else None,
                external_medication_id=external_id,
                fhir_medication_request_id=incoming.id,
                medication_name=_require_concept_name(incoming.medication, "Medication"),
                medication_code=coding.code if coding else None,
                coding_system=coding.system if coding else None,
                dosage_text=dosage.text if dosage else None,
                route=_concept_name(dosage.route) if dosage and dosage.route else None,
                start_date=incoming.authored_on,
                status=incoming.status,
                medication_action="unknown",
                source_system=payload.source_system,
            )
            self.structured.add(record)
            accepted += 1
            touched_patient_ids.add(patient.patient_id)

        for incoming in resources.diagnostic_reports:
            patient = self._resolve_patient(incoming.subject, payload.source_system, patient_refs)
            encounter = self._resolve_optional_encounter(
                incoming.encounter, payload.source_system, encounter_refs, patient.patient_id
            )
            external_id = _optional_identifier(incoming.identifier)
            if self.structured.find_report(payload.source_system, external_id, incoming.id):
                skipped += 1
                continue
            report = self._report_record(incoming, patient, encounter, payload.source_system)
            self.structured.add(report)
            accepted += 1
            touched_patient_ids.add(patient.patient_id)

        for incoming in resources.documents:
            patient = self._resolve_patient(incoming.subject, payload.source_system, patient_refs)
            encounter = self._resolve_optional_encounter(
                incoming.encounter_reference(),
                payload.source_system,
                encounter_refs,
                patient.patient_id,
            )
            raw_hash = hashlib.sha256(incoming.raw_text.encode("utf-8")).hexdigest()
            external_id = _optional_identifier(incoming.identifier)
            fhir_document_id = incoming.id if incoming.resource_type == "DocumentReference" else None
            fhir_composition_id = incoming.id if incoming.resource_type == "Composition" else None
            if self.documents.find_duplicate(
                source_system=payload.source_system,
                patient_id=patient.patient_id,
                external_document_id=external_id,
                fhir_document_reference_id=fhir_document_id,
                fhir_composition_id=fhir_composition_id,
                raw_text_hash=raw_hash,
            ):
                skipped += 1
                continue
            document = ClinicalDocument(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id if encounter else None,
                external_document_id=external_id,
                fhir_document_reference_id=fhir_document_id,
                fhir_composition_id=fhir_composition_id,
                document_type=_document_type(incoming),
                document_title=incoming.title or incoming.description,
                document_datetime=incoming.date,
                raw_text=incoming.raw_text,
                raw_text_hash=raw_hash,
                source_file_uri=incoming.source_file_uri,
                source_system=payload.source_system,
                confidentiality_level=incoming.confidentiality_level or "deidentified",
            )
            self.documents.add(document)
            self.session.flush()
            chunks_created += self.document_service.create_chunks(document)
            accepted += 1
            touched_patient_ids.add(patient.patient_id)

        self.session.flush()
        patient_id = next(iter(touched_patient_ids)) if len(touched_patient_ids) == 1 else None
        self.audit_service.record(
            action="import_data",
            patient_id=patient_id,
            resource_type="ingestion",
            resource_id=operation_id,
            metadata={
                "source_system": payload.source_system,
                "ingestion_type": payload.ingestion_type,
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
                "total_records": resources.total_records(),
                "accepted_records": accepted,
                "skipped_duplicates": skipped,
                "chunks_created": chunks_created,
                "deidentified_only": True,
            },
        )
        return ImportResponse(
            ingestion_batch_id=operation_id,
            total_records=resources.total_records(),
            accepted_records=accepted,
            skipped_duplicates=skipped,
            chunks_created=chunks_created,
        )

    def _resolve_patient(
        self,
        reference: FhirReferenceIn,
        source_system: str,
        local: dict[str, Patient],
    ) -> Patient:
        if not reference.reference.startswith("Patient/"):
            raise IngestionValidationError("Clinical resource subject must reference a Patient.")
        if reference.reference in local:
            return local[reference.reference]
        identifier = reference.reference.split("/", 1)[1]
        patient = self.patients.find_source_identity(source_system, None, identifier)
        if patient is None:
            try:
                patient = self.patients.get(uuid.UUID(identifier))
            except ValueError:
                patient = None
        if patient is None:
            raise IngestionValidationError(
                f"Patient reference '{reference.reference}' could not be resolved."
            )
        return patient

    def _resolve_optional_encounter(
        self,
        reference: FhirReferenceIn | None,
        source_system: str,
        local: dict[str, Encounter],
        patient_id: uuid.UUID,
    ) -> Encounter | None:
        if reference is None:
            return None
        if not reference.reference.startswith("Encounter/"):
            raise IngestionValidationError("Encounter reference is malformed.")
        if reference.reference in local:
            encounter = local[reference.reference]
        else:
            identifier = reference.reference.split("/", 1)[1]
            encounter = self.encounters.find_source_identity(source_system, None, identifier)
            if encounter is None:
                try:
                    encounter = self.encounters.get(uuid.UUID(identifier))
                except ValueError:
                    encounter = None
        if encounter is None:
            raise IngestionValidationError(
                f"Encounter reference '{reference.reference}' could not be resolved."
            )
        if encounter.patient_id != patient_id:
            raise IngestionValidationError("Encounter reference belongs to a different patient.")
        return encounter

    @staticmethod
    def _report_record(
        incoming: FhirDiagnosticReportImport,
        patient: Patient,
        encounter: Encounter | None,
        source_system: str,
    ) -> DiagnosticReport:
        category = incoming.category[0] if incoming.category else None
        return DiagnosticReport(
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id if encounter else None,
            external_report_id=_optional_identifier(incoming.identifier),
            fhir_diagnostic_report_id=incoming.id,
            report_type=_concept_name(category),
            report_title=_concept_name(incoming.code),
            report_text=incoming.report_text or incoming.conclusion or "",
            conclusion_text=incoming.conclusion,
            report_status=incoming.status,
            performed_at=incoming.effective_date_time,
            reported_at=incoming.issued,
            source_system=source_system,
        )


def _identifier(values: list) -> str:
    if not values:
        raise IngestionValidationError("FHIR-like resource identifier is required.")
    return values[0].value


def _optional_identifier(values: list) -> str | None:
    return values[0].value if values else None


def _deidentified_hash(source_system: str, external_id: str) -> str:
    value = hashlib.sha256(f"{source_system}:{external_id}".encode("utf-8")).hexdigest()
    return f"sha256:{value}"


def _first_coding(concept: FhirConceptIn | None):
    return concept.coding[0] if concept and concept.coding else None


def _concept_name(concept: FhirConceptIn | None) -> str | None:
    if concept is None:
        return None
    if concept.text:
        return concept.text
    coding = _first_coding(concept)
    return coding.display if coding else None


def _require_concept_name(concept: FhirConceptIn, label: str) -> str:
    name = _concept_name(concept)
    if not name:
        raise IngestionValidationError(f"{label} requires display text.")
    return name


def _concept_code(concept: FhirConceptIn | None) -> str | None:
    coding = _first_coding(concept)
    return coding.code if coding else _concept_name(concept)


def _encounter_type(code: str | None) -> str | None:
    return {
        "IMP": "inpatient",
        "AMB": "outpatient",
        "EMER": "emergency",
        "VR": "telemedicine",
    }.get(code, "other" if code else None)


def _observation_type(categories: list[FhirConceptIn]) -> str | None:
    category = _concept_code(categories[0]) if categories else None
    return {
        "laboratory": "lab",
        "vital-signs": "vital",
        "survey": "score",
        "exam": "measurement",
    }.get(category, "other" if category else None)


def _document_type(incoming: FhirDocumentImport) -> str:
    supplied = incoming.document_type or (incoming.type.text if incoming.type else None)
    if not supplied:
        raise IngestionValidationError("Clinical document type is required.")
    return supplied.strip().casefold().replace(" ", "_")
