"""Confirm only an existing media owner for internal collection, under its lock."""

from alembic import op

revision = "p002_media_gc"
down_revision = "p001_links"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        """CREATE FUNCTION identity.lock_media_owner(owner text) RETURNS TABLE(id text)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            SELECT u.id FROM identity.users u WHERE u.id=$1 FOR UPDATE
        $$""",
        "REVOKE ALL ON FUNCTION identity.lock_media_owner(text) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.lock_media_owner(text) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
        "ALTER FUNCTION identity.lock_media_owner(text) OWNER TO opengym_identity_executor",
        "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
