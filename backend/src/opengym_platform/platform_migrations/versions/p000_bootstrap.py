"""Platform privilege baseline; business DDL belongs to its consuming slice."""

from alembic import op

revision = "p000_bootstrap"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    op.execute("REVOKE ALL ON SCHEMA public FROM opengym_api_runtime")
    op.execute("GRANT USAGE ON SCHEMA public TO opengym_api_runtime")
    op.execute("GRANT SELECT ON TABLE public.alembic_version TO opengym_api_runtime")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE opengym_schema_owner "
        "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
    )


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
