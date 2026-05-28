from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.seed import seed_mock_data
from backend.app.db.session import create_db_engine, create_session_factory
from backend.app.models import (
    AuditLog,
    ClaimCitation,
    ClaimSupportStatus,
    ClinicalDocument,
    DocumentChunk,
    Encounter,
    Patient,
    Role,
    Summary,
    SummaryClaim,
    SummarySection,
    SummaryStatus,
    User,
)
from backend.app.repositories import ClinicalRepository


ROOT_DIR = Path(__file__).resolve().parents[2]
CORE_TABLES = {
    "users",
    "roles",
    "patients",
    "encounters",
    "clinical_documents",
    "document_chunks",
    "summaries",
    "summary_sections",
    "summary_claims",
    "claim_citations",
    "summary_reviews",
    "audit_logs",
    "model_runs",
}


@pytest.fixture
def session(tmp_path: Path) -> Session:
    engine = create_db_engine(f"sqlite+pysqlite:///{tmp_path / 'persistence.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db_session:
        yield db_session
    engine.dispose()


def _create_clinical_context(session: Session) -> tuple[User, Patient, Encounter]:
    role = Role(role_code="doctor", role_name="Doctor")
    doctor = User(
        full_name="Doctor Demo",
        email="doctor-test@example.invalid",
        role=role,
    )
    patient = Patient(
        external_patient_id="PAT-001",
        patient_hash="hash-pat-001",
        fhir_patient_id="fhir-pat-001",
        source_system="sandbox",
        is_deidentified=True,
    )
    session.add_all([role, doctor, patient])
    session.flush()
    encounter = Encounter(
        patient_id=patient.patient_id,
        external_encounter_id="ENC-001",
        fhir_encounter_id="fhir-enc-001",
        attending_doctor_id=doctor.user_id,
        source_system="sandbox",
        status="finished",
    )
    session.add(encounter)
    session.commit()
    return doctor, patient, encounter


def test_alembic_upgrade_creates_core_persistence_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("RAG_DATABASE_URL", database_url)
    config = Config(str(ROOT_DIR / "alembic.ini"))

    command.upgrade(config, "head")
    command.check(config)

    engine = create_db_engine(database_url)
    try:
        assert CORE_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_session_creates_patient_encounter_document_and_chunks(session: Session) -> None:
    doctor, patient, encounter = _create_clinical_context(session)
    text = "Patient reports fatigue. Blood pressure recorded as 128/78 mmHg."
    document = ClinicalDocument(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        external_document_id="DOC-001",
        fhir_document_reference_id="fhir-doc-001",
        document_type="progress_note",
        document_datetime=datetime.now(UTC),
        author_id=doctor.user_id,
        raw_text=text,
        source_system="sandbox",
    )
    session.add(document)
    session.flush()
    session.add(
        DocumentChunk(
            document_id=document.document_id,
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id,
            chunk_index=0,
            section_name="Status",
            chunk_text=text,
            char_start=0,
            char_end=len(text),
            embedding_id="qdrant-point-001",
            vector_store="qdrant",
        )
    )
    session.commit()

    stored = session.scalar(
        select(ClinicalDocument).where(ClinicalDocument.document_id == document.document_id)
    )
    assert stored is not None
    assert stored.patient_id == patient.patient_id
    assert stored.chunks[0].char_start == 0
    assert stored.chunks[0].embedding_id == "qdrant-point-001"


def test_creates_draft_summary_claim_citation_and_audit_log(session: Session) -> None:
    doctor, patient, encounter = _create_clinical_context(session)
    document = ClinicalDocument(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        document_type="progress_note",
        raw_text="Patient reports fatigue.",
        source_system="sandbox",
    )
    session.add(document)
    session.flush()
    chunk = DocumentChunk(
        document_id=document.document_id,
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        chunk_index=0,
        chunk_text="Patient reports fatigue.",
        char_start=0,
        char_end=24,
    )
    summary = Summary(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        summary_type="patient_snapshot",
        summary_text="Patient reports fatigue.",
        generated_by=doctor.user_id,
        citation_coverage=Decimal("1.0000"),
    )
    session.add_all([chunk, summary])
    session.flush()
    section = SummarySection(
        summary_id=summary.summary_id,
        section_order=1,
        section_title="Patient Snapshot",
        section_text=summary.summary_text,
    )
    session.add(section)
    session.flush()
    claim = SummaryClaim(
        summary_id=summary.summary_id,
        section_id=section.section_id,
        claim_order=1,
        claim_text="Patient reports fatigue.",
        support_status=ClaimSupportStatus.SUPPORTED,
    )
    session.add(claim)
    session.flush()
    citation = ClaimCitation(
        claim_id=claim.claim_id,
        source_type="document_chunk",
        source_document_id=document.document_id,
        source_chunk_id=chunk.chunk_id,
        source_text_span=chunk.chunk_text,
    )
    session.add(citation)
    event = ClinicalRepository(session).record_audit_event(
        action="generate_summary",
        user_id=doctor.user_id,
        patient_id=patient.patient_id,
        resource_type="summary",
        resource_id=summary.summary_id,
        metadata={"draft": True},
    )
    session.commit()

    assert summary.status == SummaryStatus.DRAFT
    assert claim.support_status == ClaimSupportStatus.SUPPORTED
    assert claim.citations[0].source_chunk_id == chunk.chunk_id
    assert session.get(AuditLog, event.audit_id).metadata_json == {"draft": True}


def test_seed_data_is_deidentified_cited_draft_and_idempotent(session: Session) -> None:
    first = seed_mock_data(session)
    session.commit()
    second = seed_mock_data(session)
    session.commit()

    summary = session.get(Summary, first.summary_id)
    assert first.created is True
    assert second.created is False
    assert summary is not None and summary.status == SummaryStatus.DRAFT
    assert len(summary.claims) == 2
    assert all(claim.citations for claim in summary.claims)
    assert session.scalar(select(Patient).where(Patient.patient_id == summary.patient_id)).is_deidentified


def test_summary_status_enum_rejects_unknown_values(session: Session) -> None:
    _, patient, encounter = _create_clinical_context(session)
    session.add(
        Summary(
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id,
            summary_type="patient_snapshot",
            summary_text="Draft text.",
            status="published",
        )
    )

    with pytest.raises(StatementError):
        session.commit()
    session.rollback()


def test_claim_support_status_enum_rejects_unknown_values(session: Session) -> None:
    _, patient, encounter = _create_clinical_context(session)
    summary = Summary(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        summary_type="patient_snapshot",
        summary_text="Draft text.",
    )
    session.add(summary)
    session.commit()
    session.add(
        SummaryClaim(
            summary_id=summary.summary_id,
            claim_order=1,
            claim_text="Unvalidated claim.",
            support_status="plausible",
        )
    )

    with pytest.raises(StatementError):
        session.commit()
    session.rollback()


def test_citation_requires_a_persisted_source_reference(session: Session) -> None:
    _, patient, encounter = _create_clinical_context(session)
    summary = Summary(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        summary_type="patient_snapshot",
        summary_text="Draft text.",
    )
    session.add(summary)
    session.flush()
    claim = SummaryClaim(
        summary_id=summary.summary_id,
        claim_order=1,
        claim_text="Unlinked claim.",
        support_status=ClaimSupportStatus.UNSUPPORTED,
    )
    session.add(claim)
    session.flush()
    session.add(ClaimCitation(claim_id=claim.claim_id, source_type="document_chunk"))

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
