"""remove text column from posts

Revision ID: remove_text_from_posts
Revises: 
Create Date: 2026-01-29 18:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_text_from_posts'
down_revision = None  # Update this with actual previous revision if needed
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove text column from posts table
    op.drop_column('posts', 'text')


def downgrade() -> None:
    # Add text column back (nullable)
    op.add_column('posts', sa.Column('text', sa.Text(), nullable=True))
