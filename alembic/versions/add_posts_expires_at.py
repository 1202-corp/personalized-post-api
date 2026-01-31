"""add posts.expires_at for realtime post TTL (10 min)

Revision ID: add_posts_expires_at
Revises: merge_per_channel_fix
Create Date: 2026-01-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_posts_expires_at'
down_revision = 'merge_per_channel_fix'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'posts',
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_post_expires_at', 'posts', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_post_expires_at', table_name='posts')
    op.drop_column('posts', 'expires_at')
