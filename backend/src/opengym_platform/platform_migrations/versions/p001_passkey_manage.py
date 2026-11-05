"""Own passkey management under the existing forced owner policy."""

from alembic import op

revision = "p001_passkey_manage"
down_revision = "p001_account"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("GRANT INSERT, DELETE ON identity.passkeys TO opengym_api_runtime")
    op.execute("GRANT UPDATE(label) ON identity.passkeys TO opengym_api_runtime")


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
