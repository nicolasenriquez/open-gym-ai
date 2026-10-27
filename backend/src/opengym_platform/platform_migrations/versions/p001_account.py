"""Own account access and bounded global alias availability."""

from alembic import op

revision = "p001_account"
down_revision = "p001_passkey"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        """CREATE POLICY runtime_owner ON identity.login_aliases TO opengym_api_runtime
            USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
            WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''))""",
        "GRANT SELECT ON identity.login_aliases, identity.passkeys TO opengym_api_runtime",
        """CREATE FUNCTION identity.alias_available(alias_key text) RETURNS boolean
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            SELECT nullif(current_setting('app.owner_id', true), '') IS NOT NULL
                AND $1 IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM identity.login_aliases a WHERE a.alias_key = $1
                    AND a.owner_id <> nullif(current_setting('app.owner_id', true), '')
                    AND (a.email_claim OR a.password_name_claim OR a.reset_name_until > clock_timestamp())
                )
        $$""",
        """CREATE FUNCTION identity.release_expired_alias(alias_key text) RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            DELETE FROM identity.login_aliases a WHERE a.alias_key = $1
                AND nullif(current_setting('app.owner_id', true), '') IS NOT NULL
                AND NOT a.email_claim AND NOT a.password_name_claim
                AND a.reset_name_until <= clock_timestamp()
        $$""",
        "REVOKE ALL ON FUNCTION identity.release_expired_alias(text) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.release_expired_alias(text) TO opengym_api_runtime",
        "GRANT INSERT, DELETE ON identity.password_credentials TO opengym_api_runtime",
        "GRANT UPDATE(set_at) ON identity.password_credentials TO opengym_api_runtime",
        "GRANT SELECT(session_version), UPDATE(session_version) ON identity.users TO opengym_api_runtime",
        "GRANT INSERT, DELETE ON identity.login_aliases TO opengym_api_runtime",
        "GRANT UPDATE(email_claim, password_name_claim, reset_name_until) ON identity.login_aliases TO opengym_api_runtime",
        """CREATE TABLE identity.password_resets (
            owner_id text PRIMARY KEY REFERENCES identity.users(id) ON DELETE CASCADE,
            code_digest bytea NOT NULL CHECK (octet_length(code_digest)=32),
            expires_at timestamptz(3) NOT NULL, issued_by text NOT NULL
        )""",
        """CREATE TABLE identity.device_links (
            code_digest bytea PRIMARY KEY CHECK (octet_length(code_digest)=32),
            owner_id text NOT NULL UNIQUE REFERENCES identity.users(id) ON DELETE CASCADE,
            created_at timestamptz(3) NOT NULL, expires_at timestamptz(3) NOT NULL
        )""",
        "ALTER TABLE identity.password_resets ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE identity.password_resets FORCE ROW LEVEL SECURITY",
        "ALTER TABLE identity.device_links ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE identity.device_links FORCE ROW LEVEL SECURITY",
        """CREATE POLICY runtime_owner ON identity.password_resets TO opengym_api_runtime
            USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
            WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''))""",
        """CREATE POLICY runtime_owner ON identity.device_links TO opengym_api_runtime
            USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
            WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''))""",
        "GRANT SELECT(owner_id), DELETE ON identity.password_resets, identity.device_links TO opengym_api_runtime",
        "REVOKE ALL ON FUNCTION identity.alias_available(text) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.alias_available(text) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
        "ALTER FUNCTION identity.alias_available(text) OWNER TO opengym_identity_executor",
        "ALTER FUNCTION identity.release_expired_alias(text) OWNER TO opengym_identity_executor",
        "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
