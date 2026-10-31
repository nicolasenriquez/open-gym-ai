"""Bounded actor-target administration and Training's existing admin views."""

from alembic import op

revision = "p004_admin_users"
down_revision = "p005_subscriptions"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        "CREATE SCHEMA administration AUTHORIZATION opengym_schema_owner",
        "REVOKE ALL ON SCHEMA administration FROM PUBLIC",
        "GRANT USAGE ON SCHEMA administration TO opengym_api_runtime,opengym_administration_executor",
        "GRANT USAGE ON SCHEMA identity,training,notifications TO opengym_administration_executor",
        "GRANT SELECT(id,display_name,created_at,is_admin,disabled,invited_by,last_pull_at),UPDATE(id,disabled) ON identity.users TO opengym_administration_executor",
        "GRANT SELECT(last_pull_at),UPDATE(last_pull_at) ON identity.users TO opengym_api_runtime",
        "CREATE POLICY admin_users ON identity.users TO opengym_administration_executor USING(true) WITH CHECK(true)",
        "GRANT SELECT(owner_id) ON identity.password_credentials TO opengym_administration_executor",
        "GRANT SELECT(owner_id,alias_key,email_claim) ON identity.login_aliases TO opengym_administration_executor",
        "GRANT SELECT(owner_id,expires_at) ON identity.password_resets TO opengym_administration_executor",
        "GRANT SELECT(owner_id),DELETE ON identity.device_links TO opengym_administration_executor",
        "GRANT SELECT(owner_id) ON notifications.subscriptions TO opengym_administration_executor",
        "GRANT SELECT ON training.documents TO opengym_administration_executor",
        "SET ROLE opengym_identity_executor",
        "GRANT EXECUTE ON FUNCTION identity.lock_actor(text,bigint,timestamptz) TO opengym_administration_executor",
        "SET ROLE opengym_schema_owner",
    ]
    for table in (
        "identity.password_credentials",
        "identity.login_aliases",
        "identity.password_resets",
        "identity.device_links",
        "notifications.subscriptions",
        "training.documents",
    ):
        statements.append(
            f"CREATE POLICY admin_projection ON {table} FOR SELECT TO opengym_administration_executor USING(true)"
        )
    statements.append(
        "CREATE POLICY admin_links_delete ON identity.device_links FOR DELETE TO opengym_administration_executor USING(true)"
    )
    statements += [
        """CREATE FUNCTION administration.inspect_user(actor text,sv bigint,exp timestamptz,target text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE authorized record; result jsonb;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            PERFORM u.id FROM identity.users u WHERE u.id IN (actor,target)
                ORDER BY u.id COLLATE "C" FOR UPDATE;
            SELECT * INTO authorized FROM identity.lock_actor(actor,sv,exp);
            IF NOT FOUND THEN RETURN NULL; END IF;
            IF NOT authorized.is_admin THEN RETURN '{}'::jsonb; END IF;
            SELECT jsonb_build_object('id',u.id,'name',u.display_name,
                'created',CASE WHEN u.created_at IS NOT NULL THEN to_char(u.created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') END,
                'disabled',u.disabled,'admin',u.is_admin,'invitedBy',u.invited_by,
                'password',EXISTS(SELECT FROM identity.password_credentials p WHERE p.owner_id=u.id),
                'email',(SELECT a.alias_key FROM identity.login_aliases a WHERE a.owner_id=u.id AND a.email_claim),
                'resetUntil',(SELECT floor(extract(epoch FROM r.expires_at)*1000) FROM identity.password_resets r
                    WHERE r.owner_id=u.id AND r.expires_at>clock_timestamp())) INTO result
                FROM identity.users u WHERE u.id=target;
            RETURN coalesce(result,'{"error":"no such user"}'::jsonb);
        END $$""",
        """CREATE FUNCTION administration.list_users(actor text,sv bigint,exp timestamptz,page_size integer,after_id text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb; result jsonb;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            -- Lock the small instance in one order, including across internal pages.
            PERFORM u.id FROM identity.users u ORDER BY u.id COLLATE "C" FOR UPDATE;
            access:=administration.inspect_user(actor,sv,exp,actor);
            IF access IS NULL OR access='{}'::jsonb THEN RETURN access; END IF;
            IF page_size IS NULL OR page_size<1 OR page_size>500 THEN
                RAISE EXCEPTION 'ADMIN_PAGE_INVALID' USING ERRCODE='22023'; END IF;
            SELECT coalesce(jsonb_agg(administration.inspect_user(actor,sv,exp,u.id)-'resetUntil'
                || jsonb_build_object('hasPush',EXISTS(SELECT FROM notifications.subscriptions s WHERE s.owner_id=u.id))
                ORDER BY u.id COLLATE "C"),'[]'::jsonb) INTO result
                FROM (SELECT id FROM identity.users WHERE after_id IS NULL OR id COLLATE "C">after_id COLLATE "C"
                    ORDER BY id COLLATE "C" LIMIT page_size) u;
            IF exp<=clock_timestamp() THEN RETURN NULL; END IF;
            RETURN result;
        END $$""",
        """CREATE FUNCTION administration.set_disabled(actor text,sv bigint,exp timestamptz,target text,disabled boolean)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,target);
            IF access IS NULL OR access='{}'::jsonb OR access ? 'error' THEN RETURN access; END IF;
            IF (access->>'admin')::boolean THEN RETURN '{"error":"cannot disable an admin"}'::jsonb; END IF;
            UPDATE identity.users u SET disabled=$5 WHERE u.id=target;
            IF $5 THEN DELETE FROM identity.device_links l WHERE l.owner_id=target; END IF;
            RETURN jsonb_build_object('ok',true,'id',target,'disabled',$5);
        END $$""",
    ]
    # records() keeps only objects, preserving array order and omitting malformed rows.
    workouts = "jsonb_array_elements(CASE WHEN jsonb_typeof(doc->'workouts')='array' THEN doc->'workouts' ELSE '[]'::jsonb END) WITH ORDINALITY AS w(value,position)"
    sync = "synced"
    for name, projection in (
        (
            "read_admin_summary",
            f"""jsonb_build_object('workouts',(SELECT count(*) FROM {workouts} WHERE jsonb_typeof(value)='object'),
            'lastSync',{sync}) || coalesce((SELECT CASE WHEN value ? 'd' THEN jsonb_build_object('lastWorkout',value->'d') ELSE '{{}}'::jsonb END
                FROM {workouts} WHERE jsonb_typeof(value)='object' ORDER BY position DESC LIMIT 1),jsonb_build_object('lastWorkout',NULL))""",
        ),
        (
            "read_admin_detail",
            f"""jsonb_build_object('unit',CASE WHEN doc->'unit' IS NULL OR doc->'unit' IN ('null','false','0','\"\"') THEN '\"kg\"'::jsonb ELSE doc->'unit' END,
            'lastSync',{sync},
            'routines',coalesce((SELECT jsonb_agg((SELECT coalesce(jsonb_object_agg(key,val),'{{}}') FROM (VALUES('id',value->'id'),('name',value->'name'),('emoji',value->'emoji')) p(key,val) WHERE val IS NOT NULL)
                || jsonb_build_object('count',(SELECT count(*) FROM jsonb_array_elements(CASE WHEN jsonb_typeof(value->'ex')='array' THEN value->'ex' ELSE '[]'::jsonb END) e WHERE jsonb_typeof(e)='object')) ORDER BY position)
                FROM jsonb_array_elements(CASE WHEN jsonb_typeof(doc->'routines')='array' THEN doc->'routines' ELSE '[]'::jsonb END) WITH ORDINALITY AS r(value,position)
                WHERE jsonb_typeof(value)='object'),'[]'),
            'bodyweight',coalesce((SELECT jsonb_agg(value ORDER BY position)
                FROM jsonb_array_elements(CASE WHEN jsonb_typeof(doc->'bodyweight')='array' THEN doc->'bodyweight' ELSE '[]'::jsonb END) WITH ORDINALITY AS b(value,position)
                WHERE jsonb_typeof(value)='object'),'[]'),
            'workouts',coalesce((SELECT jsonb_agg(value-'media' ORDER BY position DESC) FROM {workouts} WHERE jsonb_typeof(value)='object'),'[]'))""",
        ),
    ):
        statements.append(f"""CREATE FUNCTION training.{name}(actor text,sv bigint,exp timestamptz,target text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb; doc jsonb; stamp jsonb; pull numeric; pushed double precision; synced double precision;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,target);
            IF access IS NULL OR access='{{}}'::jsonb OR access ? 'error' THEN RETURN access; END IF;
            SELECT d.document INTO doc FROM training.documents d WHERE d.owner_id=target;
            SELECT floor(extract(epoch FROM u.last_pull_at)*1000) INTO pull FROM identity.users u WHERE u.id=target;
            -- Node Math.max invalid/overflow input serializes as null, never a failed view.
            BEGIN
                stamp:=doc->'_ts';
                WHILE jsonb_typeof(stamp)='array' LOOP
                    EXIT WHEN jsonb_array_length(stamp)>1;
                    stamp:=stamp->0;
                END LOOP;
                pushed:=CASE WHEN doc->'_ts' IS NULL OR doc->'_ts' IN ('null','false') THEN 0
                    WHEN doc->'_ts'='true'::jsonb THEN 1
                    ELSE coalesce(nullif(btrim(stamp #>> '{{}}'),''),'0')::double precision END;
            EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN pushed:=NULL;
            END;
            IF pushed IS NOT NULL AND pushed NOT IN ('Infinity'::double precision,'-Infinity'::double precision,'NaN'::double precision)
            THEN synced:=nullif(greatest(pushed,coalesce(pull,0)),0); END IF;
            RETURN {projection};
        END $$""")
    for signature in (
        "administration.inspect_user(text,bigint,timestamptz,text)",
        "administration.list_users(text,bigint,timestamptz,integer,text)",
        "administration.set_disabled(text,bigint,timestamptz,text,boolean)",
        "training.read_admin_summary(text,bigint,timestamptz,text)",
        "training.read_admin_detail(text,bigint,timestamptz,text)",
    ):
        schema = signature.split(".")[0]
        statements += [
            f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION {signature} TO opengym_api_runtime",
            f"GRANT CREATE ON SCHEMA {schema} TO opengym_administration_executor",
            f"ALTER FUNCTION {signature} OWNER TO opengym_administration_executor",
            f"REVOKE CREATE ON SCHEMA {schema} FROM opengym_administration_executor",
        ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
