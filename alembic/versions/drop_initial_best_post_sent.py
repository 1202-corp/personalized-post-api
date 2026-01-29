"""drop users initial_best_post_sent

Revision ID: drop_initial_best
Revises: add_user_pref_vectors
Create Date: 2026-01-29 22:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'drop_initial_best'
down_revision = 'add_user_pref_vectors'
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
    if _column_exists(conn, 'users', 'initial_best_post_sent'):
        op.drop_column('users', 'initial_best_post_sent')


def downgrade() -> None:
    op.add_column('users', sa.Column('initial_best_post_sent', sa.Boolean(), nullable=False, server_default=sa.false()))
