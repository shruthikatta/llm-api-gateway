"""phase2_teams_policies_permissions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-16 11:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_teams_org_slug"),
    )
    op.create_index("ix_teams_org", "teams", ["organization_id"])
    op.create_index("ix_teams_active", "teams", ["is_active"])

    op.create_table(
        "team_provider_permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("is_allowed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "provider_id", name="uq_team_provider"),
    )
    op.create_index(
        "ix_team_provider_permissions_team",
        "team_provider_permissions",
        ["team_id"],
    )

    op.create_table(
        "team_allowed_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["llm_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "model_id", name="uq_team_model"),
    )
    op.create_index("ix_team_allowed_models_team", "team_allowed_models", ["team_id"])

    op.create_table(
        "team_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("compliance_prompt", sa.Text(), nullable=True),
        sa.Column(
            "content_filter_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "routing_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "enrichment_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
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
        sa.UniqueConstraint("team_id"),
    )

    op.add_column("api_keys", sa.Column("team_id", sa.UUID(), nullable=True))
    op.create_index("ix_api_keys_team_id", "api_keys", ["team_id"])
    op.create_foreign_key(
        "fk_api_keys_team_id",
        "api_keys",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_api_keys_team_id", "api_keys", type_="foreignkey")
    op.drop_index("ix_api_keys_team_id", table_name="api_keys")
    op.drop_column("api_keys", "team_id")

    op.drop_table("team_policies")
    op.drop_index("ix_team_allowed_models_team", table_name="team_allowed_models")
    op.drop_table("team_allowed_models")
    op.drop_index(
        "ix_team_provider_permissions_team",
        table_name="team_provider_permissions",
    )
    op.drop_table("team_provider_permissions")
    op.drop_index("ix_teams_active", table_name="teams")
    op.drop_index("ix_teams_org", table_name="teams")
    op.drop_table("teams")
