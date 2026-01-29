"""add channel avatar and user_channel mailing_enabled

Revision ID: add_avatar_mailing
Revises: remove_text_from_posts
Create Date: 2026-01-29 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_avatar_mailing'
down_revision = 'remove_text_from_posts'
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
    if not _column_exists(conn, 'channels', 'avatar_telegram_file_id'):
        op.add_column('channels', sa.Column('avatar_telegram_file_id', sa.String(255), nullable=True))
    if not _column_exists(conn, 'user_channels', 'mailing_enabled'):
        op.add_column('user_channels', sa.Column('mailing_enabled', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, 'user_channels', 'mailing_enabled'):
        op.drop_column('user_channels', 'mailing_enabled')
    if _column_exists(conn, 'channels', 'avatar_telegram_file_id'):
        op.drop_column('channels', 'avatar_telegram_file_id')
