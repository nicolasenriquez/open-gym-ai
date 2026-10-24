"""Allow the restricted runtime to read only migration metadata for readiness."""

from alembic import op

revision = "0002_health_readiness"
down_revision = "0001_infrastructure"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("GRANT USAGE ON SCHEMA public TO python_foundation_runtime")
    op.execute(
        "GRANT SELECT ON TABLE public.alembic_version TO python_foundation_runtime"
    )


def downgrade():
    raise RuntimeError("FOUNDATION_MIGRATION_FORWARD_ONLY")
