import uuid
from datetime import UTC, datetime
from typing import Any

from ..models import AuditLog
from ..persistence_schemas import AuditLogListResponse, AuditLogResponse
from ..repositories import AuditRepository
from .persistence_common import PersistedResourceNotFoundError
from .persistence_common import pagination


GLOBAL_AUDIT_ROLES = {"clinical_admin", "it_admin", "auditor", "ai_safety_reviewer"}
LIMITED_AUDIT_ROLE = "doctor"
SENSITIVE_METADATA_KEYS = {
    "raw_text",
    "edited_summary_text",
    "source_text_span",
    "highlighted_span",
    "surrounding_context",
}


class AuditPermissionError(PermissionError):
    pass


class AuditService:
    def __init__(self, repository: AuditRepository):
        self.repository = repository

    def record(
        self,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        return self.repository.add(
            AuditLog(
                user_id=user_id,
                patient_id=patient_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json=metadata,
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )

    def list(
        self,
        *,
        page: int,
        page_size: int,
        role_code: str | None = None,
        actor_external_id: str | None = None,
        patient_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> AuditLogListResponse:
        self._require_list_permission(
            role_code,
            has_filter=any(
                (patient_id, user_id, action, resource_type, resource_id, from_date, to_date)
            ),
        )
        events, total = self.repository.list(
            page=page,
            page_size=page_size,
            patient_id=patient_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            from_date=from_date,
            to_date=to_date,
        )
        summary_contexts = self.repository.summary_contexts(
            {
                event.resource_id
                for event in events
                if event.resource_type == "summary" and event.resource_id is not None
            }
        )
        display_names = self.repository.user_display_names(
            {event.user_id for event in events if event.user_id}
        )
        return AuditLogListResponse(
            items=[
                self._response(
                    item,
                    display_names.get(item.user_id),
                    summary_context=summary_contexts.get(item.resource_id),
                )
                for item in events
            ],
            pagination=pagination(page, page_size, total),
        )

    def detail(
        self,
        audit_id: uuid.UUID,
        *,
        role_code: str,
        actor_external_id: str,
    ) -> AuditLogResponse:
        event = self.repository.get(audit_id)
        if event is None:
            raise PersistedResourceNotFoundError("Audit log was not found.")
        self._require_detail_permission(event, role_code, actor_external_id)
        display_names = self.repository.user_display_names({event.user_id} if event.user_id else set())
        summary_contexts = self.repository.summary_contexts(
            {event.resource_id}
            if event.resource_type == "summary" and event.resource_id is not None
            else set()
        )
        return self._response(
            event,
            display_names.get(event.user_id),
            summary_context=summary_contexts.get(event.resource_id),
        )

    @staticmethod
    def _require_list_permission(role_code: str | None, *, has_filter: bool) -> None:
        if role_code in GLOBAL_AUDIT_ROLES:
            return
        if role_code == LIMITED_AUDIT_ROLE:
            return
        raise AuditPermissionError("This role cannot view global audit logs.")

    @staticmethod
    def _require_detail_permission(
        event: AuditLog,
        role_code: str,
        actor_external_id: str,
    ) -> None:
        if role_code in GLOBAL_AUDIT_ROLES:
            return
        metadata = event.metadata_json or {}
        if role_code == LIMITED_AUDIT_ROLE and metadata.get("actor_external_id") == actor_external_id:
            return
        raise AuditPermissionError("This role cannot view this audit log.")

    @staticmethod
    def _response(
        event: AuditLog,
        user_display_name: str | None = None,
        *,
        summary_context: dict[str, Any] | None = None,
    ) -> AuditLogResponse:
        metadata = {
            key: value
            for key, value in (_safe_metadata(event.metadata_json) or {}).items()
            if value is not None
        }
        if summary_context:
            metadata = {
                key: value
                for key, value in {**summary_context, **metadata}.items()
                if value is not None
            }
        return AuditLogResponse(
            audit_id=event.audit_id,
            user_id=event.user_id,
            user_display_name=user_display_name,
            patient_id=event.patient_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            metadata=metadata,
            action_metadata=metadata,
            ip_address=event.ip_address,
            timestamp=event.timestamp,
            created_at=event.timestamp,
        )


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return metadata
    return {
        key: value
        for key, value in metadata.items()
        if key not in SENSITIVE_METADATA_KEYS
    }
