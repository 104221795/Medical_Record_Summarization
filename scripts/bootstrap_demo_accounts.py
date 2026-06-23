from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy import select

from backend.app.config import Settings
from backend.app.db.seed import seed_mock_data
from backend.app.db.session import (
    build_engine_from_settings,
    create_session_factory,
    session_scope,
)
from backend.app.models import User
from backend.app.persistence_schemas import AuthSignupRequest
from backend.app.routers.auth import _hash_password


DEMO_ACCOUNTS = (
    {
        "external_user_id": "doctor-demo",
        "email": "doctor.demo@example.invalid",
        "full_name": "De-identified Demo Doctor",
        "role": "doctor",
    },
    {
        "external_user_id": "clinical-admin-demo",
        "email": "clinical.admin@example.invalid",
        "full_name": "De-identified Clinical Admin",
        "role": "admin",
    },
)


def main() -> None:
    args = parse_args()
    settings = Settings()
    if settings.environment == "production":
        raise RuntimeError("Demo account bootstrap is disabled in production.")

    password = os.environ.get(args.password_env) or _prompt_for_password()
    for account in DEMO_ACCOUNTS:
        AuthSignupRequest(
            full_name=account["full_name"],
            email=account["email"],
            password=password,
            confirm_password=password,
            role=account["role"],
        )

    engine = build_engine_from_settings(settings)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        seed_mock_data(session)
        for account in DEMO_ACCOUNTS:
            user = session.scalar(
                select(User).where(
                    User.external_user_id == account["external_user_id"]
                )
            )
            if user is None:
                raise RuntimeError(
                    f"Seeded demo account {account['external_user_id']} was not found."
                )
            user.password_hash = _hash_password(password)
            user.auth_provider = "password"
            user.status = "active"

    print("Local demo accounts are ready:")
    for account in DEMO_ACCOUNTS:
        print(f"- {account['role']}: {account['email']}")
    print("The password was not printed or stored in the repository.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed de-identified local demo data and set passwords for the "
            "doctor/admin demo accounts."
        )
    )
    parser.add_argument(
        "--password-env",
        default="RAG_DEMO_ACCOUNT_PASSWORD",
        help=(
            "Environment variable containing the temporary demo password. "
            "If unset, the script prompts without echo."
        ),
    )
    return parser.parse_args()


def _prompt_for_password() -> str:
    password = getpass.getpass("Temporary local demo password: ")
    confirmation = getpass.getpass("Confirm temporary local demo password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    return password


if __name__ == "__main__":
    main()
