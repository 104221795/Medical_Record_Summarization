from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..dependencies import RequestContext, get_rag_service, get_request_context
from ..schemas import (
    CitationSummaryResponse,
    IngestRequest,
    IngestResponse,
    RetrieveRequest,
    RetrieveResponse,
    SummaryRequest,
    SummaryResponse,
)
from ..services.generators import GenerationError
from ..services.rag import RagService, RetrievalError


router = APIRouter(prefix="/patients", tags=["RAG Pipeline"])


@router.post("/{patient_id}/records:ingest", response_model=IngestResponse)
def ingest_records(
    patient_id: Annotated[str, Path(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")],
    payload: IngestRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[RagService, Depends(get_rag_service)],
) -> IngestResponse:
    try:
        return service.ingest(context.tenant_id, patient_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/{patient_id}/evidence:retrieve", response_model=RetrieveResponse)
def retrieve_evidence(
    patient_id: Annotated[str, Path(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")],
    payload: RetrieveRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[RagService, Depends(get_rag_service)],
) -> RetrieveResponse:
    return service.retrieve(context.tenant_id, patient_id, payload.query, payload.top_k)


@router.post("/{patient_id}/summaries:generate", response_model=SummaryResponse)
def generate_summary(
    patient_id: Annotated[str, Path(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")],
    payload: SummaryRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[RagService, Depends(get_rag_service)],
) -> SummaryResponse:
    try:
        return service.summarize(context.tenant_id, patient_id, payload)
    except RetrievalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/{patient_id}/summaries:generate-cited", response_model=CitationSummaryResponse)
def generate_citation_summary(
    patient_id: Annotated[str, Path(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")],
    payload: SummaryRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[RagService, Depends(get_rag_service)],
) -> CitationSummaryResponse:
    try:
        return service.summarize_with_citations(context.tenant_id, patient_id, payload)
    except RetrievalError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
