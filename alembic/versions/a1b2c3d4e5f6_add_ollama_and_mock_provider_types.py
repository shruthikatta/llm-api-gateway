"""add_ollama_and_mock_provider_types

Revision ID: a1b2c3d4e5f6
Revises: 5eef1ccef64a
Create Date: 2026-07-16 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "5eef1ccef64a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enum labels match SQLAlchemy Enum member names.
    op.execute("ALTER TYPE provider_type ADD VALUE IF NOT EXISTS 'OLLAMA'")
    op.execute("ALTER TYPE provider_type ADD VALUE IF NOT EXISTS 'MOCK'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values safely; leave labels in place.
    pass
