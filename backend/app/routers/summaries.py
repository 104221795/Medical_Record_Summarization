from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from ..dependencies import (
    RequestContext,
    get_request_context,
    get_review_service,
    get_summary_service,
)
from ..persistence_schemas import (
    ModelJobResponse,
    SummaryApproveRequest,
    SummaryDetailResponse,
    SummaryEditRequest,
    SummaryGenerateRequest,
    SummaryGenerateResponse,
    SummaryRegenerateRequest,
    SummaryRegenerateResponse,
    SummaryRejectRequest,
    SummaryReviewActionResponse,
    SummaryReviewListResponse,
    SummaryReviewStartResponse,
)
from ..services.background_jobs import model_job_service
from ..services.deterministic_summary_service import (
    DeterministicSummaryService,
    SummaryGenerationError,
)
from ..services.persistence_common import PersistedResourceNotFoundError
from ..services.review_service import (
    ReviewPermissionError,
    ReviewService,
    ReviewTransitionError,
)
from ..services.llm_gateway import SummaryProviderGateway


router = APIRouter(tags=["Summaries"])


@router.post(
    "/patients/{patient_id}/summaries/generate",
    response_model=SummaryGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_patient_summary(
    request: Request,
    patient_id: Annotated[str, Path(min_length=1, max_length=128)],
    payload: SummaryGenerateRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[DeterministicSummaryService, Depends(get_summary_service)],
) -> SummaryGenerateResponse:
    try:
        selected_provider = str(payload.model_provider or payload.provider or "deterministic")
        _require_selectable_provider(request, selected_provider)
        return service.generate(
            patient_id,
            payload,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SummaryGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post(
    "/patients/{patient_id}/summaries/generate-async",
    response_model=ModelJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_patient_summary_async(
    request: Request,
    patient_id: Annotated[str, Path(min_length=1, max_length=128)],
    payload: SummaryGenerateRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> ModelJobResponse:
    selected_provider = str(payload.model_provider or payload.provider or "deterministic")
    _require_selectable_provider(request, selected_provider)
    return model_job_service.enqueue_summary_generation(
        patient_id=patient_id,
        request_payload=payload.model_dump(mode="json"),
        tenant_id=context.tenant_id,
        actor_external_id=context.user_id,
        model_provider=selected_provider,
        timeout_seconds=_generation_timeout_seconds(selected_provider),
    )


def _require_selectable_provider(request: Request, selected_provider: str) -> None:
    settings = request.app.state.settings
    if settings.environment == "test":
        injected = getattr(request.app.state, "summary_model_providers", {})
        if selected_provider in injected:
            return
        if (
            selected_provider == "gemini"
            and settings.llm_provider == "gemini"
            and getattr(request.app.state, "gemini_json_client", None) is not None
        ):
            return
    provider = next(
        (
            item
            for item in SummaryProviderGateway(settings).list_providers().providers
            if item.provider_name == selected_provider
        ),
        None,
    )
    if provider is None or not provider.selectable:
        reason = provider.disabled_reason if provider else "Provider is not registered."
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Provider '{selected_provider}' is unavailable: {reason}",
        )


@router.get("/summaries/{summary_id}", response_model=SummaryDetailResponse)
def get_summary(
    summary_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[DeterministicSummaryService, Depends(get_summary_service)],
) -> SummaryDetailResponse:
    try:
        summary = service.get_summary_model(summary_id)
        service.record_view(
            summary,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
        )
        return service.detail(summary_id)
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/summaries/{summary_id}/regenerate",
    response_model=SummaryRegenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def regenerate_summary(
    summary_id: Annotated[str, Path(min_length=1, max_length=128)],
    payload: SummaryRegenerateRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[DeterministicSummaryService, Depends(get_summary_service)],
) -> SummaryRegenerateResponse:
    try:
        return service.regenerate(
            summary_id,
            payload,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SummaryGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post(
    "/summaries/{summary_id}/review/start",
    response_model=SummaryReviewStartResponse,
)
def start_summary_review(
    summary_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> SummaryReviewStartResponse:
    try:
        return service.start_review(
            summary_id,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
            role_code=context.role_code,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReviewTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch(
    "/summaries/{summary_id}/edit",
    response_model=SummaryReviewActionResponse,
)
def edit_summary(
    summary_id: Annotated[str, Path(min_length=1, max_length=128)],
    payload: SummaryEditRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> SummaryReviewActionResponse:
    try:
        return service.edit(
            summary_id,
            payload,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
            role_code=context.role_code,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReviewTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/summaries/{summary_id}/approve",
    response_model=SummaryReviewActionResponse,
)
def approve_summary(
    summary_id: Annotated[str, Path(min_length=1, max_length=128)],
    payload: SummaryApproveRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> SummaryReviewActionResponse:
    try:
        return service.approve(
            summary_id,
            payload,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
            role_code=context.role_code,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReviewTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/summaries/{summary_id}/reject",
    response_model=SummaryReviewActionResponse,
)
def reject_summary(
    summary_id: Annotated[str, Path(min_length=1, max_length=128)],
    payload: SummaryRejectRequest,
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> SummaryReviewActionResponse:
    try:
        return service.reject(
            summary_id,
            payload,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
            role_code=context.role_code,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ReviewTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/summaries/{summary_id}/reviews",
    response_model=SummaryReviewListResponse,
)
def get_summary_reviews(
    summary_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> SummaryReviewListResponse:
    try:
        return service.history(
            summary_id,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
            role_code=context.role_code,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def _generation_timeout_seconds(provider: str) -> int:
    if provider in {"qwen2.5", "llama3.2", "gemini2.5_flash_lite"}:
        return 240
    if provider in {"bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail", "pegasus_xsum"}:
        return 900
    return 120
