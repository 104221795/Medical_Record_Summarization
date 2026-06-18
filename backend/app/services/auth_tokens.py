from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from ..config import Settings


def encode_session_token(payload: dict[str, Any], settings: Settings) -> str:
    now = datetime.now(UTC)
    claims = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.auth_token_ttl_minutes)).timestamp()),
        "auth_mode": "signed_password_session",
    }
    body = _b64(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    signature = _signature(body, settings)
    return f"{body}.{signature}"


def decode_session_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token.",
        ) from exc
    if not hmac.compare_digest(_signature(body, settings), signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token.",
        )
    try:
        claims = json.loads(base64.urlsafe_b64decode(_pad_b64(body)).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token.",
        ) from exc
    if int(claims.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token expired.",
        )
    return claims


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    return authorization.removeprefix("Bearer ").strip()


def _signature(body: str, settings: Settings) -> str:
    key = settings.auth_secret_key.get_secret_value().encode("utf-8")
    return _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _pad_b64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")
