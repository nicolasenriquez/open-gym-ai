"""Consented internal Coach collaboration, without global Training grants."""

from alembic import op

revision = "p003_coach_client"
down_revision = "p003_coach_admin"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        "GRANT SELECT(id,disabled),UPDATE(id) ON identity.users TO opengym_coach_executor",
        "CREATE POLICY coach_candidates ON identity.users TO opengym_coach_executor USING(true) WITH CHECK(true)",
        """CREATE FUNCTION coach.cohort_candidates(actor text,sv bigint,exp timestamptz)
        RETURNS TABLE(owner_id text) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE candidate text;
        BEGIN
            IF NOT (CASE WHEN sv IS NULL AND exp IS NULL THEN EXISTS(SELECT FROM coach.lock_scheduled_owner(actor))
                ELSE nullif(current_setting('app.owner_id',true),'') IS NOT DISTINCT FROM actor AND EXISTS(SELECT FROM identity.lock_actor(actor,sv,exp)) END)
                OR NOT EXISTS(SELECT FROM coach.settings WHERE community AND enabled AND provider NOT IN ('claude','codex'))
                OR NOT EXISTS(SELECT FROM coach.profile_state p WHERE p.owner_id=actor AND p.sharing)
                OR NOT EXISTS(SELECT FROM training.documents WHERE document #> '{coach,consent,agreedAt}' IS NOT NULL
                    AND document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""'))
            THEN RETURN; END IF;
            FOR candidate IN SELECT p.owner_id FROM coach.profile_state p JOIN identity.users u ON u.id=p.owner_id WHERE p.sharing AND NOT u.disabled ORDER BY p.owner_id COLLATE "C" LOOP
                PERFORM set_config('app.owner_id',candidate,true);
                IF EXISTS(SELECT FROM training.documents WHERE document #> '{coach,consent,agreedAt}' IS NOT NULL
                    AND document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""'))
                THEN owner_id:=candidate; RETURN NEXT; END IF;
            END LOOP;
            PERFORM set_config('app.owner_id',actor,true);
        END $$""",
        """CREATE FUNCTION coach.lock_cohort_owner(actor text,sv bigint,exp timestamptz,target text)
        RETURNS TABLE(owner_id text) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            PERFORM u.id FROM identity.users u WHERE u.id IN (actor,target) ORDER BY u.id COLLATE "C" FOR UPDATE;
            IF NOT (CASE WHEN sv IS NULL AND exp IS NULL THEN EXISTS(SELECT FROM coach.lock_scheduled_owner(actor)) ELSE EXISTS(SELECT FROM identity.lock_actor(actor,sv,exp)) END) THEN RETURN; END IF;
            IF NOT EXISTS(SELECT FROM coach.settings WHERE community AND enabled AND provider NOT IN ('claude','codex'))
                OR NOT EXISTS(SELECT FROM identity.users WHERE id=target AND NOT disabled)
            THEN RETURN; END IF;
            PERFORM set_config('app.owner_id',actor,true);
            IF NOT EXISTS(SELECT FROM coach.profile_state p WHERE p.owner_id=actor AND p.sharing)
                OR NOT EXISTS(SELECT FROM training.documents WHERE document #> '{coach,consent,agreedAt}' IS NOT NULL
                    AND document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""'))
            THEN RETURN; END IF;
            PERFORM set_config('app.owner_id',target,true);
            IF NOT EXISTS(SELECT FROM coach.profile_state p WHERE p.owner_id=target AND p.sharing)
                OR NOT EXISTS(SELECT FROM training.documents WHERE document #> '{coach,consent,agreedAt}' IS NOT NULL
                    AND document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""'))
            THEN PERFORM set_config('app.owner_id',actor,true); RETURN; END IF;
            IF exp<=clock_timestamp() THEN PERFORM set_config('app.owner_id',actor,true); RETURN; END IF;
            RETURN QUERY SELECT target;
        END $$""",
    ]
    statements += [
        """CREATE FUNCTION coach.scheduled_candidates(at timestamptz)
        RETURNS TABLE(owner_id text) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE candidate text; previous text:=current_setting('app.owner_id',true);
        BEGIN
            IF at IS NULL OR NOT isfinite(at) OR NOT EXISTS(SELECT FROM coach.settings WHERE enabled AND provider NOT IN ('claude','codex')) THEN RETURN; END IF;
            FOR candidate IN SELECT u.id FROM identity.users u WHERE NOT u.disabled ORDER BY u.id COLLATE "C" LOOP
                PERFORM set_config('app.owner_id',candidate,true);
                IF EXISTS(SELECT FROM training.documents WHERE document #> '{coach,consent,agreedAt}' IS NOT NULL
                    AND document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""')
                    AND jsonb_typeof(document #> '{coach,cadence}')='object')
                THEN owner_id:=candidate; RETURN NEXT; END IF;
            END LOOP;
            PERFORM set_config('app.owner_id',coalesce(previous,''),true);
        END $$""",
        """CREATE FUNCTION coach.lock_scheduled_owner(owner text)
        RETURNS TABLE(owner_id text,forget_generation bigint)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE previous text:=current_setting('app.owner_id',true);
        BEGIN
            PERFORM u.id FROM identity.users u WHERE u.id=owner AND NOT u.disabled FOR UPDATE;
            IF NOT FOUND THEN PERFORM set_config('app.owner_id',coalesce(previous,''),true); RETURN; END IF;
            PERFORM set_config('app.owner_id',owner,true);
            IF NOT EXISTS(SELECT FROM training.documents WHERE document #> '{coach,consent,agreedAt}' IS NOT NULL
                AND document #> '{coach,consent,agreedAt}' NOT IN ('null','false','0','""')
                AND (jsonb_typeof(document #> '{coach,cadence}')='object' OR EXISTS(SELECT FROM coach.jobs j WHERE j.owner_id=owner AND j.kind='review' AND j.trigger='scheduled')))
            THEN PERFORM set_config('app.owner_id',coalesce(previous,''),true); RETURN; END IF;
            PERFORM 1 FROM coach.settings WHERE (enabled AND provider NOT IN ('claude','codex'))
                OR EXISTS(SELECT FROM coach.jobs j WHERE j.owner_id=owner AND j.kind='review' AND j.trigger='scheduled') FOR UPDATE;
            IF NOT FOUND THEN PERFORM set_config('app.owner_id',coalesce(previous,''),true); RETURN; END IF;
            RETURN QUERY SELECT owner,coalesce((SELECT p.forget_generation FROM coach.profile_state p WHERE p.owner_id=owner),0);
        END $$""",
        """CREATE FUNCTION coach.reserve_scheduled_job(owner text,requested_job text,expected_generation bigint,at timestamptz)
        RETURNS TABLE(job_id text,state text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF NOT EXISTS(SELECT FROM coach.lock_scheduled_owner(owner))
            THEN RETURN QUERY SELECT NULL::text,'unauthorized'::text; RETURN; END IF;
            RETURN QUERY SELECT * FROM coach.reserve_job(owner,NULL,NULL,requested_job,'review','scheduled',expected_generation,at);
        END $$""",
    ]
    for signature in (
        "cohort_candidates(text,bigint,timestamptz)",
        "lock_cohort_owner(text,bigint,timestamptz,text)",
        "scheduled_candidates(timestamptz)",
        "lock_scheduled_owner(text)",
        "reserve_scheduled_job(text,text,bigint,timestamptz)",
    ):
        statements += [
            f"REVOKE ALL ON FUNCTION coach.{signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION coach.{signature} TO opengym_api_runtime",
            "GRANT CREATE ON SCHEMA coach TO opengym_coach_executor",
            f"ALTER FUNCTION coach.{signature} OWNER TO opengym_coach_executor",
            "REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor",
        ]
    for statement in statements:
        op.execute(statement)

    op.execute("GRANT CREATE ON SCHEMA coach TO opengym_coach_executor")
    op.execute("SET ROLE opengym_coach_executor")
    op.execute("""CREATE OR REPLACE FUNCTION coach.reserve_job(actor text, sv bigint, exp timestamptz,
            requested_job text, requested_kind text, requested_trigger text,
            expected_generation bigint, at timestamptz)
        RETURNS TABLE(job_id text,state text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE config record; generation bigint; day_utc date; used bigint; total bigint;
        BEGIN
            IF sv IS NULL AND exp IS NULL THEN
                IF requested_kind IS DISTINCT FROM 'review' OR requested_trigger IS DISTINCT FROM 'scheduled'
                    OR NOT EXISTS(SELECT FROM coach.lock_scheduled_owner(actor))
                THEN RETURN QUERY SELECT NULL::text,'unauthorized'::text; RETURN; END IF;
            ELSE
            IF nullif(current_setting('app.owner_id',true),'') IS DISTINCT FROM actor
                OR NOT EXISTS (SELECT FROM identity.lock_actor(actor,sv,exp))
            THEN RETURN QUERY SELECT NULL::text,'unauthorized'::text; RETURN; END IF;
            END IF;
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
    op.execute("""CREATE OR REPLACE FUNCTION coach.execution_config(actor text, sv bigint, exp timestamptz)
        RETURNS TABLE(provider text,model text,options jsonb,auth_mode text,
            max_message_len integer,max_output_tokens integer,per_profile_daily integer)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
            IF sv IS NULL AND exp IS NULL THEN
                IF NOT EXISTS(SELECT FROM coach.lock_scheduled_owner(actor)) THEN RETURN; END IF;
            ELSE
            IF nullif(current_setting('app.owner_id',true),'') IS DISTINCT FROM actor
                OR NOT EXISTS (SELECT FROM identity.lock_actor(actor,sv,exp))
            THEN RETURN; END IF;
            END IF;
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
    op.execute("""CREATE OR REPLACE FUNCTION coach.credential_context(actor text, sv bigint, exp timestamptz)
        RETURNS TABLE(provider text,auth_mode text,enabled boolean,secret_ref text,bound_owner_id text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF sv IS NULL AND exp IS NULL THEN
                IF NOT EXISTS(SELECT FROM coach.lock_scheduled_owner(actor)) THEN RETURN; END IF;
            ELSE
            IF nullif(current_setting('app.owner_id',true),'') IS DISTINCT FROM actor
                OR NOT EXISTS (SELECT FROM identity.lock_actor(actor,sv,exp))
            THEN RETURN; END IF;
            END IF;
            PERFORM 1 FROM coach.settings FOR UPDATE;
            IF exp<=clock_timestamp() THEN RETURN; END IF;
            RETURN QUERY SELECT s.provider,s.auth_mode,s.enabled,p.secret_ref,p.bound_owner_id
                FROM coach.settings s JOIN coach.provider_settings p ON p.provider=s.provider
                FOR UPDATE OF s;
        END $$""")
    op.execute("SET ROLE opengym_schema_owner")
    op.execute("REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor")


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
