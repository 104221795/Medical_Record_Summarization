from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import RequestContext, get_metrics_service, get_request_context
from ..persistence_schemas import (
    ReviewMetricsResponse,
    SafetyMetricsResponse,
    SummaryQualityMetricsResponse,
    UsageMetricsResponse,
)
from ..services.metrics_service import MetricsPermissionError, MetricsService


router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/summary-quality", response_model=SummaryQualityMetricsResponse)
def summary_quality_metrics(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[MetricsService, Depends(get_metrics_service)],
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
    department: Annotated[str | None, Query(max_length=255)] = None,
    summary_type: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[
        Literal["draft", "under_review", "edited", "approved", "rejected", "archived"] | None,
        Query(alias="status"),
    ] = None,
) -> SummaryQualityMetricsResponse:
    try:
        return service.summary_quality(
            role_code=context.role_code,
            from_date=from_date,
            to_date=to_date,
            department=department,
            summary_type=summary_type,
            status=status_filter,
        )
    except MetricsPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/usage", response_model=UsageMetricsResponse)
def usage_metrics(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> UsageMetricsResponse:
    try:
        return service.usage(role_code=context.role_code)
    except MetricsPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/safety", response_model=SafetyMetricsResponse)
def safety_metrics(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> SafetyMetricsResponse:
    try:
        return service.safety(role_code=context.role_code)
    except MetricsPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/review", response_model=ReviewMetricsResponse)
def review_metrics(
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[MetricsService, Depends(get_metrics_service)],
) -> ReviewMetricsResponse:
    try:
        return service.review(role_code=context.role_code)
    except MetricsPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
