"""drop channels is_active

Revision ID: drop_channels_is_active
Revises: drop_uc_is_for_training
Create Date: 2026-01-29 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'drop_channels_is_active'
down_revision = 'drop_uc_is_for_training'
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    ), {"t": table, "c": column})
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, 'channels', 'is_active'):
        op.drop_column('channels', 'is_active')


def downgrade() -> None:
    op.add_column('channels', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
