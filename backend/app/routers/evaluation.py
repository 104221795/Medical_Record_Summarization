from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..dependencies import RequestContext, get_evaluation_service, get_request_context
from ..persistence_schemas import (
    BenchmarkFlowComparisonResponse,
    BenchmarkResultsResponse,
    BenchmarkStatusResponse,
    EvaluationStatusResponse,
    FunctionalValidationResponse,
    HumanEvaluationCreateRequest,
    HumanEvaluationListResponse,
    HumanEvaluationResponse,
    HumanEvaluationSummaryResponse,
)
from ..services.evaluation_service import EvaluationService


router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.get("/status", response_model=EvaluationStatusResponse)
def evaluation_status(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationStatusResponse:
    return service.status()


@router.get("/functional/status", response_model=FunctionalValidationResponse)
def functional_status(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> FunctionalValidationResponse:
    return service.functional_status()


@router.post("/functional/run", response_model=FunctionalValidationResponse)
def run_functional_validation(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> FunctionalValidationResponse:
    return service.run_functional_validation(
        tenant_id=context.tenant_id,
        actor_external_id=context.user_id,
    )


@router.get("/benchmark/status", response_model=BenchmarkStatusResponse)
def benchmark_status(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> BenchmarkStatusResponse:
    return service.benchmark_status()


@router.get("/benchmark/results", response_model=BenchmarkResultsResponse)
def benchmark_results(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    benchmark_type: Annotated[
        str | None,
        Query(pattern="^(summarization_only|clinical_context|rag_grounded|rag_best_models)$"),
    ] = None,
) -> BenchmarkResultsResponse:
    return service.benchmark_results(benchmark_type=benchmark_type)


@router.get("/benchmark/flow-comparison", response_model=BenchmarkFlowComparisonResponse)
def benchmark_flow_comparison(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
    provider: Annotated[str | None, Query(max_length=80)] = None,
) -> BenchmarkFlowComparisonResponse:
    return service.benchmark_flow_comparison(limit=limit, provider=provider)


@router.post(
    "/human",
    response_model=HumanEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_human_evaluation(
    payload: HumanEvaluationCreateRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> HumanEvaluationResponse:
    try:
        return service.create_human_evaluation(
            payload,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/human/summary", response_model=HumanEvaluationSummaryResponse)
def human_evaluation_summary(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> HumanEvaluationSummaryResponse:
    return service.human_summary()


@router.get("/human/by-summary/{summary_id}", response_model=HumanEvaluationListResponse)
def human_evaluations_by_summary(
    summary_id: Annotated[uuid.UUID, Path()],
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> HumanEvaluationListResponse:
    return service.human_by_summary(summary_id)
