"""phase3_rate_limits_budgets_audit

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-16 14:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

rate_limit_priority = postgresql.ENUM(
    "low",
    "normal",
    "high",
    name="rate_limit_priority",
    create_type=False,
)


def upgrade() -> None:
    rate_limit_priority.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "llm_models",
        sa.Column(
            "input_price_per_million_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0.500000",
        ),
    )
    op.add_column(
        "llm_models",
        sa.Column(
            "output_price_per_million_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="1.500000",
        ),
    )

    op.create_table(
        "team_rate_limits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("tokens_per_minute", sa.Integer(), nullable=False),
        sa.Column("burst_multiplier", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column(
            "priority",
            rate_limit_priority,
            nullable=False,
            server_default="normal",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_team_rate_limit_team"),
    )
    op.create_index("ix_team_rate_limits_team", "team_rate_limits", ["team_id"])

    op.create_table(
        "team_budgets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("daily_budget_usd", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "monthly_budget_usd",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
        ),
        sa.Column("warning_threshold_pct", sa.Integer(), nullable=False),
        sa.Column("hard_enforcement", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_team_budget_team"),
    )
    op.create_index("ix_team_budgets_team", "team_budgets", ["team_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_user_id"])
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id"],
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_team_budgets_team", table_name="team_budgets")
    op.drop_table("team_budgets")

    op.drop_index("ix_team_rate_limits_team", table_name="team_rate_limits")
    op.drop_table("team_rate_limits")

    op.drop_column("llm_models", "output_price_per_million_usd")
    op.drop_column("llm_models", "input_price_per_million_usd")

    rate_limit_priority.drop(op.get_bind(), checkfirst=True)
