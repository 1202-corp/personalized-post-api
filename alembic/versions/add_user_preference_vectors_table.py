"""add user_preference_vectors table and move data from users

Revision ID: add_user_pref_vectors
Revises: drop_user_logs
Create Date: 2026-01-29 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = 'add_user_pref_vectors'
down_revision = 'drop_user_logs'
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
    if not _table_exists(conn, 'user_preference_vectors'):
        op.create_table(
            'user_preference_vectors',
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('preference_vector', JSON, nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        )
    # Migrate data from users (only when source columns still exist)
    if _column_exists(conn, 'users', 'preference_vector_cache') and _column_exists(conn, 'users', 'preference_vector_updated_at'):
        conn.execute(sa.text("""
            INSERT INTO user_preference_vectors (user_id, preference_vector, updated_at)
            SELECT id, preference_vector_cache, preference_vector_updated_at
            FROM users
            WHERE preference_vector_cache IS NOT NULL
            ON CONFLICT (user_id) DO UPDATE SET
                preference_vector = EXCLUDED.preference_vector,
                updated_at = EXCLUDED.updated_at
        """))
    if _column_exists(conn, 'users', 'preference_vector_cache'):
        op.drop_column('users', 'preference_vector_cache')
    if _column_exists(conn, 'users', 'preference_vector_updated_at'):
        op.drop_column('users', 'preference_vector_updated_at')


def downgrade() -> None:
    op.add_column('users', sa.Column('preference_vector_cache', JSON, nullable=True))
    op.add_column('users', sa.Column('preference_vector_updated_at', sa.DateTime(timezone=True), nullable=True))
    conn = op.get_bind()
    if _table_exists(conn, 'user_preference_vectors'):
        conn.execute(sa.text("""
            UPDATE users u SET
                preference_vector_cache = uv.preference_vector,
                preference_vector_updated_at = uv.updated_at
            FROM user_preference_vectors uv
            WHERE uv.user_id = u.id
        """))
    op.drop_table('user_preference_vectors')
