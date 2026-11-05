"""Atomic password registration and namespace claims, after the Training pilot."""

from alembic import op

revision = "p001_password_register"
down_revision = "p002_training_write"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "CREATE UNIQUE INDEX login_aliases_email ON identity.login_aliases(owner_id) WHERE email_claim",
        "CREATE UNIQUE INDEX login_aliases_name ON identity.login_aliases(owner_id) WHERE password_name_claim OR reset_name_until IS NOT NULL",
        """CREATE POLICY identity_invitation ON identity.invitations TO opengym_identity_executor
            USING (true) WITH CHECK (true)""",
        "GRANT INSERT ON identity.users, identity.password_credentials TO opengym_identity_executor",
        "GRANT INSERT, UPDATE, DELETE ON identity.login_aliases TO opengym_identity_executor",
        "GRANT SELECT, UPDATE ON identity.invitations TO opengym_identity_executor",
        """CREATE FUNCTION identity.register_password(
            owner text, display_name text, alias_key text, email_key text,
            scrypt_hash text, invite_code text, created_at timestamptz)
        RETURNS TABLE(result text, id text, name text, admin boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE make_admin boolean; invite_only boolean;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            invite_only := current_setting('app.invite_only', true) = 'true';
            IF invite_only IS NULL THEN RAISE EXCEPTION 'registration config missing'; END IF;
            IF invite_only AND NOT EXISTS (
                SELECT 1 FROM identity.invitations i
                WHERE i.code = invite_code AND NOT i.consumed AND NOT i.revoked
            ) THEN
                RETURN QUERY SELECT 'invite'::text, NULL::text, NULL::text, NULL::boolean;
                RETURN;
            END IF;
            IF EXISTS (SELECT 1 FROM identity.login_aliases a WHERE a.alias_key = $3
                AND (a.email_claim OR a.password_name_claim OR a.reset_name_until > clock_timestamp())) THEN
                RETURN QUERY SELECT 'name-taken'::text, NULL::text, NULL::text, NULL::boolean;
                RETURN;
            END IF;
            IF email_key IS NOT NULL AND EXISTS (
                SELECT 1 FROM identity.login_aliases a WHERE a.alias_key = email_key
                AND (a.email_claim OR a.password_name_claim OR a.reset_name_until > clock_timestamp())
            ) THEN
                RETURN QUERY SELECT 'email-taken'::text, NULL::text, NULL::text, NULL::boolean;
                RETURN;
            END IF;
            -- A null hash is the bounded pre-crypto check, with no persistent changes.
            IF scrypt_hash IS NULL THEN
                RETURN QUERY SELECT 'available'::text, NULL::text, NULL::text, NULL::boolean;
                RETURN;
            END IF;
            DELETE FROM identity.login_aliases a WHERE a.alias_key IN ($3, email_key)
                AND NOT a.email_claim AND NOT a.password_name_claim
                AND a.reset_name_until <= clock_timestamp();
            make_admin := (current_setting('app.first_user_admin', true) = 'true'
                AND NOT EXISTS (SELECT 1 FROM identity.users))
                OR owner = ANY(string_to_array(current_setting('app.admin_uids', true), ','));
            INSERT INTO identity.users(id, display_name, created_at, is_admin, invited_by)
                VALUES (owner, display_name, created_at, coalesce(make_admin, false),
                        CASE WHEN invite_only THEN invite_code END);
            INSERT INTO identity.password_credentials VALUES (owner, scrypt_hash, created_at);
            INSERT INTO identity.login_aliases VALUES ($3, owner, coalesce(email_key = $3, false), true, NULL);
            IF email_key IS NOT NULL AND email_key <> $3 THEN
                INSERT INTO identity.login_aliases VALUES (email_key, owner, true, false, NULL);
            END IF;
            IF invite_only THEN
                UPDATE identity.invitations SET consumed = true, used_by = owner, used_at = $7
                    WHERE code = invite_code;
            END IF;
            RETURN QUERY SELECT 'registered'::text, owner, display_name, coalesce(make_admin, false);
        END $$""",
        "REVOKE ALL ON FUNCTION identity.register_password(text,text,text,text,text,text,timestamptz) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.register_password(text,text,text,text,text,text,timestamptz) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
        "ALTER FUNCTION identity.register_password(text,text,text,text,text,text,timestamptz) OWNER TO opengym_identity_executor",
        "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
