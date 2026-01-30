"""add channel_id to taste_clusters; user_channel_preference_vectors; user_channel_tastes

Revision ID: per_channel_taste
Revises: add_user_preference_vectors_table
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'per_channel_taste'
down_revision = 'drop_initial_best'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'taste_clusters',
        sa.Column('channel_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_taste_clusters_channel_id_channels',
        'taste_clusters',
        'channels',
        ['channel_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_taste_clusters_channel_id', 'taste_clusters', ['channel_id'], unique=False)

    op.create_table(
        'user_channel_preference_vectors',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('preference_vector', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id', 'channel_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
    )
    op.create_index(
        'ix_user_channel_preference_vectors_channel_id',
        'user_channel_preference_vectors',
        ['channel_id'],
        unique=False,
    )

    op.create_table(
        'user_channel_tastes',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('taste_cluster_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'channel_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['taste_cluster_id'], ['taste_clusters.id'], ondelete='CASCADE'),
    )
    op.create_index(
        'ix_user_channel_tastes_channel_id',
        'user_channel_tastes',
        ['channel_id'],
        unique=False,
    )
    op.create_index(
        'ix_user_channel_tastes_taste_cluster_id',
        'user_channel_tastes',
        ['taste_cluster_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table('user_channel_tastes')
    op.drop_table('user_channel_preference_vectors')
    op.drop_index('ix_taste_clusters_channel_id', table_name='taste_clusters')
    op.drop_constraint('fk_taste_clusters_channel_id_channels', 'taste_clusters', type_='foreignkey')
    op.drop_column('taste_clusters', 'channel_id')
