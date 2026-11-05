"""Bounded preauthentication and atomic single-use password reset."""

from alembic import op

revision = "p001_reset"
down_revision = "p001_passkey_manage"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "CREATE POLICY identity_reset ON identity.password_resets TO opengym_identity_executor USING (true) WITH CHECK (true)",
        "CREATE POLICY identity_link ON identity.device_links TO opengym_identity_executor USING (true) WITH CHECK (true)",
        "GRANT SELECT, DELETE ON identity.password_resets TO opengym_identity_executor",
        "GRANT SELECT(owner_id), DELETE ON identity.device_links TO opengym_identity_executor",
        "GRANT UPDATE(scrypt_hash,set_at) ON identity.password_credentials TO opengym_identity_executor",
        "CREATE INDEX password_resets_digest ON identity.password_resets(code_digest)",
        """CREATE FUNCTION identity.lookup_reset(code_digest bytea)
        RETURNS TABLE(owner_id text, display_name text, email text, session_version bigint, disabled boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            SELECT u.id, u.display_name, a.alias_key, u.session_version, u.disabled
            FROM identity.password_resets r JOIN identity.users u ON u.id=r.owner_id
            LEFT JOIN identity.login_aliases a ON a.owner_id=u.id AND a.email_claim
            WHERE octet_length($1)=32 AND r.code_digest=$1 AND r.expires_at > clock_timestamp()
        $$""",
        """CREATE FUNCTION identity.finish_reset(owner text, digest bytea, new_hash text)
        RETURNS TABLE(result text, id text, display_name text, is_admin boolean, session_version bigint)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE actor identity.users%ROWTYPE; alias text;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            SELECT u.* INTO actor FROM identity.users u WHERE u.id=owner FOR UPDATE;
            IF NOT FOUND OR octet_length(digest) IS DISTINCT FROM 32
                OR actor.session_version::text IS DISTINCT FROM current_setting('app.reset_sv',true)
                OR actor.display_name IS DISTINCT FROM current_setting('app.reset_name',true)
                OR NOT EXISTS (SELECT 1 FROM identity.password_resets r WHERE r.owner_id=owner
                    AND r.code_digest=digest AND r.expires_at > clock_timestamp())
            THEN RETURN; END IF;
            IF actor.disabled THEN
                RETURN QUERY SELECT 'disabled'::text, NULL::text, NULL::text, NULL::boolean, NULL::bigint;
                RETURN;
            END IF;
            alias := nullif(current_setting('app.reset_alias',true),'');
            IF alias IS NULL OR new_hash IS NULL THEN RAISE EXCEPTION 'reset context missing'; END IF;
            IF current_setting('app.reset_identifier',true) IS DISTINCT FROM alias
                AND NOT EXISTS (SELECT 1 FROM identity.login_aliases a WHERE a.owner_id=owner
                    AND a.email_claim AND a.alias_key=current_setting('app.reset_identifier',true))
            THEN RETURN; END IF;
            IF EXISTS (SELECT 1 FROM identity.login_aliases a WHERE a.alias_key=alias AND a.owner_id<>owner
                AND (a.email_claim OR a.password_name_claim OR a.reset_name_until > clock_timestamp())) THEN
                RETURN QUERY SELECT 'name-taken'::text, NULL::text, NULL::text, NULL::boolean, NULL::bigint;
                RETURN;
            END IF;
            DELETE FROM identity.login_aliases a WHERE a.alias_key=alias AND a.owner_id<>owner
                AND NOT a.email_claim AND NOT a.password_name_claim AND a.reset_name_until<=clock_timestamp();
            DELETE FROM identity.login_aliases a WHERE a.owner_id=owner AND a.alias_key<>alias
                AND NOT a.email_claim;
            UPDATE identity.login_aliases a SET password_name_claim=false,reset_name_until=NULL
                WHERE a.owner_id=owner AND a.alias_key<>alias;
            INSERT INTO identity.login_aliases VALUES (alias,owner,false,true,NULL)
                ON CONFLICT(alias_key) DO UPDATE SET password_name_claim=true,reset_name_until=NULL;
            INSERT INTO identity.password_credentials VALUES (owner,new_hash,clock_timestamp())
                ON CONFLICT(owner_id) DO UPDATE SET scrypt_hash=EXCLUDED.scrypt_hash,set_at=EXCLUDED.set_at;
            DELETE FROM identity.password_resets r WHERE r.owner_id=owner;
            DELETE FROM identity.device_links l WHERE l.owner_id=owner;
            UPDATE identity.users u SET session_version=u.session_version+1 WHERE u.id=owner
                RETURNING u.* INTO actor;
            RETURN QUERY SELECT 'reset'::text, actor.id, actor.display_name, actor.is_admin, actor.session_version;
        END $$""",
        "REVOKE ALL ON FUNCTION identity.lookup_reset(bytea), identity.finish_reset(text,bytea,text) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.lookup_reset(bytea), identity.finish_reset(text,bytea,text) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
        "ALTER FUNCTION identity.lookup_reset(bytea) OWNER TO opengym_identity_executor",
        "ALTER FUNCTION identity.finish_reset(text,bytea,text) OWNER TO opengym_identity_executor",
        "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
