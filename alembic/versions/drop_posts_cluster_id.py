"""drop posts.cluster_id (post-clusters removed, only taste clusters used)

Revision ID: drop_posts_cluster_id
Revises: add_taste_clusters
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa


revision = 'drop_posts_cluster_id'
down_revision = 'add_taste_clusters'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'posts' AND column_name = 'cluster_id'"
    ))
    if result.scalar() is not None:
        op.drop_index('ix_posts_cluster_id', table_name='posts', if_exists=True)
        op.drop_index('idx_post_cluster_id', table_name='posts', if_exists=True)
        op.drop_column('posts', 'cluster_id')


def downgrade() -> None:
    op.add_column(
        'posts',
        sa.Column('cluster_id', sa.Integer(), nullable=True),
    )
    op.create_index('ix_posts_cluster_id', 'posts', ['cluster_id'], unique=False)
    op.create_index('idx_post_cluster_id', 'posts', ['cluster_id'], unique=False)
