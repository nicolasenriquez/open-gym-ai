"""Coach configuration and bounded public availability; no execution state yet."""

from alembic import op

revision = "p003_coach"
down_revision = "p002_media_gc"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "CREATE SCHEMA coach AUTHORIZATION opengym_schema_owner",
        "REVOKE ALL ON SCHEMA coach FROM PUBLIC",
        "GRANT USAGE ON SCHEMA coach TO opengym_api_runtime, opengym_coach_executor",
        """CREATE TABLE coach.provider_settings (
            provider text PRIMARY KEY CHECK (provider IN
                ('fixture','claude','codex','anthropic','openai','gemini','compatible')),
            model text,
            options jsonb NOT NULL DEFAULT '{}' CHECK (
                jsonb_typeof(options) = 'object'
                AND options - ARRAY['baseUrl','headers']::text[] = '{}'::jsonb
                AND (NOT options ? 'baseUrl' OR jsonb_typeof(options->'baseUrl') IN ('string','null'))
                AND (NOT options ? 'headers' OR jsonb_typeof(options->'headers') = 'object')),
            secret_ref text,
            bound_owner_id text REFERENCES identity.users(id) ON DELETE RESTRICT
        )""",
        """CREATE INDEX provider_settings_bound_owner ON coach.provider_settings(bound_owner_id)
            WHERE bound_owner_id IS NOT NULL""",
        """CREATE TABLE coach.settings (
            id smallint PRIMARY KEY CHECK (id = 1),
            enabled boolean NOT NULL DEFAULT false,
            provider text NOT NULL REFERENCES coach.provider_settings(provider),
            auth_mode text NOT NULL DEFAULT 'instance' CHECK (auth_mode IN ('instance','profile')),
            community boolean NOT NULL DEFAULT false,
            per_profile_daily integer NOT NULL DEFAULT 10 CHECK (per_profile_daily BETWEEN 0 AND 200),
            instance_daily integer NOT NULL DEFAULT 0 CHECK (instance_daily BETWEEN 0 AND 5000),
            max_message_len integer NOT NULL DEFAULT 1000 CHECK (max_message_len BETWEEN 200 AND 4000),
            max_output_tokens integer NOT NULL DEFAULT 16000 CHECK (max_output_tokens BETWEEN 1024 AND 65536)
        )""",
        """INSERT INTO coach.provider_settings(provider) VALUES
            ('fixture'),('claude'),('codex'),('anthropic'),('openai'),('gemini'),('compatible')""",
        "INSERT INTO coach.settings(id,provider) VALUES (1,'fixture')",
        "ALTER TABLE coach.settings ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE coach.settings FORCE ROW LEVEL SECURITY",
        "ALTER TABLE coach.provider_settings ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE coach.provider_settings FORCE ROW LEVEL SECURITY",
        """CREATE POLICY coach_disclosure ON coach.settings FOR SELECT TO opengym_coach_executor
            USING (true)""",
        """GRANT SELECT (enabled,provider,auth_mode,community) ON coach.settings
            TO opengym_coach_executor""",
        """CREATE FUNCTION coach.public_disclosure()
        RETURNS TABLE(enabled boolean, provider text, auth_mode text, community boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
            SELECT s.enabled AND s.provider NOT IN ('claude','codex'),
                s.provider, s.auth_mode, s.community FROM coach.settings s
        $$""",
        "REVOKE ALL ON FUNCTION coach.public_disclosure() FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION coach.public_disclosure() TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA coach TO opengym_coach_executor",
        "ALTER FUNCTION coach.public_disclosure() OWNER TO opengym_coach_executor",
        "REVOKE CREATE ON SCHEMA coach FROM opengym_coach_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
