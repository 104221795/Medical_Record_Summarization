import math
import uuid

from ..persistence_schemas import PaginationResponse


class PersistedResourceNotFoundError(LookupError):
    pass


class IngestionValidationError(ValueError):
    pass


def require_uuid(value: str, resource_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise PersistedResourceNotFoundError(f"{resource_name} was not found.") from exc


def pagination(page: int, page_size: int, total: int) -> PaginationResponse:
    total_pages = math.ceil(total / page_size) if total else 0
    return PaginationResponse(
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
    )
