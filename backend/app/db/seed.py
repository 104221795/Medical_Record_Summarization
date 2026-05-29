from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ROOT_DIR, Settings
from ..models import (
    ClaimCitation,
    ClaimSupportStatus,
    ClinicalDocument,
    Condition,
    DiagnosticReport,
    DocumentChunk,
    Encounter,
    Medication,
    ModelRun,
    Observation,
    Patient,
    Role,
    Summary,
    SummaryClaim,
    SummarySection,
    SummaryStatus,
    User,
)
from ..repositories import ClinicalRepository
from .session import build_engine_from_settings, create_session_factory, session_scope


SEED_CASES_PATH = ROOT_DIR / "data" / "demo" / "seed_clinical_cases.json"


@dataclass(frozen=True)
class SeedResult:
    patient_id: uuid.UUID
    encounter_id: uuid.UUID
    summary_id: uuid.UUID
    created: bool


def seed_mock_data(session: Session) -> SeedResult:
    """Seed richer de-identified clinical cases for local validation.

    The fixture intentionally uses mock/de-identified MIMIC-demo-inspired
    records. It does not create real identifiable patients.
    """

    repository = ClinicalRepository(session)
    users = _ensure_demo_users(session)
    cases = _load_seed_cases()
    first_patient_id: uuid.UUID | None = None
    first_encounter_id: uuid.UUID | None = None
    first_summary_id: uuid.UUID | None = None
    created_any = False

    for case_index, case in enumerate(cases):
        existing_patient = repository.find_patient_by_external_id(case["external_patient_id"])
        if existing_patient:
            _backfill_patient_fields(existing_patient, case)
            encounter = _first_or_create_encounter(session, existing_patient, case, users["doctor"])
            summary = _first_or_create_summary(
                session,
                existing_patient,
                encounter,
                case,
                users["doctor"],
                create_documents_if_missing=False,
            )
            created = False
        else:
            existing_patient, encounter, summary = _create_case(
                session,
                case,
                case_index=case_index,
                doctor=users["doctor"],
            )
            created = True
            created_any = True

        if first_patient_id is None:
            first_patient_id = existing_patient.patient_id
            first_encounter_id = encounter.encounter_id
            first_summary_id = summary.summary_id

    if first_patient_id is None or first_encounter_id is None or first_summary_id is None:
        raise RuntimeError("No demo seed cases were available.")

    repository.record_audit_event(
        action="seed_mock_data",
        user_id=users["doctor"].user_id,
        patient_id=first_patient_id,
        resource_type="demo_fixture",
        resource_id=first_summary_id,
        metadata={
            "deidentified": True,
            "case_count": len(cases),
            "created": created_any,
            "source": "data/demo/seed_clinical_cases.json",
        },
    )
    return SeedResult(first_patient_id, first_encounter_id, first_summary_id, created_any)


def _load_seed_cases() -> list[dict]:
    return json.loads(SEED_CASES_PATH.read_text(encoding="utf-8"))


def _ensure_demo_users(session: Session) -> dict[str, User]:
    roles = {
        "doctor": "Doctor",
        "clinical_admin": "Clinical Admin",
        "auditor": "Auditor",
        "ai_safety_reviewer": "AI Safety Reviewer",
        "it_admin": "IT Admin",
        "nurse": "Nurse",
    }
    for role_code, role_name in roles.items():
        if session.get(Role, role_code) is None:
            session.add(
                Role(
                    role_code=role_code,
                    role_name=role_name,
                    description=f"Demo {role_name.lower()} role.",
                )
            )
    session.flush()

    user_specs = {
        "doctor": (
            "doctor-demo",
            "De-identified Demo Doctor",
            "doctor.demo@example.invalid",
            "General Medicine",
        ),
        "clinical_admin": (
            "clinical-admin-demo",
            "De-identified Clinical Admin",
            "clinical.admin@example.invalid",
            "Quality",
        ),
        "auditor": (
            "auditor-demo",
            "De-identified Auditor",
            "auditor@example.invalid",
            "Compliance",
        ),
    }
    users: dict[str, User] = {}
    for role_code, (external_id, name, email, department) in user_specs.items():
        user = session.scalar(select(User).where(User.external_user_id == external_id))
        if user is None:
            user = User(
                external_user_id=external_id,
                full_name=name,
                email=email,
                department=department,
                role_code=role_code,
                status="active",
            )
            session.add(user)
            session.flush()
        users[role_code] = user
    return users


