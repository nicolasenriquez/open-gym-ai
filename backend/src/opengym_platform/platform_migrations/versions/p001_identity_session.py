"""Identity's first consumer: serialized session authorization, no credentials yet."""

from alembic import op

revision = "p001_identity_session"
down_revision = "p000_bootstrap"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "CREATE SCHEMA identity AUTHORIZATION opengym_schema_owner",
        "REVOKE ALL ON SCHEMA identity FROM PUBLIC",
        "GRANT USAGE ON SCHEMA identity TO opengym_api_runtime, opengym_identity_executor",
        """CREATE TABLE identity.invitations (
            code text PRIMARY KEY, note text NOT NULL, created_by text NOT NULL,
            created_at timestamptz(3), consumed boolean NOT NULL,
            used_by text, used_at timestamptz(3), revoked boolean NOT NULL
        )""",
        """CREATE TABLE identity.users (
            id text PRIMARY KEY, display_name text NOT NULL,
            created_at timestamptz(3), is_admin boolean NOT NULL DEFAULT false,
            disabled boolean NOT NULL DEFAULT false,
            session_version bigint NOT NULL DEFAULT 0 CHECK (session_version >= 0),
            last_pull_at timestamptz(3),
            invited_by text REFERENCES identity.invitations(code) ON DELETE RESTRICT
        )""",
        "CREATE INDEX users_invited_by ON identity.users(invited_by) WHERE invited_by IS NOT NULL",
        "ALTER TABLE identity.users ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE identity.users FORCE ROW LEVEL SECURITY",
        "ALTER TABLE identity.invitations ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE identity.invitations FORCE ROW LEVEL SECURITY",
        """CREATE POLICY runtime_owner ON identity.users TO opengym_api_runtime
            USING (id = nullif(current_setting('app.owner_id', true), ''))
            WITH CHECK (id = nullif(current_setting('app.owner_id', true), ''))""",
        """CREATE POLICY identity_actor ON identity.users TO opengym_identity_executor
            USING (true) WITH CHECK (true)""",
        "GRANT SELECT (id, display_name, is_admin) ON identity.users TO opengym_api_runtime",
        "GRANT SELECT, UPDATE ON identity.users TO opengym_identity_executor",
        """CREATE FUNCTION identity.lock_actor(owner text, expected_sv bigint, expires_at timestamptz)
        RETURNS TABLE(id text, is_admin boolean, session_version bigint)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE actor identity.users%ROWTYPE;
        BEGIN
            SELECT u.* INTO actor FROM identity.users u WHERE u.id = owner FOR UPDATE;
            IF NOT FOUND OR actor.disabled OR expected_sv IS NULL OR expires_at IS NULL
                OR actor.session_version <> expected_sv OR expires_at <= clock_timestamp()
            THEN RETURN; END IF;
            RETURN QUERY SELECT actor.id, actor.is_admin, actor.session_version;
        END $$""",
        # Health needs only cardinality, not global runtime SELECT on users.
        """CREATE FUNCTION identity.public_user_count() RETURNS bigint
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
            AS $$ SELECT count(*) FROM identity.users $$""",
        "REVOKE ALL ON FUNCTION identity.lock_actor(text,bigint,timestamptz) FROM PUBLIC",
        "REVOKE ALL ON FUNCTION identity.public_user_count() FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.lock_actor(text,bigint,timestamptz) TO opengym_api_runtime",
        "GRANT EXECUTE ON FUNCTION identity.public_user_count() TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
        "ALTER FUNCTION identity.lock_actor(text,bigint,timestamptz) OWNER TO opengym_identity_executor",
        "ALTER FUNCTION identity.public_user_count() OWNER TO opengym_identity_executor",
        "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
