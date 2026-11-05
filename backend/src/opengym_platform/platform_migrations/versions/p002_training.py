"""Canonical Training documents with strict, derived metadata."""

from alembic import op

revision = "p002_training"
down_revision = "p001_password_login"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "CREATE SCHEMA training AUTHORIZATION opengym_schema_owner",
        "GRANT USAGE ON SCHEMA training TO opengym_api_runtime",
        """CREATE FUNCTION training.revision_of(document jsonb) RETURNS bigint
        LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp AS $$
        DECLARE value jsonb := document -> '_rev'; number numeric;
        BEGIN
            IF value IS NULL OR value = 'null'::jsonb THEN RETURN 0; END IF;
            IF jsonb_typeof(value) <> 'number' THEN
                RAISE EXCEPTION 'invalid training revision' USING ERRCODE = '22023';
            END IF;
            number := value::numeric;
            IF number <> trunc(number) OR number < 0 OR number > 9007199254740991 THEN
                RAISE EXCEPTION 'invalid training revision' USING ERRCODE = '22023';
            END IF;
            RETURN number::bigint;
        END $$""",
        """CREATE FUNCTION training.write_id_of(document jsonb) RETURNS text
        LANGUAGE plpgsql IMMUTABLE STRICT SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp AS $$
        DECLARE value jsonb := document -> '_wid';
        BEGIN
            IF value IS NULL OR value = 'null'::jsonb THEN RETURN NULL; END IF;
            IF jsonb_typeof(value) <> 'string' THEN
                RAISE EXCEPTION 'invalid training write id' USING ERRCODE = '22023';
            END IF;
            RETURN document ->> '_wid';
        END $$""",
        """CREATE TABLE training.documents (
            owner_id text PRIMARY KEY REFERENCES identity.users(id) ON DELETE CASCADE,
            document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
            revision bigint GENERATED ALWAYS AS (training.revision_of(document)) STORED,
            write_id text GENERATED ALWAYS AS (training.write_id_of(document)) STORED
        )""",
        "ALTER TABLE training.documents ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE training.documents FORCE ROW LEVEL SECURITY",
        """CREATE POLICY runtime_owner ON training.documents TO opengym_api_runtime
            USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
            WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''))""",
        "GRANT SELECT ON training.documents TO opengym_api_runtime",
        "GRANT EXECUTE ON FUNCTION training.revision_of(jsonb), training.write_id_of(jsonb) TO opengym_api_runtime",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