def _create_case(
    session: Session,
    case: dict,
    *,
    case_index: int,
    doctor: User,
) -> tuple[Patient, Encounter, Summary]:
    patient = Patient(
        external_patient_id=case["external_patient_id"],
        patient_hash=case["patient_hash"],
        fhir_patient_id=case["fhir_patient_id"],
        gender=case.get("gender"),
        date_of_birth=_parse_date(case.get("date_of_birth")),
        source_system="mimic_iii_demo_deidentified",
        is_deidentified=True,
    )
    session.add(patient)
    session.flush()

    encounter = _create_encounter(session, patient, case, doctor)
    documents = [_create_document(session, patient, encounter, document, doctor) for document in case["documents"]]
    _create_structured_records(session, patient, encounter, case)
    summary = _create_seed_summary(session, patient, encounter, case, documents, doctor, case_index)
    return patient, encounter, summary


def _backfill_patient_fields(patient: Patient, case: dict) -> None:
    patient.gender = patient.gender or case.get("gender")
    patient.date_of_birth = patient.date_of_birth or _parse_date(case.get("date_of_birth"))
    patient.fhir_patient_id = patient.fhir_patient_id or case.get("fhir_patient_id")
    patient.source_system = patient.source_system or "mimic_iii_demo_deidentified"
    patient.is_deidentified = True


def _first_or_create_encounter(
    session: Session,
    patient: Patient,
    case: dict,
    doctor: User,
) -> Encounter:
    encounter = session.scalar(
        select(Encounter).where(Encounter.external_encounter_id == case["encounter"]["external_encounter_id"])
    )
    if encounter is not None:
        return encounter
    return _create_encounter(session, patient, case, doctor)


def _first_or_create_summary(
    session: Session,
    patient: Patient,
    encounter: Encounter,
    case: dict,
    doctor: User,
    *,
    create_documents_if_missing: bool,
) -> Summary:
    summary = session.scalar(select(Summary).where(Summary.patient_id == patient.patient_id))
    if summary is not None:
        return summary
    documents = session.scalars(
        select(ClinicalDocument).where(ClinicalDocument.patient_id == patient.patient_id)
    ).all()
    if not documents and create_documents_if_missing:
        documents = [
            _create_document(session, patient, encounter, document, doctor)
            for document in case["documents"]
        ]
    if not documents:
        documents = [
            _create_document(session, patient, encounter, document, doctor)
            for document in case["documents"]
        ]
    return _create_seed_summary(session, patient, encounter, case, list(documents), doctor, 0)


def _create_encounter(session: Session, patient: Patient, case: dict, doctor: User) -> Encounter:
    data = case["encounter"]
    encounter = Encounter(
        patient_id=patient.patient_id,
        external_encounter_id=data["external_encounter_id"],
        fhir_encounter_id=data["fhir_encounter_id"],
        encounter_type=data.get("encounter_type"),
        department=data.get("department"),
        attending_doctor=doctor,
        start_time=_parse_datetime(data.get("start_time")),
        end_time=_parse_datetime(data.get("end_time")),
        status=data.get("status"),
        reason_for_visit=data.get("reason_for_visit"),
        source_system="mimic_iii_demo_deidentified",
    )
    session.add(encounter)
    session.flush()
    return encounter


