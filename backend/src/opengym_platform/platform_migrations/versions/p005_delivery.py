"""Scheduled notification authorization and durable local-date claims."""

from alembic import op

revision = "p005_delivery"
down_revision = "p004_admin_users"
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE notifications.delivery_state (
            owner_id text PRIMARY KEY REFERENCES identity.users(id) ON DELETE CASCADE,
            last_reminder_date date, last_nudge_date date
        )""",
        "ALTER TABLE notifications.delivery_state ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE notifications.delivery_state FORCE ROW LEVEL SECURITY",
        """CREATE POLICY runtime_owner ON notifications.delivery_state TO opengym_api_runtime
            USING(owner_id=nullif(current_setting('app.owner_id',true),''))
            WITH CHECK(owner_id=nullif(current_setting('app.owner_id',true),''))""",
        "GRANT SELECT,INSERT,UPDATE ON notifications.delivery_state TO opengym_api_runtime",
        "GRANT SELECT(disabled) ON identity.users TO opengym_notifications_executor",
        "GRANT USAGE ON SCHEMA training TO opengym_notifications_executor",
        "GRANT SELECT ON training.documents TO opengym_notifications_executor",
        """CREATE POLICY notification_owner ON training.documents TO opengym_notifications_executor
            USING(owner_id=nullif(current_setting('app.owner_id',true),''))""",
        """CREATE FUNCTION notifications.delivery_candidates(at timestamptz)
        RETURNS TABLE(owner_id text) LANGUAGE sql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
            SELECT u.id FROM identity.users u WHERE NOT u.disabled
                AND at IS NOT NULL AND isfinite(at)
                AND EXISTS(SELECT FROM notifications.subscriptions s WHERE s.owner_id=u.id)
            ORDER BY u.id COLLATE "C"
        $$""",
        """CREATE FUNCTION notifications.lock_delivery_owner(owner text)
        RETURNS TABLE(owner_id text) LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $$
        DECLARE previous text:=current_setting('app.owner_id',true);
        BEGIN
            PERFORM u.id FROM identity.users u WHERE u.id=owner AND NOT u.disabled FOR UPDATE;
            IF NOT FOUND THEN RETURN; END IF;
            PERFORM set_config('app.owner_id',owner,true);
            IF NOT EXISTS(SELECT FROM notifications.subscriptions s WHERE s.owner_id=owner)
                OR NOT EXISTS(SELECT FROM training.documents d WHERE d.owner_id=owner
                    AND d.document #> '{reminder,on}' IS NOT NULL
                    AND d.document #> '{reminder,on}' NOT IN ('null','false','0','""'))
            THEN PERFORM set_config('app.owner_id',coalesce(previous,''),true); RETURN; END IF;
            RETURN QUERY SELECT owner;
        END $$""",
    ]
    for signature in ("delivery_candidates(timestamptz)", "lock_delivery_owner(text)"):
        statements += [
            f"REVOKE ALL ON FUNCTION notifications.{signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION notifications.{signature} TO opengym_api_runtime",
            "GRANT CREATE ON SCHEMA notifications TO opengym_notifications_executor",
            f"ALTER FUNCTION notifications.{signature} OWNER TO opengym_notifications_executor",
            "REVOKE CREATE ON SCHEMA notifications FROM opengym_notifications_executor",
        ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
