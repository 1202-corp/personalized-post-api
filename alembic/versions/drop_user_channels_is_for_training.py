"""drop user_channels is_for_training

Revision ID: drop_uc_is_for_training
Revises: drop_initial_best
Create Date: 2026-01-29 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'drop_uc_is_for_training'
down_revision = 'drop_initial_best'
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
    if _column_exists(conn, 'user_channels', 'is_for_training'):
        op.drop_column('user_channels', 'is_for_training')


def downgrade() -> None:
    op.add_column('user_channels', sa.Column('is_for_training', sa.Boolean(), nullable=False, server_default=sa.false()))
