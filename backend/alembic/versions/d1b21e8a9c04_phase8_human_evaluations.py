"""phase8 human evaluations

Revision ID: d1b21e8a9c04
Revises: c6b0b16f9b78
Create Date: 2026-05-28 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1b21e8a9c04"
down_revision: Union[str, Sequence[str], None] = "c6b0b16f9b78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "human_evaluations",
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("summary_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_id", sa.String(length=100), nullable=True),
        sa.Column("evaluator_name", sa.String(length=255), nullable=True),
        sa.Column("model_provider", sa.String(length=100), nullable=True),
        sa.Column("factual_correctness_score", sa.Integer(), nullable=False),
        sa.Column("completeness_score", sa.Integer(), nullable=False),
        sa.Column("conciseness_score", sa.Integer(), nullable=False),
        sa.Column("readability_score", sa.Integer(), nullable=False),
        sa.Column("citation_usefulness_score", sa.Integer(), nullable=False),
        sa.Column("hallucination_risk", sa.String(length=20), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "factual_correctness_score BETWEEN 1 AND 5",
            name="ck_human_eval_factual_score_range",
        ),
        sa.CheckConstraint(
            "completeness_score BETWEEN 1 AND 5",
            name="ck_human_eval_completeness_score_range",
        ),
        sa.CheckConstraint(
            "conciseness_score BETWEEN 1 AND 5",
            name="ck_human_eval_conciseness_score_range",
        ),
        sa.CheckConstraint(
            "readability_score BETWEEN 1 AND 5",
            name="ck_human_eval_readability_score_range",
        ),
        sa.CheckConstraint(
            "citation_usefulness_score BETWEEN 1 AND 5",
            name="ck_human_eval_citation_score_range",
        ),
        sa.CheckConstraint(
            "hallucination_risk IN ('low', 'medium', 'high')",
            name="ck_human_eval_hallucination_risk",
        ),
        sa.ForeignKeyConstraint(["summary_id"], ["summaries.summary_id"]),
        sa.PrimaryKeyConstraint("evaluation_id"),
    )
    op.create_index(
        op.f("ix_human_evaluations_summary_id"),
        "human_evaluations",
        ["summary_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_human_evaluations_summary_id"), table_name="human_evaluations")
    op.drop_table("human_evaluations")
