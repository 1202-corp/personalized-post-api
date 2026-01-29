"""drop user_logs table

Revision ID: drop_user_logs
Revises: drop_users_redundant
Create Date: 2026-01-29 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'drop_user_logs'
down_revision = 'drop_users_redundant'
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    ), {"t": table})
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'user_logs'):
        op.drop_table('user_logs')


def downgrade() -> None:
    op.create_table(
        'user_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_log_user_action', 'user_logs', ['user_id', 'action'])
    op.create_index('idx_log_created', 'user_logs', ['created_at'])
