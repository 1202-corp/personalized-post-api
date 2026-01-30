"""merge per_channel_taste and fix_userrole_enum

Revision ID: merge_per_channel_fix
Revises: per_channel_taste, fix_userrole_enum
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op


revision = 'merge_per_channel_fix'
down_revision = ('per_channel_taste', 'fix_userrole_enum')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
