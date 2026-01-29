"""add channel description

Revision ID: add_channel_description
Revises: add_avatar_photo_bytes
Create Date: 2026-01-29 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_channel_description'
down_revision = 'add_avatar_photo_bytes'
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
    if not _column_exists(conn, 'channels', 'description'):
        op.add_column('channels', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, 'channels', 'description'):
        op.drop_column('channels', 'description')
