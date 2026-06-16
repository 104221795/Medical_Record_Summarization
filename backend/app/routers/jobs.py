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
    include_smoke: Annotated[bool, Query(description="Run live provider smoke checks when possible.")] = False,
) -> ModelReadinessResponse:
    model_names = model or [
        "facebook/bart-large-cnn",
        "google/pegasus-pubmed",
        "sentence-transformers/all-MiniLM-L6-v2",
        "roberta-large",
        "ollama/qwen2.5:3b",
        "ollama/llama3.2:3b",
        "gemini/gemini-2.5-flash-lite",
    ]
    return model_job_service.readiness(model_names, include_smoke=include_smoke)


@router.post("/warmup-defaults", response_model=ModelJobListResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_default_model_warmups(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    timeout_seconds: Annotated[int, Query(ge=1, le=24 * 60 * 60)] = 900,
) -> ModelJobListResponse:
    return model_job_service.enqueue_default_warmups(timeout_seconds=timeout_seconds)


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
