"""Current Coach work and bounded restart events; forward-only after configuration."""

from alembic import op

revision = "p003_coach_jobs"
down_revision = "p003_coach"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE coach.jobs (
            owner_id text PRIMARY KEY REFERENCES identity.users(id) ON DELETE CASCADE,
            job_id text NOT NULL UNIQUE,
            kind text NOT NULL CHECK (kind IN ('create','review','debrief')),
            trigger text NOT NULL CHECK (trigger IN ('manual','scheduled')),
            state text NOT NULL CHECK (state IN ('queued','running')),
            started_at timestamptz NOT NULL,
            forget_generation bigint NOT NULL CHECK (forget_generation >= 0)
        )""",
        """CREATE TABLE coach.history_events (
            event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            owner_id text NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
            job_id text,
            kind text NOT NULL CHECK (kind IN ('create','review','debrief')),
            outcome text NOT NULL CHECK (outcome IN
                ('ready','nochange','failed','applied','dismissed','expired')),
            occurred_at timestamptz NOT NULL,
            error_class text,
            details jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(details)='object')
        )""",
        "CREATE INDEX history_events_owner_time ON coach.history_events(owner_id,occurred_at DESC,event_id DESC)",
    ]
    for table in ("jobs", "history_events"):
        statements += [
            f"ALTER TABLE coach.{table} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE coach.{table} FORCE ROW LEVEL SECURITY",
            f"""CREATE POLICY runtime_owner ON coach.{table} TO opengym_api_runtime
                USING (owner_id=nullif(current_setting('app.owner_id',true),''))
                WITH CHECK (owner_id=nullif(current_setting('app.owner_id',true),''))""",
            f"CREATE POLICY coach_work ON coach.{table} TO opengym_coach_executor USING (true) WITH CHECK (true)",
            f"GRANT SELECT,INSERT,UPDATE,DELETE ON coach.{table} TO opengym_coach_executor",
            f"GRANT SELECT,INSERT,UPDATE,DELETE ON coach.{table} TO opengym_api_runtime",
        ]
    statements += [
        "GRANT USAGE ON SEQUENCE coach.history_events_event_id_seq TO opengym_coach_executor,opengym_api_runtime",
        """CREATE FUNCTION coach.fail_interrupted_jobs() RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE affected bigint; owners text[];
        BEGIN
            -- Only the single worker's startup calls this, before accepting traffic.
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
        END $$""",
        "REVOKE ALL ON FUNCTION coach.fail_interrupted_jobs() FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION coach.fail_interrupted_jobs() TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA coach TO opengym_coach_executor",
        "ALTER FUNCTION coach.fail_interrupted_jobs() OWNER TO opengym_coach_executor",
        "REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor",
    ]
    statements += [
        """CREATE TABLE coach.profile_state (
            owner_id text PRIMARY KEY REFERENCES identity.users(id) ON DELETE CASCADE,
            sharing boolean NOT NULL DEFAULT false,
            forget_generation bigint NOT NULL DEFAULT 0 CHECK (forget_generation >= 0))""",
        """CREATE TABLE coach.daily_usage (
            owner_id text NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
            day date NOT NULL, count bigint NOT NULL CHECK (count >= 0),
            PRIMARY KEY(owner_id,day))""",
        """CREATE TABLE coach.instance_daily_usage (
            day date PRIMARY KEY, count bigint NOT NULL CHECK (count >= 0))""",
        "GRANT USAGE ON SCHEMA identity,training TO opengym_coach_executor",
        "SET ROLE opengym_identity_executor",
        "GRANT EXECUTE ON FUNCTION identity.lock_actor(text,bigint,timestamptz) TO opengym_coach_executor",
        "SET ROLE opengym_schema_owner",
        "GRANT SELECT (owner_id,document) ON training.documents TO opengym_coach_executor",
        """CREATE POLICY coach_consent ON training.documents FOR SELECT TO opengym_coach_executor
            USING (owner_id=nullif(current_setting('app.owner_id',true),''))""",
        "GRANT SELECT (per_profile_daily,instance_daily) ON coach.settings TO opengym_coach_executor",
        "GRANT UPDATE (id) ON coach.settings TO opengym_coach_executor",
        "CREATE POLICY coach_reserve_lock ON coach.settings FOR UPDATE TO opengym_coach_executor USING (true) WITH CHECK (true)",
    ]
    for table in ("profile_state", "daily_usage", "instance_daily_usage"):
        statements += [
            f"ALTER TABLE coach.{table} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE coach.{table} FORCE ROW LEVEL SECURITY",
            f"CREATE POLICY coach_work ON coach.{table} TO opengym_coach_executor USING (true) WITH CHECK (true)",
            f"GRANT SELECT,INSERT,UPDATE ON coach.{table} TO opengym_coach_executor",
        ]
        if table != "instance_daily_usage":
            statements += [
                f"""CREATE POLICY runtime_owner ON coach.{table} TO opengym_api_runtime
                    USING (owner_id=nullif(current_setting('app.owner_id',true),''))
                    WITH CHECK (owner_id=nullif(current_setting('app.owner_id',true),''))""",
                f"GRANT SELECT ON coach.{table} TO opengym_api_runtime",
            ]
    statements += [
        "REVOKE UPDATE ON coach.history_events FROM opengym_api_runtime",
        "REVOKE INSERT ON coach.jobs FROM opengym_api_runtime",
        "REVOKE UPDATE ON coach.jobs FROM opengym_api_runtime",
        "GRANT UPDATE (state) ON coach.jobs TO opengym_api_runtime",
        """CREATE FUNCTION coach.reserve_job(actor text, sv bigint, exp timestamptz,
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
            -- HTTP execution/credential resolution is not installed until 5.3/5.5.
            IF NOT FOUND OR NOT config.enabled OR config.provider <> 'fixture' OR config.auth_mode <> 'instance'
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
        END $$""",
        "REVOKE ALL ON FUNCTION coach.reserve_job(text,bigint,timestamptz,text,text,text,bigint,timestamptz) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION coach.reserve_job(text,bigint,timestamptz,text,text,text,bigint,timestamptz) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA coach TO opengym_coach_executor",
        "ALTER FUNCTION coach.reserve_job(text,bigint,timestamptz,text,text,text,bigint,timestamptz) OWNER TO opengym_coach_executor",
        "REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
