"""Create infrastructure namespace, not business or test fixture tables."""

from alembic import op

revision = "0001_infrastructure"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA foundation")
    op.execute("REVOKE ALL ON SCHEMA foundation FROM PUBLIC")
    op.execute(
        "GRANT USAGE ON SCHEMA foundation TO python_foundation_runtime, python_foundation_training"
    )


def downgrade():
    raise RuntimeError("FOUNDATION_MIGRATION_FORWARD_ONLY")
