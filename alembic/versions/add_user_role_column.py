"""add user_role column to users

Revision ID: add_user_role_column
Revises: remove_text_from_posts
Create Date: 2026-01-29 20:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_role_column'
down_revision = 'remove_text_from_posts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type using raw SQL for PostgreSQL (if not exists)
    op.execute("DO $$ BEGIN CREATE TYPE userrole AS ENUM ('guest', 'member', 'admin'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Add user_role column with default value (if not exists)
    op.execute("""
        DO $$ 
        BEGIN 
            ALTER TABLE users ADD COLUMN user_role userrole NOT NULL DEFAULT 'guest';
        EXCEPTION 
            WHEN duplicate_column THEN null;
        END $$;
    """)


def downgrade() -> None:
    op.drop_column('users', 'user_role')
    # Drop enum type
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
