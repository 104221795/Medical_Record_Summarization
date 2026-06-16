"""persisted model jobs

Revision ID: f20260616jobs
Revises: e20260604auth
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "f20260616jobs"
down_revision = "e20260604auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("model_jobs"):
        op.create_table(
            "model_jobs",
            sa.Column("job_id", sa.Uuid(), nullable=False),
            sa.Column("job_type", sa.String(length=100), nullable=False),
            sa.Column("model_provider", sa.String(length=100), nullable=False),
            sa.Column("model_name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("progress", sa.Float(), nullable=False),
            sa.Column("current_step", sa.String(length=100), nullable=True),
            sa.Column("timeout_seconds", sa.Integer(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("job_id"),
        )

    existing_indexes = {index["name"] for index in inspect(bind).get_indexes("model_jobs")}
    if op.f("ix_model_jobs_job_type") not in existing_indexes:
        op.create_index(op.f("ix_model_jobs_job_type"), "model_jobs", ["job_type"], unique=False)
    if op.f("ix_model_jobs_model_provider") not in existing_indexes:
        op.create_index(op.f("ix_model_jobs_model_provider"), "model_jobs", ["model_provider"], unique=False)
    if op.f("ix_model_jobs_status") not in existing_indexes:
        op.create_index(op.f("ix_model_jobs_status"), "model_jobs", ["status"], unique=False)
    if "idx_model_jobs_created_status" not in existing_indexes:
        op.create_index("idx_model_jobs_created_status", "model_jobs", ["created_at", "status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("model_jobs"):
        return
    existing_indexes = {index["name"] for index in inspector.get_indexes("model_jobs")}
    if "idx_model_jobs_created_status" in existing_indexes:
        op.drop_index("idx_model_jobs_created_status", table_name="model_jobs")
    if op.f("ix_model_jobs_status") in existing_indexes:
        op.drop_index(op.f("ix_model_jobs_status"), table_name="model_jobs")
    if op.f("ix_model_jobs_model_provider") in existing_indexes:
        op.drop_index(op.f("ix_model_jobs_model_provider"), table_name="model_jobs")
    if op.f("ix_model_jobs_job_type") in existing_indexes:
        op.drop_index(op.f("ix_model_jobs_job_type"), table_name="model_jobs")
    op.drop_table("model_jobs")
