from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import RequestContext, get_ingestion_service, get_request_context
from ..persistence_schemas import FhirLikeImportRequest, ImportResponse
from ..services.ingestion_service import IngestionService
from ..services.persistence_common import IngestionValidationError


router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
def import_clinical_data(
    payload: FhirLikeImportRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> ImportResponse:
    try:
        return service.import_fhir_like(
            payload,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
        )
    except IngestionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
