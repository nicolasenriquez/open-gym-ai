"""Bounded administration; external credentials never enter PostgreSQL."""

from alembic import op

revision = "p003_coach_admin"
down_revision = "p003_coach_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE coach.instance_results (
            event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            occurred_at timestamptz NOT NULL, kind text NOT NULL CHECK(kind IN ('create','review','debrief')),
            trigger text NOT NULL CHECK(trigger IN ('manual','scheduled')),
            outcome text NOT NULL CHECK(outcome IN ('ready','nochange','failed')),
            error_class text, duration_ms bigint NOT NULL CHECK(duration_ms>=0),
            summary jsonb NOT NULL DEFAULT '{}' CHECK(summary='{}'::jsonb))""",
        "ALTER TABLE coach.instance_results ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE coach.instance_results FORCE ROW LEVEL SECURITY",
        "CREATE POLICY coach_results ON coach.instance_results TO opengym_coach_executor USING(true) WITH CHECK(true)",
        "GRANT SELECT,INSERT,DELETE ON coach.instance_results TO opengym_coach_executor",
        "GRANT USAGE ON SEQUENCE coach.instance_results_event_id_seq TO opengym_coach_executor",
        """CREATE FUNCTION coach.collect_result() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF NEW.outcome NOT IN ('ready','nochange','failed') THEN RETURN NEW; END IF;
            PERFORM 1 FROM coach.settings FOR UPDATE;
            INSERT INTO coach.instance_results(occurred_at,kind,trigger,outcome,error_class,duration_ms)
                SELECT NEW.occurred_at,j.kind,j.trigger,NEW.outcome,
                    CASE WHEN NEW.error_class IN ('auth','provider','timeout','internal','off','restart','unusable','noworkout','toolarge')
                        THEN NEW.error_class WHEN NEW.error_class IS NOT NULL THEN 'internal' END,
                    greatest(0,(extract(epoch FROM (NEW.occurred_at-j.started_at))*1000)::bigint)
                FROM coach.jobs j WHERE j.owner_id=NEW.owner_id AND j.job_id=NEW.job_id;
            DELETE FROM coach.instance_results r WHERE r.event_id IN (
                SELECT event_id FROM coach.instance_results ORDER BY event_id DESC OFFSET 100);
            RETURN NEW;
        END $$""",
        "CREATE TRIGGER coach_result AFTER INSERT ON coach.history_events FOR EACH ROW EXECUTE FUNCTION coach.collect_result()",
        "GRANT SELECT,UPDATE ON coach.settings TO opengym_coach_executor",
        "GRANT SELECT,UPDATE ON coach.provider_settings TO opengym_coach_executor",
        "CREATE POLICY coach_admin ON coach.provider_settings TO opengym_coach_executor USING (true) WITH CHECK (true)",
        """CREATE FUNCTION coach.read_instance(actor text, sv bigint, exp timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE uid text; authorized record; result jsonb;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            FOR uid IN SELECT id FROM (
                SELECT actor AS id UNION SELECT bound_owner_id FROM coach.provider_settings
                    WHERE bound_owner_id IS NOT NULL) owners ORDER BY id COLLATE "C"
            LOOP PERFORM identity.lock_actor(uid,NULL,NULL); END LOOP;
            SELECT * INTO authorized FROM identity.lock_actor(actor,sv,exp);
            IF NOT FOUND THEN RETURN NULL; END IF;
            IF NOT authorized.is_admin THEN RETURN '{}'::jsonb; END IF;
            PERFORM 1 FROM coach.settings FOR UPDATE;
            IF exp<=clock_timestamp() THEN RETURN NULL; END IF;
            SELECT jsonb_build_object('settings',to_jsonb(s)-'id','providers',(
                SELECT jsonb_object_agg(p.provider,jsonb_build_object('model',p.model,
                    'options',p.options,'secret_ref',p.secret_ref,'connected',p.secret_ref IS NOT NULL,
                    'bound_owner_id',p.bound_owner_id)) FROM coach.provider_settings p))
                INTO result FROM coach.settings s;
            RETURN result;
        END $$""",
        """CREATE FUNCTION coach.read_results(actor text, sv bigint, exp timestamptz)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb;
        BEGIN
            access:=coach.read_instance(actor,sv,exp);
            IF access IS NULL OR access='{}'::jsonb THEN RETURN NULL; END IF;
            RETURN jsonb_build_object('jobsToday',coalesce((SELECT count FROM coach.instance_daily_usage
                WHERE day=(clock_timestamp() AT TIME ZONE 'UTC')::date),0),
                'results',coalesce((SELECT jsonb_agg(jsonb_build_object('at',floor(extract(epoch FROM occurred_at)*1000),
                    'kind',kind,'trigger',trigger,'outcome',outcome,'errorClass',error_class,'ms',duration_ms) ORDER BY event_id DESC)
                    FROM coach.instance_results),'[]'::jsonb));
        END $$""",
        """CREATE FUNCTION coach.write_instance(actor text, sv bigint, exp timestamptz,
            settings jsonb, providers jsonb)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE current jsonb; name text; entry jsonb;
        BEGIN
            current := coach.read_instance(actor,sv,exp);
            IF current IS NULL OR current='{}'::jsonb THEN RETURN current; END IF;
            IF jsonb_typeof(settings) IS DISTINCT FROM 'object'
                OR settings - ARRAY['enabled','provider','auth_mode','community',
                    'per_profile_daily','instance_daily','max_message_len','max_output_tokens'] <> '{}'
                OR NOT settings ?& ARRAY['enabled','provider','auth_mode','community',
                    'per_profile_daily','instance_daily','max_message_len','max_output_tokens']
                OR jsonb_typeof(providers) IS DISTINCT FROM 'object'
            THEN RAISE EXCEPTION 'COACH_CONFIG_INVALID' USING ERRCODE='22023'; END IF;
            IF EXISTS (SELECT FROM jsonb_each(settings) e WHERE
                (e.key IN ('enabled','community') AND jsonb_typeof(e.value)<>'boolean')
                OR (e.key IN ('provider','auth_mode') AND jsonb_typeof(e.value)<>'string')
                OR (e.key IN ('per_profile_daily','instance_daily','max_message_len','max_output_tokens')
                    AND (jsonb_typeof(e.value)<>'number' OR (e.value::text)::numeric<>trunc((e.value::text)::numeric))))
            THEN RAISE EXCEPTION 'COACH_CONFIG_INVALID' USING ERRCODE='22023'; END IF;
            -- Public config never introduces per-profile sign-in that Node does not expose.
            IF settings->>'auth_mode' IS DISTINCT FROM current #>> '{settings,auth_mode}'
            THEN RAISE EXCEPTION 'COACH_CONFIG_INVALID' USING ERRCODE='22023'; END IF;
            FOR name,entry IN SELECT * FROM jsonb_each(providers) LOOP
                IF NOT EXISTS (SELECT FROM coach.provider_settings p WHERE p.provider=name)
                    OR jsonb_typeof(entry) IS DISTINCT FROM 'object'
                    OR entry - ARRAY['model','options','secret_ref'] <> '{}'
                    OR (entry ? 'model' AND jsonb_typeof(entry->'model') NOT IN ('string','null'))
                    OR (entry ? 'secret_ref' AND jsonb_typeof(entry->'secret_ref') NOT IN ('string','null'))
                    OR (entry->>'secret_ref' IS NOT NULL AND entry->>'secret_ref' !~ '^coach-key-[a-f0-9]{32}[.]json$')
                THEN RAISE EXCEPTION 'COACH_CONFIG_INVALID' USING ERRCODE='22023'; END IF;
                UPDATE coach.provider_settings p SET
                    model=CASE WHEN entry ? 'model' THEN entry->>'model' ELSE p.model END,
                    options=CASE WHEN entry ? 'options' THEN entry->'options' ELSE p.options END,
                    secret_ref=CASE WHEN entry ? 'secret_ref' THEN entry->>'secret_ref' ELSE p.secret_ref END,
                    bound_owner_id=CASE WHEN entry ? 'secret_ref' THEN NULL ELSE p.bound_owner_id END
                    WHERE p.provider=name;
            END LOOP;
            UPDATE coach.settings s SET enabled=(settings->>'enabled')::boolean,
                provider=settings->>'provider',auth_mode=settings->>'auth_mode',
                community=(settings->>'community')::boolean,
                per_profile_daily=(settings->>'per_profile_daily')::integer,
                instance_daily=(settings->>'instance_daily')::integer,
                max_message_len=(settings->>'max_message_len')::integer,
                max_output_tokens=(settings->>'max_output_tokens')::integer;
            RETURN coach.read_instance(actor,sv,exp);
        END $$""",
        """CREATE FUNCTION coach.credential_context(actor text, sv bigint, exp timestamptz)
        RETURNS TABLE(provider text,auth_mode text,enabled boolean,secret_ref text,bound_owner_id text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF nullif(current_setting('app.owner_id',true),'') IS DISTINCT FROM actor
                OR NOT EXISTS (SELECT FROM identity.lock_actor(actor,sv,exp))
            THEN RETURN; END IF;
            PERFORM 1 FROM coach.settings FOR UPDATE;
            IF exp<=clock_timestamp() THEN RETURN; END IF;
            RETURN QUERY SELECT s.provider,s.auth_mode,s.enabled,p.secret_ref,p.bound_owner_id
                FROM coach.settings s JOIN coach.provider_settings p ON p.provider=s.provider
                FOR UPDATE OF s;
        END $$""",
    ]
    for signature in (
        "read_instance(text,bigint,timestamptz)",
        "write_instance(text,bigint,timestamptz,jsonb,jsonb)",
        "credential_context(text,bigint,timestamptz)",
        "read_results(text,bigint,timestamptz)",
        "collect_result()",
    ):
        if signature != "collect_result()":
            statements.append(
                f"GRANT EXECUTE ON FUNCTION coach.{signature} TO opengym_api_runtime"
            )
        statements += [
            f"REVOKE ALL ON FUNCTION coach.{signature} FROM PUBLIC",
            "GRANT CREATE ON SCHEMA coach TO opengym_coach_executor",
            f"ALTER FUNCTION coach.{signature} OWNER TO opengym_coach_executor",
            "REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor",
        ]
    for statement in statements:
        op.execute(statement)

    op.execute("GRANT CREATE ON SCHEMA coach TO opengym_coach_executor")
    op.execute("SET ROLE opengym_coach_executor")
    op.execute("""CREATE OR REPLACE FUNCTION coach.execution_config(actor text, sv bigint, exp timestamptz)
        RETURNS TABLE(provider text,model text,options jsonb,auth_mode text,
            max_message_len integer,max_output_tokens integer,per_profile_daily integer)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
            IF nullif(current_setting('app.owner_id',true),'') IS DISTINCT FROM actor
                OR NOT EXISTS (SELECT FROM identity.lock_actor(actor,sv,exp))
            THEN RETURN; END IF;
            IF NOT EXISTS (SELECT FROM training.documents d WHERE d.owner_id=actor
                AND d.document #> '{coach,consent,agreedAt}' IS NOT NULL
                AND d.document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""'))
            THEN RETURN; END IF;
            PERFORM 1 FROM coach.settings FOR UPDATE;
            IF exp<=clock_timestamp() THEN RETURN; END IF;
            RETURN QUERY SELECT s.provider,p.model,p.options,s.auth_mode,
                s.max_message_len,s.max_output_tokens,s.per_profile_daily
                FROM coach.settings s JOIN coach.provider_settings p ON p.provider=s.provider
                WHERE s.enabled AND s.provider NOT IN ('claude','codex')
                FOR UPDATE OF s;
        END $$""")
    op.execute("""CREATE OR REPLACE FUNCTION coach.reserve_job(actor text, sv bigint, exp timestamptz,
            requested_job text, requested_kind text, requested_trigger text,
            expected_generation bigint, at timestamptz)
        RETURNS TABLE(job_id text,state text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE config record; generation bigint; day_utc date; used bigint; total bigint;
        BEGIN
            IF nullif(current_setting('app.owner_id',true),'') IS DISTINCT FROM actor
                OR NOT EXISTS (SELECT FROM identity.lock_actor(actor,sv,exp))
            THEN RETURN QUERY SELECT NULL::text,'unauthorized'::text; RETURN; END IF;
            IF requested_kind NOT IN ('create','review','debrief') OR requested_kind IS NULL
                OR requested_trigger NOT IN ('manual','scheduled') OR requested_trigger IS NULL
                OR requested_job IS NULL OR requested_job='' OR at IS NULL OR NOT isfinite(at)
                OR expected_generation IS NULL OR expected_generation < 0
            THEN RAISE EXCEPTION 'COACH_RESERVATION_INVALID' USING ERRCODE='22023'; END IF;
            SELECT enabled,provider,auth_mode,per_profile_daily,instance_daily INTO config
                FROM coach.settings FOR UPDATE;
            IF exp<=clock_timestamp()
            THEN RETURN QUERY SELECT NULL::text,'unauthorized'::text; RETURN; END IF;
            IF NOT FOUND OR NOT config.enabled OR config.provider IN ('claude','codex')
                OR (config.provider IN ('anthropic','openai','gemini') AND config.auth_mode='instance'
                    AND NOT EXISTS (SELECT FROM coach.provider_settings p WHERE p.provider=config.provider
                        AND (coalesce(p.model,'')<>'' OR p.secret_ref IS NOT NULL)))
                OR (config.provider = 'compatible'
                    AND NOT EXISTS (SELECT FROM coach.provider_settings p
                        WHERE p.provider=config.provider AND p.model IS NOT NULL AND p.model<>''))
            THEN RETURN QUERY SELECT NULL::text,'off'::text; RETURN; END IF;
            IF EXISTS (SELECT FROM coach.jobs j WHERE j.owner_id=actor)
            THEN RETURN QUERY SELECT NULL::text,'busy'::text; RETURN; END IF;
            IF NOT EXISTS (SELECT FROM training.documents d WHERE d.owner_id=actor
                AND d.document #> '{coach,consent,agreedAt}' IS NOT NULL
                AND d.document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""'))
            THEN RETURN QUERY SELECT NULL::text,'consent'::text; RETURN; END IF;
            SELECT p.forget_generation INTO generation FROM coach.profile_state p WHERE p.owner_id=actor;
            IF coalesce(generation,0) <> expected_generation
            THEN RETURN QUERY SELECT NULL::text,'consent'::text; RETURN; END IF;
            day_utc := (at AT TIME ZONE 'UTC')::date;
            SELECT count INTO used FROM coach.daily_usage u WHERE u.owner_id=actor AND u.day=day_utc;
            SELECT count INTO total FROM coach.instance_daily_usage u WHERE u.day=day_utc;
            IF (config.per_profile_daily > 0 AND coalesce(used,0) >= config.per_profile_daily)
                OR (config.instance_daily > 0 AND coalesce(total,0) >= config.instance_daily)
            THEN RETURN QUERY SELECT NULL::text,'cap'::text; RETURN; END IF;
            INSERT INTO coach.profile_state(owner_id) VALUES(actor) ON CONFLICT DO NOTHING;
            INSERT INTO coach.daily_usage(owner_id,day,count) VALUES(actor,day_utc,1)
                ON CONFLICT (owner_id,day) DO UPDATE SET count=coach.daily_usage.count+1;
            INSERT INTO coach.instance_daily_usage(day,count) VALUES(day_utc,1)
                ON CONFLICT (day) DO UPDATE SET count=coach.instance_daily_usage.count+1;
            INSERT INTO coach.jobs(owner_id,job_id,kind,trigger,state,started_at,forget_generation)
                VALUES(actor,requested_job,requested_kind,requested_trigger,'queued',at,expected_generation);
            RETURN QUERY SELECT requested_job,'queued'::text;
        END $$""")
    op.execute("""CREATE OR REPLACE FUNCTION coach.fail_interrupted_jobs() RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE affected bigint; owners text[];
        BEGIN
            -- Only the single worker's startup calls this, before accepting traffic.
            PERFORM 1 FROM coach.settings FOR UPDATE;
            INSERT INTO coach.instance_results(occurred_at,kind,trigger,outcome,error_class,duration_ms)
                SELECT clock_timestamp(),kind,trigger,'failed','restart',
                    greatest(0,(extract(epoch FROM (clock_timestamp()-started_at))*1000)::bigint)
                FROM coach.jobs;
            DELETE FROM coach.instance_results r WHERE r.event_id IN (
                SELECT event_id FROM coach.instance_results ORDER BY event_id DESC OFFSET 100);
            WITH interrupted AS (DELETE FROM coach.jobs RETURNING *), archived AS (
                INSERT INTO coach.history_events(owner_id,job_id,kind,outcome,occurred_at,error_class)
                    SELECT owner_id,job_id,kind,'failed',clock_timestamp(),'restart' FROM interrupted
                    RETURNING owner_id)
                SELECT count(*),array_agg(owner_id) INTO affected,owners FROM archived;
            DELETE FROM coach.history_events h WHERE h.owner_id=ANY(owners) AND h.event_id IN (
                SELECT event_id FROM (
                    SELECT event_id,row_number() OVER (
                        PARTITION BY owner_id ORDER BY occurred_at DESC,event_id DESC) AS position
                    FROM coach.history_events WHERE owner_id=ANY(owners)
                ) ranked WHERE position > 20);
            RETURN affected;
        END $$""")
    op.execute("SET ROLE opengym_schema_owner")
    op.execute("REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor")


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
