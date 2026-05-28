from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import (
    RequestContext,
    get_clinical_pipeline_service,
    get_fhir_mapper_service,
    get_request_context,
)
from ..fhir_schemas import (
    FhirBundleSummaryRequest,
    FhirBundleSummaryResponse,
    FhirMappingRequest,
    FhirMappingResponse,
    FhirMockPushRequest,
    FhirMockPushResponse,
    MedicalGuardrailRequest,
)
from ..medical_guardrail_schemas import MedicalGuardrailResult
from ..services.clinical_pipeline import ClinicalDataValidationError, ClinicalSummaryPipelineService
from ..services.fhir_mapper import FhirMapperService, FhirMappingError, FhirSafetyValidationError
from ..services.generators import GenerationError
from ..services.rag import RetrievalError


router = APIRouter(prefix="/fhir", tags=["FHIR Data Mapper"])


@router.post("/r4/guardrails:validate", response_model=MedicalGuardrailResult)
def validate_medical_summary_for_writeback(
    payload: MedicalGuardrailRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[FhirMapperService, Depends(get_fhir_mapper_service)],
) -> MedicalGuardrailResult:
    del context
    return service.validate_for_writeback(payload.raw_clinical_text, payload.ai_summary_json)


@router.post("/r4/bundles:ingest-and-summarize", response_model=FhirBundleSummaryResponse)
def ingest_fhir_bundle_and_summarize(
    payload: FhirBundleSummaryRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ClinicalSummaryPipelineService, Depends(get_clinical_pipeline_service)],
) -> FhirBundleSummaryResponse:
    """Validate FHIR clinical inputs and produce a guarded citation-based AI draft."""
    try:
        return service.summarize_fhir_bundle(context.tenant_id, payload)
    except (ClinicalDataValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except RetrievalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/r4/summary-bundles:map", response_model=FhirMappingResponse)
def map_summary_to_fhir(
    payload: FhirMappingRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[FhirMapperService, Depends(get_fhir_mapper_service)],
) -> FhirMappingResponse:
    try:
        return service.map_to_transaction(context.tenant_id, payload)
    except FhirSafetyValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.report.model_dump(mode="json"),
        ) from exc
    except FhirMappingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/r4/mock-server/$transaction", response_model=FhirMockPushResponse)
def mock_push_transaction(
    payload: FhirMockPushRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[FhirMapperService, Depends(get_fhir_mapper_service)],
) -> FhirMockPushResponse:
    del context
    return service.mock_push(payload.destination_base_url, payload.bundle)
