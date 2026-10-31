"""Administrative invitation history with current actor authority."""

from alembic import op

revision = "p004_admin_invites"
down_revision = "p004_external_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        "GRANT SELECT,INSERT,DELETE ON identity.invitations TO opengym_administration_executor",
        "CREATE POLICY admin_invitations ON identity.invitations TO opengym_administration_executor USING(true) WITH CHECK(true)",
        "GRANT SELECT(session_version),UPDATE(session_version) ON identity.users TO opengym_administration_executor",
        "GRANT DELETE ON identity.password_credentials TO opengym_administration_executor",
        "CREATE POLICY admin_password_delete ON identity.password_credentials FOR DELETE TO opengym_administration_executor USING(true)",
        "GRANT SELECT(password_name_claim,reset_name_until),INSERT,DELETE,UPDATE(password_name_claim,reset_name_until) ON identity.login_aliases TO opengym_administration_executor",
        "CREATE POLICY admin_alias_write ON identity.login_aliases TO opengym_administration_executor USING(true) WITH CHECK(true)",
        "GRANT SELECT(code_digest,issued_by),INSERT,UPDATE(code_digest,expires_at,issued_by) ON identity.password_resets TO opengym_administration_executor",
        "CREATE POLICY admin_reset_write ON identity.password_resets TO opengym_administration_executor USING(true) WITH CHECK(true)",
        """CREATE FUNCTION administration.list_invitations(actor text,sv bigint,exp timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb; result jsonb;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,actor);
            IF access IS NULL OR access='{}'::jsonb THEN RETURN access; END IF;
            SELECT coalesce(jsonb_agg(jsonb_build_object('code',i.code,'note',i.note,
                'createdBy',i.created_by,'created',CASE WHEN i.created_at IS NOT NULL THEN
                to_char(i.created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') END,
                'usedByName',CASE WHEN i.consumed THEN (SELECT u.display_name FROM identity.users u WHERE u.id=i.used_by) END)
                || CASE WHEN i.used_by IS NOT NULL THEN jsonb_build_object('usedBy',i.used_by) ELSE '{}'::jsonb END
                || CASE WHEN i.used_at IS NOT NULL THEN jsonb_build_object('usedAt',to_char(i.used_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')) ELSE '{}'::jsonb END
                || CASE WHEN i.revoked THEN '{"revoked": true}'::jsonb ELSE '{}'::jsonb END
                ORDER BY i.created_at NULLS FIRST,i.code COLLATE "C"),'[]'::jsonb) INTO result FROM identity.invitations i;
            IF exp<=clock_timestamp() THEN RETURN NULL; END IF;
            RETURN result;
        END $$""",
        """CREATE FUNCTION administration.create_invitation(actor text,sv bigint,exp timestamptz,code text,note text,created_at timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,actor);
            IF access IS NULL OR access='{}'::jsonb THEN RETURN access; END IF;
            IF code IS NULL OR note IS NULL OR created_at IS NULL THEN
                RAISE EXCEPTION 'INVITATION_INPUT_INVALID' USING ERRCODE='22023'; END IF;
            IF EXISTS(SELECT FROM identity.invitations i WHERE i.code=$4) THEN
                RETURN '{"collision": true}'::jsonb; END IF;
            created_at:=date_trunc('milliseconds',created_at);
            INSERT INTO identity.invitations VALUES(code,note,actor,created_at,false,NULL,NULL,false);
            RETURN jsonb_build_object('invite',jsonb_build_object('code',code,'note',note,'createdBy',actor,
                'created',to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')));
        END $$""",
        """CREATE FUNCTION administration.revoke_invitation(actor text,sv bigint,exp timestamptz,code text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb; invitation identity.invitations%ROWTYPE;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,actor);
            IF access IS NULL OR access='{}'::jsonb THEN RETURN access; END IF;
            SELECT i.* INTO invitation FROM identity.invitations i WHERE i.code=$4;
            IF NOT FOUND THEN RETURN '{"error":"no such code"}'::jsonb; END IF;
            IF invitation.consumed OR invitation.used_by IS NOT NULL THEN
                RETURN '{"error":"already used, cannot revoke"}'::jsonb; END IF;
            DELETE FROM identity.invitations i WHERE i.code=$4;
            RETURN '{"ok": true}'::jsonb;
        END $$""",
    ]
    statements.append("""CREATE FUNCTION administration.issue_reset(actor text,sv bigint,exp timestamptz,target text,digest bytea,expiry timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb; alias text;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,target);
            IF access IS NULL OR access='{}'::jsonb OR access ? 'error' THEN RETURN access; END IF;
            IF (access->>'admin')::boolean THEN
                RETURN '{"error":"an admin sets their own password in Settings"}'::jsonb; END IF;
            alias:=nullif(current_setting('app.admin_reset_alias',true),'');
            IF alias IS NULL OR access->>'name' IS DISTINCT FROM current_setting('app.admin_reset_name',true)
                OR octet_length(digest) IS DISTINCT FROM 32 OR expiry IS NULL OR expiry<=clock_timestamp()
            THEN RAISE EXCEPTION 'RESET_INPUT_INVALID' USING ERRCODE='22023'; END IF;
            IF EXISTS(SELECT FROM identity.login_aliases a WHERE a.alias_key=alias AND a.owner_id<>target
                AND (a.email_claim OR a.password_name_claim OR a.reset_name_until>clock_timestamp())) THEN
                RETURN '{"error":"another profile already signs in with this name","code":"name-taken"}'::jsonb; END IF;
            DELETE FROM identity.login_aliases a WHERE a.alias_key=alias AND a.owner_id<>target
                AND NOT a.email_claim AND NOT a.password_name_claim AND a.reset_name_until<=clock_timestamp();
            DELETE FROM identity.login_aliases a WHERE a.owner_id=target AND a.alias_key<>alias AND NOT a.email_claim;
            UPDATE identity.login_aliases a SET password_name_claim=false,reset_name_until=NULL
                WHERE a.owner_id=target AND a.alias_key<>alias;
            INSERT INTO identity.login_aliases VALUES(alias,target,false,false,expiry)
                ON CONFLICT(alias_key) DO UPDATE SET password_name_claim=false,reset_name_until=EXCLUDED.reset_name_until;
            DELETE FROM identity.password_credentials p WHERE p.owner_id=target;
            INSERT INTO identity.password_resets VALUES(target,digest,expiry,actor)
                ON CONFLICT(owner_id) DO UPDATE SET code_digest=EXCLUDED.code_digest,expires_at=EXCLUDED.expires_at,issued_by=EXCLUDED.issued_by;
            UPDATE identity.users u SET session_version=u.session_version+1 WHERE u.id=target;
            DELETE FROM identity.device_links l WHERE l.owner_id=target;
            RETURN jsonb_build_object('ok',true,'name',access->'name','expires',floor(extract(epoch FROM expiry)*1000));
        END $$""")
    for signature in (
        "administration.issue_reset(text,bigint,timestamptz,text,bytea,timestamptz)",
        "administration.list_invitations(text,bigint,timestamptz)",
        "administration.create_invitation(text,bigint,timestamptz,text,text,timestamptz)",
        "administration.revoke_invitation(text,bigint,timestamptz,text)",
    ):
        statements += [
            f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION {signature} TO opengym_api_runtime",
            "GRANT CREATE ON SCHEMA administration TO opengym_administration_executor",
            f"ALTER FUNCTION {signature} OWNER TO opengym_administration_executor",
            "REVOKE CREATE ON SCHEMA administration FROM opengym_administration_executor",
        ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
