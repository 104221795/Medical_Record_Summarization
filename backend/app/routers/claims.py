from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..dependencies import RequestContext, get_citation_service, get_request_context
from ..persistence_schemas import ClaimCitationListResponse
from ..services.citation_service import CitationService
from ..services.persistence_common import PersistedResourceNotFoundError


router = APIRouter(prefix="/claims", tags=["Claims"])


@router.get("/{claim_id}/citations", response_model=ClaimCitationListResponse)
def get_claim_citations(
    claim_id: Annotated[str, Path(min_length=1, max_length=128)],
    _context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[CitationService, Depends(get_citation_service)],
) -> ClaimCitationListResponse:
    try:
        return service.list_by_claim(claim_id)
    except PersistedResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
