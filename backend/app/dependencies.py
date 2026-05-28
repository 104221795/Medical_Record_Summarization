import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .repositories import (
    AuditRepository,
    CitationRepository,
    DocumentRepository,
    EncounterRepository,
    IngestionRepository,
    MetricsRepository,
    PatientRepository,
    SummaryRepository,
)
from .services.audit_service import AuditService
from .services.citation_service import CitationService
from .services.clinical_pipeline import ClinicalSummaryPipelineService
from .services.deterministic_summary_service import DeterministicSummaryService
from .services.document_service import DocumentService
from .services.encounter_service import EncounterService
from .services.fhir_mapper import FhirMapperService
from .services.ingestion_service import IngestionService
from .services.metrics_service import MetricsService
from .services.multimodal import MultimodalService
from .services.patient_service import PatientService
from .services.rag import RagService
from .services.review_service import ReviewService
from .services.safety_service import SafetyService


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]{2,128}$")


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    user_id: str
    role_code: str


def get_request_context(
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_user_id: Annotated[str, Header(alias="X-User-ID")],
    x_role_code: Annotated[str, Header(alias="X-Role-Code")] = "doctor",
) -> RequestContext:
    for label, value in (
        ("X-Tenant-ID", x_tenant_id),
        ("X-User-ID", x_user_id),
        ("X-Role-Code", x_role_code),
    ):
        if not IDENTIFIER_RE.fullmatch(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} contains invalid characters.",
            )
    return RequestContext(tenant_id=x_tenant_id, user_id=x_user_id, role_code=x_role_code)


def get_rag_service(request: Request) -> RagService:
    return request.app.state.rag_service


def get_multimodal_service(request: Request) -> MultimodalService:
    return request.app.state.multimodal_service


def get_fhir_mapper_service(request: Request) -> FhirMapperService:
    return request.app.state.fhir_mapper_service


def get_clinical_pipeline_service(request: Request) -> ClinicalSummaryPipelineService:
    return request.app.state.clinical_pipeline_service


def get_db_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.db_session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_patient_service(session: Annotated[Session, Depends(get_db_session)]) -> PatientService:
    return PatientService(PatientRepository(session))


def get_encounter_service(session: Annotated[Session, Depends(get_db_session)]) -> EncounterService:
    return EncounterService(EncounterRepository(session), PatientRepository(session))


def get_document_service(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> DocumentService:
    return DocumentService(DocumentRepository(session), PatientRepository(session), request.app.state.settings)


def get_audit_service(session: Annotated[Session, Depends(get_db_session)]) -> AuditService:
    return AuditService(AuditRepository(session))


def get_ingestion_service(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> IngestionService:
    patients = PatientRepository(session)
    documents = DocumentRepository(session)
    audit = AuditService(AuditRepository(session))
    document_service = DocumentService(documents, patients, request.app.state.settings)
    return IngestionService(
        session,
        patients,
        EncounterRepository(session),
        documents,
        IngestionRepository(session),
        document_service,
        audit,
    )


def get_summary_service(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> DeterministicSummaryService:
    return DeterministicSummaryService(
        SummaryRepository(session),
        SafetyService(),
        AuditService(AuditRepository(session)),
        request.app.state.settings,
        getattr(request.app.state, "gemini_json_client", None),
    )


def get_review_service(session: Annotated[Session, Depends(get_db_session)]) -> ReviewService:
    return ReviewService(
        SummaryRepository(session),
        AuditService(AuditRepository(session)),
    )


def get_metrics_service(session: Annotated[Session, Depends(get_db_session)]) -> MetricsService:
    return MetricsService(MetricsRepository(session))


def get_citation_service(session: Annotated[Session, Depends(get_db_session)]) -> CitationService:
    return CitationService(
        SummaryRepository(session),
        CitationRepository(session),
        AuditService(AuditRepository(session)),
    )
