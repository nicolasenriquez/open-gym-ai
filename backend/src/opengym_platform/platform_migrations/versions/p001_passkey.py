"""WebAuthn credentials and bounded preauthentication operations."""

from alembic import op

revision = "p001_passkey"
down_revision = "p001_password_register"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE identity.passkeys (
            credential_id text PRIMARY KEY, owner_id text NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
            public_key bytea NOT NULL, counter bigint NOT NULL CHECK (counter BETWEEN 0 AND 4294967295),
            transports text[] NOT NULL, label text, created_at timestamptz(3), last_used_at timestamptz(3)
        )""",
        "CREATE INDEX passkeys_owner ON identity.passkeys(owner_id)",
        "ALTER TABLE identity.passkeys ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE identity.passkeys FORCE ROW LEVEL SECURITY",
        """CREATE POLICY runtime_owner ON identity.passkeys TO opengym_api_runtime
            USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
            WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''))""",
        """CREATE POLICY identity_passkey ON identity.passkeys TO opengym_identity_executor
            USING (true) WITH CHECK (true)""",
        "GRANT SELECT, INSERT ON identity.passkeys TO opengym_identity_executor",
        "GRANT UPDATE(counter, last_used_at) ON identity.passkeys TO opengym_identity_executor",
        """CREATE FUNCTION identity.register_passkey(owner text, display_name text, invite_code text,
            credential_id text, public_key bytea, counter bigint, transports text[], created_at timestamptz)
        RETURNS TABLE(result text, id text, name text, admin boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE make_admin boolean; invite_only boolean;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            invite_only := current_setting('app.invite_only', true) = 'true';
            IF invite_only IS NULL THEN RAISE EXCEPTION 'registration config missing'; END IF;
            IF $4 IS NOT NULL AND EXISTS (SELECT 1 FROM identity.passkeys p WHERE p.credential_id = $4) THEN
                RETURN QUERY SELECT 'credential-exists'::text, NULL::text, NULL::text, NULL::boolean;
                RETURN;
            END IF;
            IF invite_only AND NOT EXISTS (SELECT 1 FROM identity.invitations i
                WHERE i.code = invite_code AND NOT i.consumed AND NOT i.revoked) THEN
                RETURN QUERY SELECT 'invite'::text, NULL::text, NULL::text, NULL::boolean;
                RETURN;
            END IF;
            -- Options validate only the invitation and never reserve a persistent identity.
            IF $5 IS NULL THEN
                RETURN QUERY SELECT 'available'::text, NULL::text, NULL::text, NULL::boolean;
                RETURN;
            END IF;
            make_admin := (current_setting('app.first_user_admin', true) = 'true'
                AND NOT EXISTS (SELECT 1 FROM identity.users))
                OR owner = ANY(string_to_array(current_setting('app.admin_uids', true), ','));
            INSERT INTO identity.users(id, display_name, created_at, is_admin, invited_by)
                VALUES (owner, display_name, $8, coalesce(make_admin, false),
                    CASE WHEN invite_only THEN invite_code END);
            INSERT INTO identity.passkeys(credential_id, owner_id, public_key, counter, transports, created_at, last_used_at)
                VALUES ($4, owner, $5, $6, $7, $8, $8);
            IF invite_only THEN
                UPDATE identity.invitations SET consumed = true, used_by = owner, used_at = $8 WHERE code = invite_code;
            END IF;
            RETURN QUERY SELECT 'registered'::text, owner, display_name, coalesce(make_admin, false);
        END $$""",
        """CREATE FUNCTION identity.lookup_passkey(credential_id text)
        RETURNS TABLE(owner_id text, public_key bytea, counter bigint, transports text[], disabled boolean, session_version bigint)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            SELECT p.owner_id, p.public_key, p.counter, p.transports, u.disabled, u.session_version
            FROM identity.passkeys p JOIN identity.users u ON u.id = p.owner_id WHERE p.credential_id = $1
        $$""",
        """CREATE FUNCTION identity.finish_passkey_login(credential_id text, observed_key bytea,
            observed_counter bigint, new_counter bigint, observed_sv bigint)
        RETURNS TABLE(id text, display_name text, is_admin boolean, disabled boolean, session_version bigint)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE owner text; actor identity.users%ROWTYPE;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            SELECT p.owner_id INTO owner FROM identity.passkeys p WHERE p.credential_id = $1;
            IF NOT FOUND THEN RETURN; END IF;
            SELECT u.* INTO actor FROM identity.users u WHERE u.id = owner FOR UPDATE;
            IF NOT FOUND OR actor.session_version IS DISTINCT FROM observed_sv THEN RETURN; END IF;
            UPDATE identity.passkeys p SET counter = new_counter, last_used_at = clock_timestamp()
                WHERE p.credential_id = $1 AND p.owner_id = owner AND p.public_key = observed_key
                    AND p.counter = observed_counter;
            IF NOT FOUND THEN RETURN; END IF;
            RETURN QUERY SELECT actor.id, actor.display_name, actor.is_admin, actor.disabled, actor.session_version;
        END $$""",
    ]
    for name, signature in (
        ("register_passkey", "text,text,text,text,bytea,bigint,text[],timestamptz"),
        ("lookup_passkey", "text"),
        ("finish_passkey_login", "text,bytea,bigint,bigint,bigint"),
    ):
        function = f"identity.{name}({signature})"
        statements += [
            f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION {function} TO opengym_api_runtime",
            "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
            f"ALTER FUNCTION {function} OWNER TO opengym_identity_executor",
            "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
        ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
