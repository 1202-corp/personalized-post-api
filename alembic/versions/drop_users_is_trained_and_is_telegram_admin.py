"""drop users is_trained and is_telegram_admin

Revision ID: drop_users_redundant
Revises: add_channel_description
Create Date: 2026-01-29 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'drop_users_redundant'
down_revision = 'add_channel_description'
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
    if _column_exists(conn, 'users', 'is_trained'):
        op.drop_column('users', 'is_trained')
    if _column_exists(conn, 'users', 'is_telegram_admin'):
        op.drop_column('users', 'is_telegram_admin')


def downgrade() -> None:
    op.add_column('users', sa.Column('is_trained', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('is_telegram_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
