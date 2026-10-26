"""Forward-only Identity login increment; no registration/reset tables."""

from alembic import op

revision = "p001_password_login"
down_revision = "p001_identity_session"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        """CREATE TABLE identity.login_aliases (
            alias_key text COLLATE "C" PRIMARY KEY,
            owner_id text NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
            email_claim boolean NOT NULL, password_name_claim boolean NOT NULL,
            reset_name_until timestamptz(3),
            CHECK (email_claim OR password_name_claim OR reset_name_until IS NOT NULL)
        )""",
        "CREATE INDEX login_aliases_owner ON identity.login_aliases(owner_id)",
        """CREATE TABLE identity.password_credentials (
            owner_id text PRIMARY KEY REFERENCES identity.users(id) ON DELETE CASCADE,
            scrypt_hash text NOT NULL, set_at timestamptz(3)
        )""",
        "ALTER TABLE identity.login_aliases ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE identity.login_aliases FORCE ROW LEVEL SECURITY",
        "ALTER TABLE identity.password_credentials ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE identity.password_credentials FORCE ROW LEVEL SECURITY",
        """CREATE POLICY identity_alias ON identity.login_aliases TO opengym_identity_executor
            USING (true) WITH CHECK (true)""",
        """CREATE POLICY identity_password ON identity.password_credentials TO opengym_identity_executor
            USING (true) WITH CHECK (true)""",
        """CREATE POLICY runtime_owner ON identity.password_credentials TO opengym_api_runtime
            USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
            WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''))""",
        "GRANT SELECT ON identity.login_aliases, identity.password_credentials TO opengym_identity_executor",
        "GRANT SELECT ON identity.password_credentials TO opengym_api_runtime",
        "GRANT UPDATE (scrypt_hash) ON identity.password_credentials TO opengym_api_runtime",
        """CREATE FUNCTION identity.lookup_password(alias_key text)
        RETURNS TABLE(owner_id text, scrypt_hash text, disabled boolean, session_version bigint,
                      email_claim boolean, password_name_claim boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            SELECT u.id, p.scrypt_hash, u.disabled, u.session_version,
                   a.email_claim, a.password_name_claim
            FROM identity.login_aliases a
            JOIN identity.users u ON u.id = a.owner_id
            JOIN identity.password_credentials p ON p.owner_id = u.id
            WHERE a.alias_key = $1 AND (a.email_claim OR a.password_name_claim)
        $$""",
        """CREATE FUNCTION identity.finish_password_login(owner text, observed_hash text, observed_sv bigint)
        RETURNS TABLE(id text, display_name text, is_admin boolean, session_version bigint, disabled boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE actor identity.users%ROWTYPE;
        BEGIN
            SELECT u.* INTO actor FROM identity.users u WHERE u.id = owner FOR UPDATE;
            IF NOT FOUND OR actor.session_version IS DISTINCT FROM observed_sv
                OR NOT EXISTS (SELECT 1 FROM identity.password_credentials p
                               WHERE p.owner_id = owner AND p.scrypt_hash = observed_hash)
            THEN RETURN; END IF;
            RETURN QUERY SELECT actor.id, actor.display_name, actor.is_admin,
                                actor.session_version, actor.disabled;
        END $$""",
        "REVOKE ALL ON FUNCTION identity.lookup_password(text) FROM PUBLIC",
        "REVOKE ALL ON FUNCTION identity.finish_password_login(text,text,bigint) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.lookup_password(text) TO opengym_api_runtime",
        "GRANT EXECUTE ON FUNCTION identity.finish_password_login(text,text,bigint) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
        "ALTER FUNCTION identity.lookup_password(text) OWNER TO opengym_identity_executor",
        "ALTER FUNCTION identity.finish_password_login(text,text,bigint) OWNER TO opengym_identity_executor",
        "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
