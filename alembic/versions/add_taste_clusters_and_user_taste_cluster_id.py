"""add taste_clusters table and users.taste_cluster_id

Revision ID: add_taste_clusters
Revises: add_channel_avatars
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_taste_clusters'
down_revision = 'add_channel_avatars'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'taste_clusters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('centroid', sa.JSON(), nullable=True),
        sa.Column('user_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column(
        'users',
        sa.Column('taste_cluster_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_users_taste_cluster_id_taste_clusters',
        'users',
        'taste_clusters',
        ['taste_cluster_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_users_taste_cluster_id', 'users', ['taste_cluster_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_users_taste_cluster_id', table_name='users')
    op.drop_constraint('fk_users_taste_cluster_id_taste_clusters', 'users', type_='foreignkey')
    op.drop_column('users', 'taste_cluster_id')
    op.drop_table('taste_clusters')
