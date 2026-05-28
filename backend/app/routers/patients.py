from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..dependencies import RequestContext, get_audit_service, get_patient_service, get_request_context
from ..persistence_schemas import PatientDetailResponse, PatientListResponse
from ..services.audit_service import AuditService
from ..services.patient_service import PatientService
from ..services.persistence_common import PersistedResourceNotFoundError


router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=PatientListResponse)
def list_patients(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[PatientService, Depends(get_patient_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
    q: Annotated[str | None, Query(max_length=255)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PatientListResponse:
    result = service.list(page, page_size, q)
    audit.record(
        action="view_patient_list",
        resource_type="patient_collection",
        metadata={"tenant_id": context.tenant_id, "actor_external_id": context.user_id},
    )
    return result


@router.get("/{patient_id}", response_model=PatientDetailResponse)
def get_patient(
    patient_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[PatientService, Depends(get_patient_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> PatientDetailResponse:
    try:
        result = service.get(patient_id)
        audit.record(
            action="view_patient",
            patient_id=result.patient_id,
            resource_type="patient",
            resource_id=result.patient_id,
            metadata={"tenant_id": context.tenant_id, "actor_external_id": context.user_id},
        )
        return result
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
