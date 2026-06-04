from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..dependencies import get_db_session
from ..models import Role, User
from ..persistence_schemas import (
    AuthConfigResponse,
    AuthGoogleLoginRequest,
    AuthLoginRequest,
    AuthLogoutResponse,
    AuthSessionResponse,
    AuthSignupRequest,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
PASSWORD_SCHEME = "pbkdf2_sha256"


@router.get("/config", response_model=AuthConfigResponse)
def auth_config(settings: Annotated[Settings, Depends(get_settings)]) -> AuthConfigResponse:
    return AuthConfigResponse(
        google_client_id_configured=bool(settings.google_client_id),
        google_client_id=settings.google_client_id,
        auth_mode="password_with_signed_demo_token",
    )


@router.post("/signup", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: AuthSignupRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionResponse:
    existing = _find_user(session, payload.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    role_code = _role_code(payload.role)
    _ensure_role(session, role_code)
    user = User(
        external_user_id=payload.email,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=_hash_password(payload.password),
        auth_provider="password",
        role_code=role_code,
        status="active",
    )
    session.add(user)
    session.flush()
    return _session_response(user, payload.tenant_id, settings, message="Account created successfully.")


@router.post("/login", response_model=AuthSessionResponse)
def login(
    payload: AuthLoginRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionResponse:
    identifier = payload.user_id or payload.email
    if not identifier:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Email or username is required.")

    user = _find_user(session, identifier)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email/username or password.")
    if not user.password_hash or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email/username or password.")

    user.last_login_at = datetime.now(UTC)
    session.flush()
    return _session_response(user, payload.tenant_id, settings, message="Signed in successfully.")


@router.post("/google", response_model=AuthSessionResponse)
def google_login(
    payload: AuthGoogleLoginRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionResponse:
    if not settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GOOGLE_CLIENT_ID is not configured.")

    google_claims = _verify_google_credential(payload.credential, settings.google_client_id)
    email = str(google_claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google token did not include an email address.")
    if google_claims.get("email_verified") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email address is not verified.")

    user = _find_user(session, email)
    if user is None:
        role_code = _role_code(payload.role)
        _ensure_role(session, role_code)
        user = User(
            external_user_id=email,
            full_name=str(google_claims.get("name") or email),
            email=email,
            password_hash=None,
            auth_provider="google",
            role_code=role_code,
            status="active",
        )
        session.add(user)
        session.flush()
    elif user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active.")
    elif user.auth_provider not in {"google", "password"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account provider is not supported for Google sign-in.")

    user.last_login_at = datetime.now(UTC)
    session.flush()
    return _session_response(user, payload.tenant_id, settings, message="Signed in with Google successfully.")


@router.post("/logout", response_model=AuthLogoutResponse)
def logout() -> AuthLogoutResponse:
    return AuthLogoutResponse(message="Session cleared. Remove the bearer token on the client.")


@router.get("/me", response_model=AuthSessionResponse)
def me(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Annotated[Session, Depends(get_db_session)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> AuthSessionResponse:
    token = _bearer_token(authorization)
    claims = _decode_token(token, settings)
    user = _find_user(session, str(claims["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user is no longer active.")
    return _session_response(user, str(claims.get("tenant_id") or "sandbox"), settings, message="Session active.")


def _session_response(user: User, tenant_id: str, settings: Settings, *, message: str) -> AuthSessionResponse:
    role = _public_role(user.role_code)
    role_code = _role_code(role)
    token = _encode_token(
        {
            "sub": user.email,
            "name": user.full_name,
            "role": role,
            "role_code": role_code,
            "tenant_id": tenant_id,
        },
        settings,
    )
    return AuthSessionResponse(
        authenticated=True,
        user_id=user.email,
        full_name=user.full_name,
        email=user.email,
        role=role,
        role_code=role_code,
        tenant_id=tenant_id,
        token=token,
        message=message,
        google_client_id_configured=bool(settings.google_client_id),
    )


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return f"{PASSWORD_SCHEME}${salt}${base64.urlsafe_b64encode(digest).decode('ascii')}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, salt, expected = password_hash.split("$", 2)
    except ValueError:
        return False
    if scheme != PASSWORD_SCHEME:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    actual = base64.urlsafe_b64encode(digest).decode("ascii")
    return hmac.compare_digest(actual, expected)


def _verify_google_credential(credential: str, google_client_id: str) -> dict[str, Any]:
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="google-auth is required for Google sign-in. Install requirements.txt and restart the backend.",
        ) from exc

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google OAuth credential.") from exc
    if not isinstance(claims, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google OAuth credential.")
    return claims


def _encode_token(payload: dict[str, Any], settings: Settings) -> str:
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


def _decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.") from exc
    if not hmac.compare_digest(_signature(body, settings), signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.")
    claims = json.loads(base64.urlsafe_b64decode(_pad_b64(body)).decode("utf-8"))
    if int(claims.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session token expired.")
    return claims


def _signature(body: str, settings: Settings) -> str:
    key = settings.auth_secret_key.get_secret_value().encode("utf-8")
    return _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _pad_b64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    return authorization.removeprefix("Bearer ").strip()


def _find_user(session: Session, identifier: str) -> User | None:
    return session.scalar(
        select(User).where((User.email == identifier) | (User.external_user_id == identifier))
    )


def _ensure_role(session: Session, role_code: str) -> Role:
    role = session.get(Role, role_code)
    if role is None:
        role = Role(
            role_code=role_code,
            role_name="Clinical Admin" if role_code == "clinical_admin" else "Doctor",
            description="Application authentication role.",
        )
        session.add(role)
        session.flush()
    return role


def _role_code(role: str) -> str:
    return "clinical_admin" if role == "admin" else "doctor"


def _public_role(role_code: str) -> str:
    return "admin" if role_code == "clinical_admin" else "doctor"
