"""Bounded, restart-safe external deletion work; no runtime table access."""

from alembic import op

revision = "p004_external_cleanup"
down_revision = "p004_deletion_tasks"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        "ALTER TABLE administration.deletion_tasks ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT (clock_timestamp()+interval '1 second')",
        "GRANT SELECT ON administration.deletion_tasks TO opengym_administration_executor",
        "GRANT UPDATE(status,attempts,last_error_code,next_attempt_at) ON administration.deletion_tasks TO opengym_administration_executor",
        "GRANT SELECT(secret_ref) ON coach.provider_settings TO opengym_administration_executor",
        """CREATE FUNCTION administration.claim_cleanup(requested uuid)
        RETURNS TABLE(id uuid,attempt integer) LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        DECLARE task uuid;
        BEGIN
            SELECT t.id INTO task FROM administration.deletion_tasks t
                WHERE (requested IS NULL OR t.id=requested) AND t.status IN ('pending','retry')
                AND t.attempts<5 AND t.next_attempt_at<=clock_timestamp()
                ORDER BY t.created_at,t.id LIMIT 1 FOR UPDATE SKIP LOCKED;
            IF NOT FOUND THEN RETURN; END IF;
            RETURN QUERY UPDATE administration.deletion_tasks t SET status='retry',
                attempts=t.attempts+1,last_error_code='internal',
                next_attempt_at=clock_timestamp()+make_interval(secs=>(ARRAY[5,15,60,300,300])[t.attempts+1])
                WHERE t.id=task RETURNING t.id,t.attempts;
        END $$""",
        """CREATE FUNCTION administration.lock_cleanup(task uuid,attempt integer)
        RETURNS TABLE(deleted_owner_id text,secret_refs text[],error_code text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE work administration.deletion_tasks%ROWTYPE;
        BEGIN
            PERFORM pg_advisory_xact_lock(728323);
            SELECT * INTO work FROM administration.deletion_tasks t WHERE t.id=task FOR UPDATE;
            IF NOT FOUND OR work.status<>'retry' OR work.attempts IS DISTINCT FROM attempt THEN RETURN; END IF;
            -- Namespace excludes identity creation and Coach reference reassignment until local unlink completes.
            RETURN QUERY SELECT work.deleted_owner_id,work.secret_refs,
                CASE WHEN EXISTS(SELECT FROM identity.users u WHERE
                    regexp_replace(u.id,'[^a-zA-Z0-9_-]','','g')=work.deleted_owner_id)
                    OR EXISTS(SELECT FROM administration.deletion_tasks other WHERE
                        other.deleted_owner_id<>work.deleted_owner_id AND
                        regexp_replace(other.deleted_owner_id,'[^a-zA-Z0-9_-]','','g')=work.deleted_owner_id)
                    THEN 'media'::text
                WHEN EXISTS(SELECT FROM coach.provider_settings p WHERE
                    p.secret_ref=ANY(work.secret_refs) OR p.secret_ref='coach-auth-'||work.deleted_owner_id||'.json')
                    THEN 'secret'::text END;
        END $$""",
        """CREATE FUNCTION administration.finish_cleanup(task uuid,attempt integer,error_code text)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            IF error_code IS NOT NULL AND error_code NOT IN ('media','secret','internal')
                THEN RAISE EXCEPTION 'CLEANUP_ERROR_INVALID' USING ERRCODE='22023'; END IF;
            UPDATE administration.deletion_tasks t SET status=CASE WHEN error_code IS NULL THEN 'done' ELSE 'retry' END,
                last_error_code=error_code WHERE t.id=task AND t.status='retry' AND t.attempts=attempt;
            RETURN FOUND;
        END $$""",
        """CREATE FUNCTION administration.cleanup_status(task uuid)
        RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
            SELECT coalesce(jsonb_agg(jsonb_build_object('id',t.id,'deleted_owner_id',t.deleted_owner_id,
                'status',t.status,'attempts',t.attempts,'last_error_code',t.last_error_code,
                'next_attempt_at',t.next_attempt_at,'operator_required',t.status<>'done' AND t.attempts>=5)
                ORDER BY t.status='done',t.created_at,t.id),'[]'::jsonb)
            FROM (SELECT * FROM administration.deletion_tasks d WHERE task IS NULL OR d.id=task
                ORDER BY d.status='done',d.created_at,d.id LIMIT 500) t
        $$""",
        """CREATE FUNCTION administration.retry_cleanup(task uuid)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        BEGIN
            UPDATE administration.deletion_tasks t SET attempts=0,status='pending',last_error_code=NULL,
                next_attempt_at=clock_timestamp()+interval '1 second' WHERE t.id=task AND t.status='retry' AND t.attempts>=5;
            RETURN FOUND;
        END $$""",
    ]
    for signature in (
        "claim_cleanup(uuid)",
        "lock_cleanup(uuid,integer)",
        "finish_cleanup(uuid,integer,text)",
        "cleanup_status(uuid)",
        "retry_cleanup(uuid)",
    ):
        statements += [
            f"REVOKE ALL ON FUNCTION administration.{signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION administration.{signature} TO opengym_api_runtime",
            "GRANT CREATE ON SCHEMA administration TO opengym_administration_executor",
            f"ALTER FUNCTION administration.{signature} OWNER TO opengym_administration_executor",
            "REVOKE CREATE ON SCHEMA administration FROM opengym_administration_executor",
        ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
