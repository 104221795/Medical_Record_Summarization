from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import Settings
from ..db.base import Base
from ..db.seed import seed_mock_data
from ..dependencies import (
    RequestContext,
    get_db_session,
    get_evaluation_service,
    get_request_context,
)
from ..persistence_schemas import DemoReadinessResponse, DemoSeedResponse
from ..services.evaluation_service import EvaluationService


router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/readiness", response_model=DemoReadinessResponse)
def demo_readiness(
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> DemoReadinessResponse:
    return service.demo_readiness()


@router.post("/seed", response_model=DemoSeedResponse, status_code=status.HTTP_201_CREATED)
def seed_demo_data(
    request: Request,
    _context: Annotated[RequestContext, Depends(get_request_context)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DemoSeedResponse:
    settings: Settings = request.app.state.settings
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo seeding is disabled in production.",
        )

    Base.metadata.create_all(bind=session.get_bind())
    result = seed_mock_data(session)
    return DemoSeedResponse(
        patient_id=result.patient_id,
        encounter_id=result.encounter_id,
        summary_id=result.summary_id,
        created=result.created,
        message=(
            "Ten de-identified demo patients and clinical evidence records are ready."
            if result.created
            else "De-identified demo data already exists."
        ),
    )
