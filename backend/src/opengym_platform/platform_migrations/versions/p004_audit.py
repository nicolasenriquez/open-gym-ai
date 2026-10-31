"""Historical best-effort audit with narrow administrative functions."""

from alembic import op

revision = "p004_audit"
down_revision = "p004_admin_invites"
branch_labels = None
depends_on = None


# Private transaction-local settings, never supplied by an HTTP body.
RETENTION = """
    PERFORM pg_advisory_xact_lock(728325);
    days:=coalesce(nullif(current_setting('app.audit_days',true),''),'90')::numeric;
    cap:=coalesce(nullif(current_setting('app.audit_max',true),''),'5000')::bigint;
    IF days<0 OR days>365000 OR cap<0 THEN
        RAISE EXCEPTION 'AUDIT_CONFIG_INVALID' USING ERRCODE='22023'; END IF;
    IF days>0 THEN DELETE FROM audit.events WHERE occurred_at<clock_timestamp()-days*interval '1 day'; END IF;
    IF cap>0 THEN DELETE FROM audit.events WHERE id IN (SELECT id FROM audit.events ORDER BY id DESC OFFSET cap); END IF;
"""


def upgrade():
    statements = [
        "CREATE SCHEMA audit AUTHORIZATION opengym_schema_owner",
        "REVOKE ALL ON SCHEMA audit FROM PUBLIC",
        "GRANT USAGE ON SCHEMA audit TO opengym_api_runtime,opengym_administration_executor",
        """CREATE TABLE audit.events(
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            occurred_at timestamptz NOT NULL,event text NOT NULL,ok boolean NOT NULL,
            actor_id text,target_id text,actor_name text,target_name text,message text,action text,ip text)""",
        "CREATE INDEX audit_events_occurred_at ON audit.events(occurred_at)",
        "GRANT SELECT,INSERT,DELETE ON audit.events TO opengym_administration_executor",
        "GRANT USAGE ON SEQUENCE audit.events_id_seq TO opengym_administration_executor",
        """CREATE FUNCTION audit.append_event(at timestamptz,event text,ok boolean,actor_id text,target_id text,
            actor_name text,target_name text,message text,action text,ip text)
        RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE days numeric; cap bigint;
        BEGIN
            IF at IS NULL OR NOT isfinite(at) OR event IS NULL OR event !~ '^(auth|admin|media)[.][a-z.-]{1,60}$'
                OR ok IS NULL OR length(actor_id)>256 OR length(target_id)>256
                OR length(actor_name)>40 OR length(target_name)>40 OR length(message)>120
                OR length(action)>40 OR length(ip)>49 THEN
                RAISE EXCEPTION 'AUDIT_EVENT_INVALID' USING ERRCODE='22023'; END IF;
            -- Audit has its own lock, distinct from the notification endpoint lock 728324.
            PERFORM pg_advisory_xact_lock(728325);
            INSERT INTO audit.events(occurred_at,event,ok,actor_id,target_id,actor_name,target_name,message,action,ip)
            VALUES(at,event,ok,actor_id,target_id,
                coalesce(actor_name,(SELECT left(u.display_name,40) FROM identity.users u WHERE u.id=actor_id)),
                coalesce(target_name,(SELECT left(u.display_name,40) FROM identity.users u WHERE u.id=target_id)),
                message,action,ip);
        """
        + RETENTION
        + "END $$",
        """CREATE FUNCTION audit.read_events(actor text,sv bigint,exp timestamptz,after_id bigint,page_size integer)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb; result jsonb; days numeric; cap bigint; category text;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,actor);
            IF access IS NULL OR access='{}'::jsonb THEN RETURN access; END IF;
            IF page_size IS NULL OR page_size<1 OR page_size>200 THEN
                RAISE EXCEPTION 'AUDIT_PAGE_INVALID' USING ERRCODE='22023'; END IF;
        """
        + RETENTION
        + """
            category:=coalesce(current_setting('app.audit_cat',true),'');
            WITH filtered AS (SELECT * FROM audit.events e WHERE category='' OR (category='fail' AND NOT e.ok)
                OR (category<>'fail' AND left(e.event,length(category)+1)=category||'.')),
            page AS (SELECT * FROM filtered WHERE after_id IS NULL OR id<after_id ORDER BY id DESC LIMIT page_size)
            SELECT jsonb_build_object('events',coalesce((SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
                'id',id,'ts',floor(extract(epoch FROM occurred_at)*1000),'ev',event,'ok',ok,
                'uid',actor_id,'tgt',target_id,'name',actor_name,'tname',target_name,'msg',message,'act',action,'ip',ip))
                ORDER BY id DESC) FROM page),'[]'::jsonb),
                'total',(SELECT count(*) FROM filtered),
                'nextBefore',CASE WHEN (SELECT count(*) FROM page)=page_size THEN (SELECT min(id) FROM page) END)
            INTO result;
            IF exp<=clock_timestamp() THEN RETURN NULL; END IF;
            RETURN result;
        END $$""",
        """CREATE FUNCTION audit.clear_events(actor text,sv bigint,exp timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb;
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,actor);
            IF access IS NULL OR access='{}'::jsonb THEN RETURN access; END IF;
            PERFORM pg_advisory_xact_lock(728325);
            IF exp<=clock_timestamp() THEN RETURN NULL; END IF;
            DELETE FROM audit.events;
            RETURN '{"ok": true}'::jsonb;
        END $$""",
    ]
    for signature in (
        "audit.append_event(timestamptz,text,boolean,text,text,text,text,text,text,text)",
        "audit.read_events(text,bigint,timestamptz,bigint,integer)",
        "audit.clear_events(text,bigint,timestamptz)",
    ):
        statements += [
            f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION {signature} TO opengym_api_runtime",
            "GRANT CREATE ON SCHEMA audit TO opengym_administration_executor",
            f"ALTER FUNCTION {signature} OWNER TO opengym_administration_executor",
            "REVOKE CREATE ON SCHEMA audit FROM opengym_administration_executor",
        ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