def _create_structured_records(
    session: Session,
    patient: Patient,
    encounter: Encounter,
    case: dict,
) -> None:
    now = encounter.start_time or datetime.now(UTC)
    for index, item in enumerate(case.get("conditions", []), start=1):
        session.add(
            Condition(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id,
                external_condition_id=f"{case['case_id']}-condition-{index}",
                fhir_condition_id=f"condition-{case['mimic_subject_id']}-{index}",
                condition_code=item.get("code"),
                coding_system="ICD-9-CM",
                condition_name=item["name"],
                clinical_status=item.get("status"),
                verification_status=item.get("verification_status"),
                recorded_date=now,
                source_system="mimic_iii_demo_deidentified",
            )
        )
    for index, item in enumerate(case.get("observations", []), start=1):
        value = item.get("value")
        numeric = _safe_decimal(value)
        session.add(
            Observation(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id,
                external_observation_id=f"{case['case_id']}-observation-{index}",
                fhir_observation_id=f"observation-{case['mimic_subject_id']}-{index}",
                observation_type=item.get("type"),
                observation_code=item.get("code"),
                coding_system="demo",
                observation_name=item["name"],
                value_text=None if numeric is not None else str(value),
                value_numeric=numeric,
                unit=item.get("unit") or None,
                interpretation=item.get("interpretation"),
                observed_at=_parse_datetime(item.get("observed_at")),
                source_system="mimic_iii_demo_deidentified",
            )
        )
    for index, item in enumerate(case.get("medications", []), start=1):
        session.add(
            Medication(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id,
                external_medication_id=f"{case['case_id']}-medication-{index}",
                fhir_medication_request_id=f"medication-{case['mimic_subject_id']}-{index}",
                medication_name=item["name"],
                dosage_text=item.get("dosage_text"),
                route=item.get("route"),
                frequency=item.get("frequency"),
                start_date=encounter.start_time.date() if encounter.start_time else None,
                status=item.get("status"),
                medication_action="documented",
                prescribed_by=None,
                source_system="mimic_iii_demo_deidentified",
            )
        )
    for index, item in enumerate(case.get("reports", []), start=1):
        session.add(
            DiagnosticReport(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id,
                external_report_id=f"{case['case_id']}-report-{index}",
                fhir_diagnostic_report_id=f"report-{case['mimic_subject_id']}-{index}",
                report_type=item.get("type"),
                report_title=item.get("title"),
                report_text=item["text"],
                conclusion_text=item.get("conclusion"),
                report_status=item.get("status"),
                performed_at=_parse_datetime(item.get("performed_at")),
                reported_at=_parse_datetime(item.get("performed_at")),
                source_system="mimic_iii_demo_deidentified",
            )
        )
    session.flush()


def _create_document(
    session: Session,
    patient: Patient,
    encounter: Encounter,
    item: dict,
    doctor: User,
) -> ClinicalDocument:
    text = item["text"]
    document = ClinicalDocument(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        external_document_id=item["external_document_id"],
        fhir_document_reference_id=item["external_document_id"],
        document_type=item["type"],
        document_title=item["title"],
        document_datetime=_parse_datetime(item.get("datetime")),
        author=doctor,
        raw_text=text,
        raw_text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source_system="mimic_iii_demo_deidentified",
        confidentiality_level="deidentified",
    )
    session.add(document)
    session.flush()
    for chunk in _chunks_for_document(document):
        session.add(chunk)
    session.flush()
    return document


def _chunks_for_document(document: ClinicalDocument) -> list[DocumentChunk]:
    blocks = [block.strip() for block in document.raw_text.split("\n\n") if block.strip()]
    if not blocks:
        blocks = [document.raw_text]
    chunks: list[DocumentChunk] = []
    cursor = 0
    for index, block in enumerate(blocks):
        start = document.raw_text.find(block, cursor)
        if start < 0:
            start = cursor
        end = start + len(block)
        cursor = end
        section = block.splitlines()[0].strip(": ").title()[:255] if block.splitlines() else None
        chunks.append(
            DocumentChunk(
                document_id=document.document_id,
                patient_id=document.patient_id,
                encounter_id=document.encounter_id,
                chunk_index=index,
                section_name=section,
                chunk_text=block,
                token_count=len(block.split()),
                char_start=start,
                char_end=end,
                embedding_id=f"seed-{document.external_document_id}-{index}",
                vector_store="mock",
                chunk_hash=hashlib.sha256(block.encode("utf-8")).hexdigest(),
            )
        )
    return chunks


