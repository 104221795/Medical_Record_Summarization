from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..dependencies import RequestContext, get_audit_service, get_encounter_service, get_request_context
from ..persistence_schemas import EncounterListResponse, EncounterResponse
from ..services.audit_service import AuditService
from ..services.encounter_service import EncounterService
from ..services.persistence_common import PersistedResourceNotFoundError, require_uuid


router = APIRouter(tags=["Encounters"])


@router.get("/patients/{patient_id}/encounters", response_model=EncounterListResponse)
def list_patient_encounters(
    patient_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EncounterService, Depends(get_encounter_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> EncounterListResponse:
    try:
        result = service.list_by_patient(patient_id)
        resolved_patient_id = (
            result.items[0].patient_id if result.items else require_uuid(patient_id, "Patient")
        )
        audit.record(
            action="view_encounters",
            patient_id=resolved_patient_id,
            resource_type="encounter_collection",
            metadata={"tenant_id": context.tenant_id, "actor_external_id": context.user_id},
        )
        return result
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/encounters/{encounter_id}", response_model=EncounterResponse)
def get_encounter(
    encounter_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EncounterService, Depends(get_encounter_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> EncounterResponse:
    try:
        result = service.get(encounter_id)
        audit.record(
            action="view_encounter",
            patient_id=result.patient_id,
            resource_type="encounter",
            resource_id=result.encounter_id,
            metadata={"tenant_id": context.tenant_id, "actor_external_id": context.user_id},
        )
        return result
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
