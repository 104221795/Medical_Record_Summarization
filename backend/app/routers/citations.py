from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..dependencies import RequestContext, get_citation_service, get_request_context
from ..persistence_schemas import CitationSourceResponse
from ..services.citation_service import CitationService
from ..services.persistence_common import PersistedResourceNotFoundError


router = APIRouter(prefix="/citations", tags=["Citations"])


@router.get("/{citation_id}/source", response_model=CitationSourceResponse)
def get_citation_source(
    citation_id: Annotated[str, Path(min_length=1, max_length=128)],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[CitationService, Depends(get_citation_service)],
) -> CitationSourceResponse:
    try:
        return service.source(
            citation_id,
            tenant_id=context.tenant_id,
            actor_external_id=context.user_id,
        )
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