def _create_seed_summary(
    session: Session,
    patient: Patient,
    encounter: Encounter,
    case: dict,
    documents: list[ClinicalDocument],
    doctor: User,
    case_index: int,
) -> Summary:
    now = datetime.now(UTC)
    model_run = ModelRun(
        model_name="seed-fixture",
        model_version="10-case-demo",
        provider="none",
        prompt_version="not-generated",
        summary_type="patient_snapshot",
        status="seeded",
        run_metadata={
            "purpose": "deidentified_local_fixture",
            "ai_generated": False,
            "case_id": case["case_id"],
            "mimic_subject_id": case.get("mimic_subject_id"),
            "mimic_hadm_id": case.get("mimic_hadm_id"),
        },
    )
    session.add(model_run)
    session.flush()

    condition_text = ", ".join(item["name"] for item in case.get("conditions", [])[:2]) or "available source record"
    first_lab = case.get("observations", [{}])[0]
    lab_text = (
        f"{first_lab.get('name')} {first_lab.get('value')} {first_lab.get('unit', '')}".strip()
        if first_lab
        else "No lab value selected"
    )
    summary_text = (
        f"Seeded de-identified case {case_index + 1}: {case['title']}. "
        f"Documented problems include {condition_text}. Key observed value: {lab_text}. "
        "This is a seeded draft for demo navigation only."
    )
    summary = Summary(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        model_run_id=model_run.model_run_id,
        summary_type="patient_snapshot",
        summary_text=summary_text,
        summary_language="vi",
        status=SummaryStatus.DRAFT,
        citation_coverage=1,
        unsupported_claim_count=0,
        conflict_count=0,
        generated_by=doctor.user_id,
        generated_at=now,
        version_number=1,
    )
    session.add(summary)
    session.flush()

    section = SummarySection(
        summary_id=summary.summary_id,
        section_order=1,
        section_title="Patient Snapshot",
        section_text=summary_text,
        section_type="patient_snapshot",
    )
    session.add(section)
    session.flush()

    source_document = documents[0]
    source_chunk = source_document.chunks[0] if source_document.chunks else None
    claims = [
        SummaryClaim(
            summary_id=summary.summary_id,
            section_id=section.section_id,
            claim_order=1,
            claim_text=f"Seed case title: {case['title']}.",
            claim_type="general",
            support_status=ClaimSupportStatus.SUPPORTED,
            confidence_score=1,
            clinical_risk_level="low",
        ),
        SummaryClaim(
            summary_id=summary.summary_id,
            section_id=section.section_id,
            claim_order=2,
            claim_text=f"Documented problems include {condition_text}.",
            claim_type="diagnosis",
            support_status=ClaimSupportStatus.SUPPORTED,
            confidence_score=1,
            clinical_risk_level="high",
        ),
    ]
    session.add_all(claims)
    session.flush()
    for claim in claims:
        session.add(_citation_for_claim(claim, source_document, source_chunk))
    session.flush()
    return summary


def _citation_for_claim(
    claim: SummaryClaim,
    document: ClinicalDocument,
    chunk: DocumentChunk | None,
) -> ClaimCitation:
    source_text = chunk.chunk_text if chunk else document.raw_text
    source_start = chunk.char_start if chunk else 0
    source_end = chunk.char_end if chunk else len(document.raw_text)
    return ClaimCitation(
        claim_id=claim.claim_id,
        source_type="document_chunk" if chunk else "clinical_document",
        source_document_id=document.document_id,
        source_chunk_id=chunk.chunk_id if chunk else None,
        source_text_span=source_text,
        source_char_start=source_start,
        source_char_end=source_end,
        citation_confidence=1,
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _safe_decimal(value):
    if value is None:
        return None
    if "/" in str(value):
        return None
    try:
        from decimal import Decimal

        return Decimal(str(value))
    except Exception:
        return None


def main() -> None:
    engine = build_engine_from_settings(Settings())
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        result = seed_mock_data(session)
    state = "created or completed" if result.created else "already present"
    print(
        "Mock persistence seed "
        f"{state}: patient={result.patient_id}, summary={result.summary_id}"
    )


if __name__ == "__main__":
    main()
