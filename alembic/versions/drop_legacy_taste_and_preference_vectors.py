"""drop users.taste_cluster_id and user_preference_vectors (legacy; per-channel only)

Revision ID: drop_legacy_taste
Revises: add_posts_expires_at
Create Date: 2026-01-29

"""
from alembic import op


revision = 'drop_legacy_taste'
down_revision = 'add_posts_expires_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop legacy global taste cluster link from users
    op.drop_constraint(
        'fk_users_taste_cluster_id_taste_clusters',
        'users',
        type_='foreignkey',
    )
    op.drop_index('ix_users_taste_cluster_id', table_name='users')
    op.drop_column('users', 'taste_cluster_id')

    # Drop legacy global preference vectors table
    op.drop_table('user_preference_vectors')


def downgrade() -> None:
    import sqlalchemy as sa

    op.create_table(
        'user_preference_vectors',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('preference_vector', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
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
