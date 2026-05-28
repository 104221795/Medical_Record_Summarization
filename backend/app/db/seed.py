from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (
    ClaimCitation,
    ClaimSupportStatus,
    ClinicalDocument,
    DocumentChunk,
    Encounter,
    ModelRun,
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


@dataclass(frozen=True)
class SeedResult:
    patient_id: uuid.UUID
    encounter_id: uuid.UUID
    summary_id: uuid.UUID
    created: bool


def seed_mock_data(session: Session) -> SeedResult:
    """Seed de-identified evidence and a cited draft summary for local validation."""

    repository = ClinicalRepository(session)
    existing_patient = repository.find_patient_by_external_id("DEMO-PATIENT-001")
    if existing_patient:
        existing_encounter = session.scalar(
            select(Encounter).where(Encounter.patient_id == existing_patient.patient_id)
        )
        existing_summary = session.scalar(
            select(Summary).where(Summary.patient_id == existing_patient.patient_id)
        )
        if existing_encounter and existing_summary:
            return SeedResult(
                existing_patient.patient_id,
                existing_encounter.encounter_id,
                existing_summary.summary_id,
                False,
            )
        raise RuntimeError(
            "The demo patient exists without its complete seed fixture; "
            "use a clean local database or complete the fixture explicitly."
        )

    now = datetime.now(UTC)
    role = session.get(Role, "doctor")
    if role is None:
        role = Role(
            role_code="doctor",
            role_name="Doctor",
            description="Reviews draft summaries and approves or rejects clinical output.",
        )
        session.add(role)

    doctor = session.scalar(select(User).where(User.email == "doctor.demo@example.invalid"))
    if doctor is None:
        doctor = User(
            external_user_id="DEMO-DOCTOR-001",
            full_name="De-identified Demo Doctor",
            email="doctor.demo@example.invalid",
            department="General Medicine",
            role=role,
        )
        session.add(doctor)

    patient = Patient(
        external_patient_id="DEMO-PATIENT-001",
        patient_hash="sha256:deidentified-demo-patient-001",
        source_system="sandbox",
        fhir_patient_id="patient-demo-001",
        is_deidentified=True,
    )
    session.add(patient)
    session.flush()

    encounter = Encounter(
        patient_id=patient.patient_id,
        external_encounter_id="DEMO-ENC-001",
        fhir_encounter_id="encounter-demo-001",
        encounter_type="outpatient",
        attending_doctor=doctor,
        start_time=now,
        status="finished",
        reason_for_visit="De-identified demonstration record",
        source_system="sandbox",
    )
    session.add(encounter)
    session.flush()

    note_text = "Patient reports fatigue. Blood pressure recorded as 128/78 mmHg."
    follow_up_text = "Follow-up note documents improved fatigue and continued clinical review."
    note = ClinicalDocument(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        external_document_id="DEMO-DOC-001",
        fhir_document_reference_id="document-demo-001",
        document_type="progress_note",
        document_title="De-identified progress note",
        document_datetime=now,
        author=doctor,
        raw_text=note_text,
        source_system="sandbox",
        confidentiality_level="deidentified",
    )
    follow_up = ClinicalDocument(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        external_document_id="DEMO-DOC-002",
        fhir_document_reference_id="document-demo-002",
        document_type="progress_note",
        document_title="De-identified follow-up note",
        document_datetime=now,
        author=doctor,
        raw_text=follow_up_text,
        source_system="sandbox",
        confidentiality_level="deidentified",
    )
    session.add_all([note, follow_up])
    session.flush()

    note_chunk = DocumentChunk(
        document_id=note.document_id,
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        chunk_index=0,
        section_name="Clinical status",
        chunk_text=note_text,
        char_start=0,
        char_end=len(note_text),
        embedding_id="seed-note-chunk-001",
        vector_store="mock",
    )
    follow_up_chunk = DocumentChunk(
        document_id=follow_up.document_id,
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        chunk_index=0,
        section_name="Follow-up",
        chunk_text=follow_up_text,
        char_start=0,
        char_end=len(follow_up_text),
        embedding_id="seed-note-chunk-002",
        vector_store="mock",
    )
    session.add_all([note_chunk, follow_up_chunk])

    model_run = ModelRun(
        model_name="seed-fixture",
        model_version="1",
        provider="none",
        prompt_version="not-generated",
        summary_type="patient_snapshot",
        status="seeded",
        run_metadata={"purpose": "deidentified_local_fixture", "ai_generated": False},
    )
    session.add(model_run)
    session.flush()

    summary_text = "Patient reports fatigue. Blood pressure was recorded as 128/78 mmHg."
    summary = Summary(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        model_run_id=model_run.model_run_id,
        summary_type="patient_snapshot",
        summary_text=summary_text,
        status=SummaryStatus.DRAFT,
        citation_coverage=1,
        generated_by=doctor.user_id,
        generated_at=now,
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

    claims = [
        SummaryClaim(
            summary_id=summary.summary_id,
            section_id=section.section_id,
            claim_order=1,
            claim_text="Patient reports fatigue.",
            claim_type="general",
            support_status=ClaimSupportStatus.SUPPORTED,
            confidence_score=1,
            clinical_risk_level="low",
        ),
        SummaryClaim(
            summary_id=summary.summary_id,
            section_id=section.section_id,
            claim_order=2,
            claim_text="Blood pressure was recorded as 128/78 mmHg.",
            claim_type="vital_sign",
            support_status=ClaimSupportStatus.SUPPORTED,
            confidence_score=1,
            clinical_risk_level="medium",
        ),
    ]
    session.add_all(claims)
    session.flush()
    session.add_all(
        [
            ClaimCitation(
                claim_id=claim.claim_id,
                source_type="document_chunk",
                source_document_id=note.document_id,
                source_chunk_id=note_chunk.chunk_id,
                source_text_span=note_text,
                source_char_start=0,
                source_char_end=len(note_text),
                citation_confidence=1,
            )
            for claim in claims
        ]
    )
    repository.record_audit_event(
        action="seed_mock_data",
        user_id=doctor.user_id,
        patient_id=patient.patient_id,
        resource_type="summary",
        resource_id=summary.summary_id,
        metadata={"deidentified": True, "summary_status": SummaryStatus.DRAFT.value},
    )
    return SeedResult(patient.patient_id, encounter.encounter_id, summary.summary_id, True)


def main() -> None:
    engine = build_engine_from_settings(Settings())
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        result = seed_mock_data(session)
    state = "created" if result.created else "already present"
    print(f"Mock persistence seed {state}: patient={result.patient_id}, summary={result.summary_id}")


if __name__ == "__main__":
    main()
