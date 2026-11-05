"""Atomic account deletion and durable external cleanup identifiers."""

from alembic import op

revision = "p004_deletion_tasks"
down_revision = "p005_delivery"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE administration.deletion_tasks (
            id uuid PRIMARY KEY, deleted_owner_id text NOT NULL,
            created_at timestamptz(3) NOT NULL, status text NOT NULL CHECK(status IN ('pending','retry','done')),
            attempts integer NOT NULL CHECK(attempts>=0), last_error_code text,
            secret_refs text[] NOT NULL CHECK(array_position(secret_refs,NULL) IS NULL),
            CHECK(last_error_code IS NULL OR last_error_code IN ('media','secret','internal'))
        )""",
        "CREATE INDEX deletion_tasks_pending ON administration.deletion_tasks(created_at,id) WHERE status IN ('pending','retry')",
        "ALTER TABLE administration.deletion_tasks ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE administration.deletion_tasks FORCE ROW LEVEL SECURITY",
        "CREATE POLICY deletion_tasks ON administration.deletion_tasks TO opengym_administration_executor USING(true) WITH CHECK(true)",
        "GRANT INSERT ON administration.deletion_tasks TO opengym_administration_executor",
        "GRANT DELETE ON identity.users TO opengym_administration_executor",
        "GRANT USAGE ON SCHEMA coach TO opengym_administration_executor",
        "GRANT SELECT(bound_owner_id) ON coach.provider_settings TO opengym_administration_executor",
        "CREATE POLICY deletion_bound_check ON coach.provider_settings FOR SELECT TO opengym_administration_executor USING(true)",
        """CREATE FUNCTION coach.disconnect_owner(actor text,sv bigint,exp timestamptz,target text)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE authorized record; refs text[];
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            PERFORM u.id FROM identity.users u WHERE u.id IN (actor,target)
                ORDER BY u.id COLLATE "C" FOR UPDATE;
            SELECT * INTO authorized FROM identity.lock_actor(actor,sv,exp);
            IF NOT FOUND THEN RETURN NULL; END IF;
            IF actor IS DISTINCT FROM target AND NOT authorized.is_admin THEN RETURN '{}'::jsonb; END IF;
            PERFORM 1 FROM coach.settings FOR UPDATE;
            IF exp<=clock_timestamp() THEN RETURN NULL; END IF;
            SELECT coalesce(array_agg(DISTINCT p.secret_ref) FILTER(WHERE p.secret_ref IS NOT NULL),ARRAY[]::text[])
                INTO refs FROM coach.provider_settings p WHERE p.bound_owner_id=target;
            UPDATE coach.provider_settings p SET secret_ref=NULL,bound_owner_id=NULL WHERE p.bound_owner_id=target;
            PERFORM set_config('app.deletion_cleanup',jsonb_build_object('target',target,'refs',refs)::text,true);
            RETURN jsonb_build_object('ok',true);
        END $$""",
        """CREATE FUNCTION administration.delete_user(actor text,sv bigint,exp timestamptz,target text,task_id uuid)
        RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE access jsonb; cleanup jsonb; refs text[];
        BEGIN
            access:=administration.inspect_user(actor,sv,exp,target);
            IF access IS NULL OR access='{}'::jsonb OR access ? 'error' THEN RETURN access; END IF;
            IF target=actor THEN RETURN '{"error":"you cannot delete your own account"}'::jsonb; END IF;
            IF (access->>'admin')::boolean AND (SELECT count(*) FROM identity.users u WHERE u.is_admin)<=1
                THEN RETURN '{"error":"cannot delete the last admin"}'::jsonb; END IF;
            cleanup:=nullif(current_setting('app.deletion_cleanup',true),'')::jsonb;
            IF cleanup->>'target' IS DISTINCT FROM target OR jsonb_typeof(cleanup->'refs') IS DISTINCT FROM 'array'
                OR EXISTS(SELECT FROM coach.provider_settings p WHERE p.bound_owner_id=target)
            THEN RAISE EXCEPTION 'DELETE_CLEANUP_REQUIRED' USING ERRCODE='22023'; END IF;
            SELECT coalesce(array_agg(value),ARRAY[]::text[]) INTO refs FROM jsonb_array_elements_text(cleanup->'refs');
            INSERT INTO administration.deletion_tasks(id,deleted_owner_id,created_at,status,attempts,secret_refs)
                VALUES(task_id,target,clock_timestamp(),'pending',0,refs);
            DELETE FROM identity.users u WHERE u.id=target;
            PERFORM set_config('app.deletion_cleanup','',true);
            RETURN jsonb_build_object('ok',true,'id',target);
        END $$""",
    ]
    for signature, owner in (
        (
            "coach.disconnect_owner(text,bigint,timestamptz,text)",
            "opengym_coach_executor",
        ),
        (
            "administration.delete_user(text,bigint,timestamptz,text,uuid)",
            "opengym_administration_executor",
        ),
    ):
        schema = signature.split(".")[0]
        statements += [
            f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION {signature} TO opengym_api_runtime",
            f"GRANT CREATE ON SCHEMA {schema} TO {owner}",
            f"ALTER FUNCTION {signature} OWNER TO {owner}",
            f"REVOKE CREATE ON SCHEMA {schema} FROM {owner}",
        ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
