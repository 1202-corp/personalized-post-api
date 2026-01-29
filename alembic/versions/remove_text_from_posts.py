"""remove text column from posts

Revision ID: remove_text_from_posts
Revises:
Create Date: 2026-01-29 18:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'remove_text_from_posts'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Удаляем колонку text только если она есть (идемпотентно)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'posts' AND column_name = 'text'"
    ))
    if result.scalar() is not None:
        op.drop_column('posts', 'text')


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'posts' AND column_name = 'text'"
    ))
    if result.scalar() is None:
        op.add_column('posts', sa.Column('text', sa.Text(), nullable=True))
