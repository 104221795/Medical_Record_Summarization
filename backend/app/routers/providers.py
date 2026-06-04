from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ..persistence_schemas import ProviderListResponse
from ..services.llm_gateway import SummaryProviderGateway


router = APIRouter(prefix="/providers", tags=["Providers"])


def get_provider_gateway(request: Request) -> SummaryProviderGateway:
    return SummaryProviderGateway(request.app.state.settings)


@router.get("", response_model=ProviderListResponse)
def list_summary_providers(
    gateway: Annotated[SummaryProviderGateway, Depends(get_provider_gateway)],
) -> ProviderListResponse:
    return gateway.list_providers()
