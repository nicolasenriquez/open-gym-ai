"""Consented execution settings and owner-scoped pending proposals."""

from alembic import op

revision = "p003_coach_http"
down_revision = "p003_coach_jobs"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        """CREATE TABLE coach.pending_proposals (
            owner_id text PRIMARY KEY REFERENCES identity.users(id) ON DELETE CASCADE,
            document jsonb NOT NULL CHECK (jsonb_typeof(document)='object'),
            proposal_id text GENERATED ALWAYS AS
                (CASE WHEN jsonb_typeof(document->'id')='string' THEN document->>'id' END) STORED NOT NULL CHECK (proposal_id<>''),
            kind text GENERATED ALWAYS AS
                (CASE WHEN jsonb_typeof(document->'kind')='string' THEN document->>'kind' END) STORED NOT NULL CHECK (kind IN ('create','review','debrief')),
            expires_at_ms bigint GENERATED ALWAYS AS
                (CASE WHEN jsonb_typeof(document->'expiresAt')='number'
                    AND (document->>'expiresAt')::numeric=trunc((document->>'expiresAt')::numeric)
                    THEN (document->>'expiresAt')::bigint END) STORED NOT NULL CHECK (expires_at_ms>0))""",
        "ALTER TABLE coach.pending_proposals ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE coach.pending_proposals FORCE ROW LEVEL SECURITY",
        """CREATE POLICY runtime_owner ON coach.pending_proposals TO opengym_api_runtime
            USING (owner_id=nullif(current_setting('app.owner_id',true),''))
            WITH CHECK (owner_id=nullif(current_setting('app.owner_id',true),''))""",
        "GRANT SELECT,INSERT,UPDATE,DELETE ON coach.pending_proposals TO opengym_api_runtime",
        "GRANT SELECT (model,options,provider) ON coach.provider_settings TO opengym_coach_executor",
        """CREATE POLICY coach_execution ON coach.provider_settings FOR SELECT TO opengym_coach_executor
            USING (provider=(SELECT s.provider FROM coach.settings s))""",
        "GRANT SELECT (max_message_len,max_output_tokens) ON coach.settings TO opengym_coach_executor",
        """CREATE FUNCTION coach.execution_config(actor text, sv bigint, exp timestamptz)
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
            RETURN QUERY SELECT s.provider,p.model,p.options,s.auth_mode,
                s.max_message_len,s.max_output_tokens,s.per_profile_daily
                FROM coach.settings s JOIN coach.provider_settings p ON p.provider=s.provider
                WHERE s.enabled AND s.provider NOT IN ('claude','codex') AND s.auth_mode='instance'
                FOR UPDATE OF s;
        END $$""",
        "REVOKE ALL ON FUNCTION coach.execution_config(text,bigint,timestamptz) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION coach.execution_config(text,bigint,timestamptz) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA coach TO opengym_coach_executor",
        "ALTER FUNCTION coach.execution_config(text,bigint,timestamptz) OWNER TO opengym_coach_executor",
        "SET ROLE opengym_coach_executor",
        """CREATE OR REPLACE FUNCTION coach.reserve_job(actor text, sv bigint, exp timestamptz,
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
            IF NOT FOUND OR NOT config.enabled OR config.provider IN ('claude','codex')
                OR config.auth_mode <> 'instance' OR (config.provider <> 'fixture'
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
        END $$""",
        "SET ROLE opengym_schema_owner",
        "REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
