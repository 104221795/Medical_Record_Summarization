"""phase5 review workflow fields

Revision ID: c6b0b16f9b78
Revises: b888cb77eb72
Create Date: 2026-05-28 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6b0b16f9b78"
down_revision: Union[str, Sequence[str], None] = "b888cb77eb72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "summary_reviews",
        sa.Column("edit_distance_score", sa.Numeric(precision=8, scale=4), nullable=True),
    )
    op.add_column(
        "summary_reviews",
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("summary_reviews", "reviewed_at")
    op.drop_column("summary_reviews", "edit_distance_score")
