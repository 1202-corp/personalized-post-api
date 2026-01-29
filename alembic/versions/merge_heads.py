"""merge heads: drop_posts_cluster_id and add_user_role_column

Revision ID: merge_heads
Revises: drop_posts_cluster_id, add_user_role_column
Create Date: 2026-01-30

"""
from alembic import op


revision = 'merge_heads'
down_revision = ('drop_posts_cluster_id', 'add_user_role_column')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
