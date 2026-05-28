from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..dependencies import RequestContext, get_audit_service, get_document_service, get_request_context
from ..persistence_schemas import DocumentChunkListResponse, DocumentDetailResponse, DocumentListResponse
from ..services.audit_service import AuditService
from ..services.document_service import DocumentService
from ..services.persistence_common import PersistedResourceNotFoundError, require_uuid


router = APIRouter(tags=["Clinical Documents"])


@router.get("/patients/{patient_id}/documents", response_model=DocumentListResponse)
def list_patient_documents(
    patient_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    encounter_id: Annotated[str | None, Query(max_length=128)] = None,
    document_type: Annotated[str | None, Query(max_length=100)] = None,
) -> DocumentListResponse:
    try:
        result = service.list_by_patient(patient_id, encounter_id, document_type)
        resolved_patient_id = (
            result.items[0].patient_id if result.items else require_uuid(patient_id, "Patient")
        )
        audit.record(
            action="view_documents",
            patient_id=resolved_patient_id,
            resource_type="document_collection",
            metadata={"tenant_id": context.tenant_id, "actor_external_id": context.user_id},
        )
        return result
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentDetailResponse:
    try:
        result = service.get(document_id)
        audit.record(
            action="view_document",
            patient_id=result.patient_id,
            resource_type="clinical_document",
            resource_id=result.document_id,
            metadata={"tenant_id": context.tenant_id, "actor_external_id": context.user_id},
        )
        return result
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/documents/{document_id}/chunks", response_model=DocumentChunkListResponse)
def list_document_chunks(
    document_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentChunkListResponse:
    try:
        document = service.get(document_id)
        result = service.list_chunks(document_id)
        audit.record(
            action="view_document_chunks",
            patient_id=document.patient_id,
            resource_type="clinical_document",
            resource_id=document.document_id,
            metadata={"tenant_id": context.tenant_id, "actor_external_id": context.user_id},
        )
        return result
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
