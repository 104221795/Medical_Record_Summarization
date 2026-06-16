import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..dependencies import RequestContext, get_audit_service, get_request_context, require_roles
from ..persistence_schemas import AuditExportResponse, AuditLogListResponse, AuditLogResponse
from ..services.audit_service import AuditPermissionError, AuditService
from ..services.persistence_common import PersistedResourceNotFoundError


router = APIRouter(prefix="/audit", tags=["Audit"])

AUDIT_EXPORT_ROLES = ("clinical_admin", "it_admin", "auditor", "ai_safety_reviewer")


@router.get("/logs", response_model=AuditLogListResponse)
def list_audit_logs(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AuditService, Depends(get_audit_service)],
    patient_id: Annotated[uuid.UUID | None, Query()] = None,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    resource_type: Annotated[str | None, Query(max_length=100)] = None,
    resource_id: Annotated[uuid.UUID | None, Query()] = None,
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogListResponse:
    try:
        result = service.list(
            page=page,
            page_size=page_size,
            role_code=context.role_code,
            actor_external_id=context.user_id,
            patient_id=patient_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            from_date=from_date,
            to_date=to_date,
        )
    except AuditPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    service.record(
        action="view_audit_logs",
        resource_type="audit_log_collection",
        metadata={
            "tenant_id": context.tenant_id,
            "actor_external_id": context.user_id,
            "role_code": context.role_code,
            "filters": {
                "patient_id": str(patient_id) if patient_id else None,
                "user_id": str(user_id) if user_id else None,
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "from_date": from_date.isoformat() if from_date else None,
                "to_date": to_date.isoformat() if to_date else None,
            },
        },
    )
    return result


@router.get("/export", response_model=AuditExportResponse)
def export_audit_logs(
    context: Annotated[RequestContext, Depends(require_roles(*AUDIT_EXPORT_ROLES))],
    service: Annotated[AuditService, Depends(get_audit_service)],
    patient_id: Annotated[uuid.UUID | None, Query()] = None,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    resource_type: Annotated[str | None, Query(max_length=100)] = None,
    resource_id: Annotated[uuid.UUID | None, Query()] = None,
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
    page_size: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> AuditExportResponse:
    try:
        result = service.export(
            role_code=context.role_code,
            page_size=page_size,
            patient_id=patient_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            from_date=from_date,
            to_date=to_date,
        )
    except AuditPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    service.record(
        action="export_audit_logs",
        resource_type="audit_log_collection",
        metadata={
            "tenant_id": context.tenant_id,
            "actor_external_id": context.user_id,
            "role_code": context.role_code,
            "export_version": result.export_version,
            "row_count": result.row_count,
            "filters": result.filters,
            "phi_safe": result.phi_safe,
        },
    )
    return result


@router.get("/logs/{audit_id}", response_model=AuditLogResponse)
def get_audit_log_detail(
    audit_id: Annotated[uuid.UUID, Path()],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[AuditService, Depends(get_audit_service)],
) -> AuditLogResponse:
    try:
        result = service.detail(
            audit_id,
            role_code=context.role_code,
            actor_external_id=context.user_id,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AuditPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    service.record(
        action="view_audit_log_detail",
        resource_type="audit_log",
        resource_id=audit_id,
        metadata={
            "tenant_id": context.tenant_id,
            "actor_external_id": context.user_id,
            "role_code": context.role_code,
        },
    )
    return result
