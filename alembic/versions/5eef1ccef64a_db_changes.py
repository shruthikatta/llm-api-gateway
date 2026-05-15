"""db_changes

Revision ID: 5eef1ccef64a
Revises: 1564a90795b4
Create Date: 2026-07-15 17:46:29.357186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5eef1ccef64a'
down_revision: Union[str, Sequence[str], None] = '1564a90795b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_models_active'), table_name='models')
    op.drop_index(op.f('ix_models_provider'), table_name='models')
    op.drop_table('models')

    op.create_table('llm_models',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('provider_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('display_name', sa.String(length=150), nullable=False),
    sa.Column('context_window', sa.Integer(), nullable=False),
    sa.Column('max_output_tokens', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index('ix_models_active', 'llm_models', ['is_active'], unique=False)
    op.create_index('ix_models_provider', 'llm_models', ['provider_id'], unique=False)

    op.add_column('llm_requests', sa.Column('model_id', sa.UUID(), nullable=False))
    op.drop_index(op.f('ix_llm_requests_model'), table_name='llm_requests')
    op.create_index('ix_llm_requests_model', 'llm_requests', ['model_id'], unique=False)
    op.create_foreign_key(None, 'llm_requests', 'llm_models', ['model_id'], ['id'], ondelete='RESTRICT')
    op.drop_column('llm_requests', 'model')

    op.add_column('usage_records', sa.Column('model_id', sa.UUID(), nullable=False))
    op.drop_index(op.f('ix_usage_model'), table_name='usage_records')
    op.create_index('ix_usage_model', 'usage_records', ['model_id'], unique=False)
    op.create_foreign_key(None, 'usage_records', 'llm_models', ['model_id'], ['id'], ondelete='RESTRICT')
    op.drop_column('usage_records', 'model')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('usage_records', sa.Column('model', sa.VARCHAR(length=100), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'usage_records', type_='foreignkey')
    op.drop_index('ix_usage_model', table_name='usage_records')
    op.create_index(op.f('ix_usage_model'), 'usage_records', ['model'], unique=False)
    op.drop_column('usage_records', 'model_id')

    op.add_column('llm_requests', sa.Column('model', sa.VARCHAR(length=100), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'llm_requests', type_='foreignkey')
    op.drop_index('ix_llm_requests_model', table_name='llm_requests')
    op.create_index(op.f('ix_llm_requests_model'), 'llm_requests', ['model'], unique=False)
    op.drop_column('llm_requests', 'model_id')

    op.drop_index('ix_models_provider', table_name='llm_models')
    op.drop_index('ix_models_active', table_name='llm_models')
    op.drop_table('llm_models')

    op.create_table('models',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('provider_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('display_name', sa.VARCHAR(length=150), autoincrement=False, nullable=False),
    sa.Column('context_window', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('max_output_tokens', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], name=op.f('models_provider_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('models_pkey')),
    sa.UniqueConstraint('name', name=op.f('models_name_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('ix_models_provider'), 'models', ['provider_id'], unique=False)
    op.create_index(op.f('ix_models_active'), 'models', ['is_active'], unique=False)
