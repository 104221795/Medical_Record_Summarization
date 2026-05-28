from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import (
    RequestContext,
    get_clinical_pipeline_service,
    get_request_context,
)
from ..schemas import ClinicalNotesSummaryRequest, ClinicalNotesSummaryResponse
from ..services.clinical_pipeline import ClinicalSummaryPipelineService
from ..services.generators import GenerationError
from ..services.rag import RetrievalError


router = APIRouter(prefix="/clinical-summaries", tags=["Clinical Summary Pipeline"])


@router.post(":generate-cited", response_model=ClinicalNotesSummaryResponse)
def summarize_submitted_notes(
    payload: ClinicalNotesSummaryRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ClinicalSummaryPipelineService, Depends(get_clinical_pipeline_service)],
) -> ClinicalNotesSummaryResponse:
    """Ingest raw clinical notes and return a guarded citation-based AI draft."""
    try:
        return service.summarize_clinical_notes(context.tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except RetrievalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
