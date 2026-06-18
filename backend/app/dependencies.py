import re
from typing import Annotated, Callable
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .repositories import (
    AuditRepository,
    CitationRepository,
    DocumentRepository,
    EncounterRepository,
    EvaluationRepository,
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
from .services.evaluation_service import EvaluationService
from .services.fhir_mapper import FhirMapperService
from .services.ingestion_service import IngestionService
from .services.metrics_service import MetricsService
from .services.multimodal import MultimodalService
from .services.patient_service import PatientService
from .services.rag import RagService
from .services.review_service import ReviewService
from .services.safety_service import SafetyService
from .services.auth_tokens import bearer_token, decode_session_token
from .models import User


TENANT_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
ROLE_RE = re.compile(r"^[A-Za-z0-9._-]{2,128}$")
USER_HEADER_RE = re.compile(r"^[A-Za-z0-9._@+-]{2,255}$")


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    user_id: str
    role_code: str


def get_request_context(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    x_role_code: Annotated[str | None, Header(alias="X-Role-Code")] = None,
) -> RequestContext:
    settings = request.app.state.settings
    if settings.environment == "test" or (
        settings.environment == "development" and settings.allow_demo_header_auth
    ):
        return _validated_header_context(
            x_tenant_id or "sandbox",
            x_user_id or "doctor-demo",
            x_role_code or "doctor",
        )

    claims = decode_session_token(bearer_token(authorization), settings)
    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token is missing a subject.",
        )
    factory = request.app.state.db_session_factory
    session = factory()
    try:
        user = session.scalar(
            select(User).where(
                (User.email == subject) | (User.external_user_id == subject)
            )
        )
    finally:
        session.close()
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session user is no longer active.",
        )
    return RequestContext(
        tenant_id=str(claims.get("tenant_id") or "sandbox"),
        user_id=str(user.external_user_id or user.email),
        role_code=user.role_code,
    )


def _validated_header_context(
    x_tenant_id: str,
    x_user_id: str,
    x_role_code: str,
) -> RequestContext:
    validators = (
        ("X-Tenant-ID", x_tenant_id, TENANT_RE),
        ("X-User-ID", x_user_id, USER_HEADER_RE),
        ("X-Role-Code", x_role_code, ROLE_RE),
    )
    for label, value, pattern in validators:
        if not pattern.fullmatch(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} contains invalid characters.",
            )
    return RequestContext(tenant_id=x_tenant_id, user_id=x_user_id, role_code=x_role_code)


def require_roles(*allowed_roles: str) -> Callable[[RequestContext], RequestContext]:
    allowed = set(allowed_roles)

    def dependency(
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> RequestContext:
        if context.role_code not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This role is not allowed to access this clinical safety endpoint.",
            )
        return context

    return dependency


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
        getattr(request.app.state, "summary_model_providers", None),
        getattr(request.app.state, "rag_service", None),
    )


def get_review_service(session: Annotated[Session, Depends(get_db_session)]) -> ReviewService:
    return ReviewService(
        SummaryRepository(session),
        AuditService(AuditRepository(session)),
    )


def get_metrics_service(session: Annotated[Session, Depends(get_db_session)]) -> MetricsService:
    return MetricsService(MetricsRepository(session))


def get_evaluation_service(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> EvaluationService:
    return EvaluationService(
        EvaluationRepository(session),
        session,
        request.app.state.settings,
        AuditService(AuditRepository(session)),
    )


def get_citation_service(session: Annotated[Session, Depends(get_db_session)]) -> CitationService:
    return CitationService(
        SummaryRepository(session),
        CitationRepository(session),
        AuditService(AuditRepository(session)),
    )
