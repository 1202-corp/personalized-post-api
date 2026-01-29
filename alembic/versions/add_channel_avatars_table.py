"""add channel_avatars table and move avatar columns from channels

Revision ID: add_channel_avatars
Revises: drop_channels_is_active
Create Date: 2026-01-29 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_channel_avatars'
down_revision = 'drop_channels_is_active'
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
    ), {"t": table, "c": column})
    return result.scalar() is not None


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    ), {"t": table})
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # Create channel_avatars table
    op.create_table(
        'channel_avatars',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('avatar_telegram_file_id', sa.String(255), nullable=True),
        sa.Column('avatar_photo_bytes', sa.LargeBinary(), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id', name='uq_channel_avatars_channel_id'),
    )
    op.create_index('ix_channel_avatars_channel_id', 'channel_avatars', ['channel_id'], unique=True)

    # Migrate data from channels to channel_avatars
    if _column_exists(conn, 'channels', 'avatar_telegram_file_id') or _column_exists(conn, 'channels', 'avatar_photo_bytes'):
        op.execute(sa.text("""
            INSERT INTO channel_avatars (channel_id, avatar_telegram_file_id, avatar_photo_bytes)
            SELECT id, avatar_telegram_file_id, avatar_photo_bytes
            FROM channels
            WHERE avatar_telegram_file_id IS NOT NULL OR avatar_photo_bytes IS NOT NULL
        """))

    # Drop columns from channels
    if _column_exists(conn, 'channels', 'avatar_telegram_file_id'):
        op.drop_column('channels', 'avatar_telegram_file_id')
    if _column_exists(conn, 'channels', 'avatar_photo_bytes'):
        op.drop_column('channels', 'avatar_photo_bytes')


def downgrade() -> None:
    conn = op.get_bind()

    # Add columns back to channels
    op.add_column('channels', sa.Column('avatar_telegram_file_id', sa.String(255), nullable=True))
    op.add_column('channels', sa.Column('avatar_photo_bytes', sa.LargeBinary(), nullable=True))

    # Copy data back from channel_avatars
    if _table_exists(conn, 'channel_avatars'):
        op.execute(sa.text("""
            UPDATE channels c
            SET avatar_telegram_file_id = a.avatar_telegram_file_id,
                avatar_photo_bytes = a.avatar_photo_bytes
            FROM channel_avatars a
            WHERE a.channel_id = c.id
        """))

    op.drop_index('ix_channel_avatars_channel_id', table_name='channel_avatars')
    op.drop_table('channel_avatars')
