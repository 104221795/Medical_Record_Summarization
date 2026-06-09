from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..dependencies import RequestContext, get_request_context
from ..persistence_schemas import ModelJobCreateRequest, ModelJobListResponse, ModelJobResponse, ModelReadinessResponse
from ..services.background_jobs import model_job_service


router = APIRouter(prefix="/jobs", tags=["Model Jobs"])


@router.post("", response_model=ModelJobResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_model_job(
    payload: ModelJobCreateRequest,
    _context: Annotated[RequestContext, Depends(get_request_context)],
) -> ModelJobResponse:
    return model_job_service.enqueue(payload)


@router.get("", response_model=ModelJobListResponse)
def list_model_jobs(
    _context: Annotated[RequestContext, Depends(get_request_context)],
) -> ModelJobListResponse:
    return model_job_service.list()


@router.get("/readiness", response_model=ModelReadinessResponse)
def model_readiness(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    model: Annotated[list[str] | None, Query()] = None,
) -> ModelReadinessResponse:
    model_names = model or [
        "facebook/bart-large-cnn",
        "google/pegasus-pubmed",
        "google/pegasus-cnn_dailymail",
        "sentence-transformers/all-MiniLM-L6-v2",
        "roberta-large",
    ]
    return model_job_service.readiness(model_names)


@router.get("/{job_id}", response_model=ModelJobResponse)
def get_model_job(
    job_id: Annotated[str, Path(min_length=8, max_length=80)],
    _context: Annotated[RequestContext, Depends(get_request_context)],
) -> ModelJobResponse:
    job = model_job_service.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model job not found.")
    return job


@router.post("/{job_id}/cancel", response_model=ModelJobResponse)
def cancel_model_job(
    job_id: Annotated[str, Path(min_length=8, max_length=80)],
    _context: Annotated[RequestContext, Depends(get_request_context)],
) -> ModelJobResponse:
    job = model_job_service.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model job not found.")
    return job
