"""auth password fields

Revision ID: e20260604auth
Revises: d1b21e8a9c04
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "e20260604auth"
down_revision = "d1b21e8a9c04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(length=50), nullable=False, server_default="password"),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("users", "auth_provider", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "password_hash")
