"""Owner-created device links and bounded preauthentication redemption."""

from alembic import op

revision = "p001_links"
down_revision = "p001_reset"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "GRANT SELECT, INSERT, UPDATE(code_digest,created_at,expires_at) ON identity.device_links TO opengym_api_runtime",
        "GRANT SELECT ON identity.device_links TO opengym_identity_executor",
        """CREATE FUNCTION identity.lookup_device_link(code_digest bytea)
        RETURNS TABLE(owner_id text, display_name text, session_version bigint, passkeys jsonb)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            SELECT u.id,u.display_name,u.session_version,
                (SELECT coalesce(jsonb_agg(jsonb_build_object('credential_id',p.credential_id,'transports',p.transports)),'[]'::jsonb)
                 FROM identity.passkeys p WHERE p.owner_id=u.id)
            FROM identity.device_links l JOIN identity.users u ON u.id=l.owner_id
            WHERE octet_length($1)=32 AND l.code_digest=$1
                AND l.expires_at > clock_timestamp() AND NOT u.disabled
        $$""",
        """CREATE FUNCTION identity.finish_device_link(owner text, digest bytea,
            credential_id text, public_key bytea, counter bigint, transports text[], label text)
        RETURNS TABLE(result text, id text, name text, admin boolean, session_version bigint)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE actor identity.users%ROWTYPE; inserted text; at timestamptz;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            SELECT u.* INTO actor FROM identity.users u WHERE u.id=owner FOR UPDATE;
            IF NOT FOUND OR actor.disabled OR octet_length(digest) IS DISTINCT FROM 32
                OR actor.session_version::text IS DISTINCT FROM current_setting('app.link_sv',true)
                OR NOT EXISTS (SELECT 1 FROM identity.device_links l WHERE l.owner_id=owner
                    AND l.code_digest=digest AND l.expires_at > clock_timestamp())
            THEN RETURN; END IF;
            IF EXISTS (SELECT 1 FROM identity.passkeys p WHERE p.credential_id=$3) THEN
                RETURN QUERY SELECT 'credential-exists'::text,NULL::text,NULL::text,NULL::boolean,NULL::bigint;
                RETURN;
            END IF;
            IF (SELECT count(*) FROM identity.passkeys p WHERE p.owner_id=owner)>=20 THEN
                RETURN QUERY SELECT 'passkey-limit'::text,NULL::text,NULL::text,NULL::boolean,NULL::bigint;
                RETURN;
            END IF;
            at := clock_timestamp();
            INSERT INTO identity.passkeys(credential_id,owner_id,public_key,counter,transports,label,created_at,last_used_at)
                VALUES ($3,owner,$4,$5,$6,$7,at,at)
                ON CONFLICT ON CONSTRAINT passkeys_pkey DO NOTHING RETURNING identity.passkeys.credential_id INTO inserted;
            IF inserted IS NULL THEN
                RETURN QUERY SELECT 'credential-exists'::text,NULL::text,NULL::text,NULL::boolean,NULL::bigint;
                RETURN;
            END IF;
            DELETE FROM identity.device_links l WHERE l.owner_id=owner AND l.code_digest=digest;
            RETURN QUERY SELECT 'linked'::text,actor.id,actor.display_name,actor.is_admin,actor.session_version;
        END $$""",
        "REVOKE ALL ON FUNCTION identity.lookup_device_link(bytea), identity.finish_device_link(text,bytea,text,bytea,bigint,text[],text) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION identity.lookup_device_link(bytea), identity.finish_device_link(text,bytea,text,bytea,bigint,text[],text) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA identity TO opengym_identity_executor",
        "ALTER FUNCTION identity.lookup_device_link(bytea) OWNER TO opengym_identity_executor",
        "ALTER FUNCTION identity.finish_device_link(text,bytea,text,bytea,bigint,text[],text) OWNER TO opengym_identity_executor",
        "REVOKE CREATE ON SCHEMA identity FROM opengym_identity_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
