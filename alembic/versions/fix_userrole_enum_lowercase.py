"""fix userrole enum to use lowercase values

If the DB enum was created with uppercase (e.g. ADMIN, MEMBER, GUEST),
PostgreSQL rejects the API value "admin". This migration ensures the
enum has lowercase values to match app.models.user.UserRole.

Revision ID: fix_userrole_enum
Revises: merge_heads
Create Date: 2026-01-30

"""
from alembic import op


revision = 'fix_userrole_enum'
down_revision = 'merge_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create new enum with lowercase values (idempotent if migration was partially applied)
    op.execute(
        "DO $$ BEGIN CREATE TYPE userrole_new AS ENUM ('guest', 'member', 'admin'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )
    # Drop default so type change can run (default is of old type)
    op.execute("ALTER TABLE users ALTER COLUMN user_role DROP DEFAULT;")
    # Migrate column: cast current value to text, lower it, cast to new type
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN user_role TYPE userrole_new
        USING (lower(user_role::text)::userrole_new);
    """)
    op.execute("ALTER TABLE users ALTER COLUMN user_role SET DEFAULT 'guest'::userrole_new;")
    op.execute("DROP TYPE userrole;")
    op.execute("ALTER TYPE userrole_new RENAME TO userrole;")


def downgrade() -> None:
    # Recreate original enum (lowercase; downgrade doesn't restore uppercase)
    op.execute("CREATE TYPE userrole_old AS ENUM ('guest', 'member', 'admin');")
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN user_role TYPE userrole_old
        USING (user_role::text::userrole_old);
    """)
    op.execute("DROP TYPE userrole;")
    op.execute("ALTER TYPE userrole_old RENAME TO userrole;")
