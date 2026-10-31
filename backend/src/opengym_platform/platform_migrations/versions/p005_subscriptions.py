"""Owner subscriptions and the bounded global endpoint transfer."""

from alembic import op

revision = "p005_subscriptions"
down_revision = "p003_coach_client"
branch_labels = None
depends_on = None


def upgrade():
    for statement in (
        "CREATE SCHEMA notifications AUTHORIZATION opengym_schema_owner",
        "REVOKE ALL ON SCHEMA notifications FROM PUBLIC",
        "GRANT USAGE ON SCHEMA notifications TO opengym_api_runtime,opengym_notifications_executor",
        """CREATE TABLE notifications.subscriptions (
            endpoint text PRIMARY KEY, owner_id text NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
            p256dh text NOT NULL CHECK(length(p256dh)>0), auth text NOT NULL CHECK(length(auth)>0),
            device_id text CHECK(device_id ~ '^[A-Za-z0-9_-]{8,64}$'),
            created_at timestamptz NOT NULL CHECK(isfinite(created_at))
        )""",
        "CREATE INDEX subscriptions_owner_created ON notifications.subscriptions(owner_id,created_at)",
        "ALTER TABLE notifications.subscriptions ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE notifications.subscriptions FORCE ROW LEVEL SECURITY",
        """CREATE POLICY runtime_owner ON notifications.subscriptions TO opengym_api_runtime
            USING(owner_id=nullif(current_setting('app.owner_id',true),''))
            WITH CHECK(owner_id=nullif(current_setting('app.owner_id',true),''))""",
        "CREATE POLICY endpoint_transfer ON notifications.subscriptions TO opengym_notifications_executor USING(true) WITH CHECK(true)",
        "GRANT SELECT,DELETE ON notifications.subscriptions TO opengym_api_runtime",
        "GRANT SELECT,INSERT,UPDATE,DELETE ON notifications.subscriptions TO opengym_notifications_executor",
        "GRANT USAGE ON SCHEMA identity TO opengym_notifications_executor",
        "GRANT SELECT(id),UPDATE(id) ON identity.users TO opengym_notifications_executor",
        "CREATE POLICY subscription_locks ON identity.users TO opengym_notifications_executor USING(true) WITH CHECK(true)",
        "SET ROLE opengym_identity_executor",
        "GRANT EXECUTE ON FUNCTION identity.lock_actor(text,bigint,timestamptz) TO opengym_notifications_executor",
        "SET ROLE opengym_schema_owner",
        """CREATE FUNCTION notifications.upsert_subscription(actor text,sv bigint,exp timestamptz,
            endpoint text,p256dh text,auth text,device_id text,created_at timestamptz)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
        DECLARE previous notifications.subscriptions%ROWTYPE;
        BEGIN
            PERFORM pg_advisory_xact_lock(728324);
            SELECT s.* INTO previous FROM notifications.subscriptions s WHERE s.endpoint=$4;
            PERFORM u.id FROM identity.users u WHERE u.id IN (actor,previous.owner_id)
                ORDER BY u.id COLLATE "C" FOR UPDATE;
            IF NOT EXISTS(SELECT FROM identity.lock_actor(actor,sv,exp)) THEN RETURN false; END IF;
            SELECT s.* INTO previous FROM notifications.subscriptions s WHERE s.endpoint=$4 FOR UPDATE;
            INSERT INTO notifications.subscriptions AS s(endpoint,owner_id,p256dh,auth,device_id,created_at)
                VALUES($4,actor,$5,$6,CASE WHEN $7 ~ '^[A-Za-z0-9_-]{8,64}$' THEN $7 ELSE previous.device_id END,
                    coalesce(previous.created_at,$8))
                ON CONFLICT ON CONSTRAINT subscriptions_pkey DO UPDATE SET
                    owner_id=excluded.owner_id,p256dh=excluded.p256dh,auth=excluded.auth,device_id=excluded.device_id;
            DELETE FROM notifications.subscriptions s WHERE s.endpoint IN (
                SELECT n.endpoint FROM notifications.subscriptions n WHERE n.owner_id=actor AND n.endpoint<>$4
                ORDER BY n.created_at DESC,n.endpoint COLLATE "C" DESC OFFSET 19);
            RETURN true;
        END $$""",
        "REVOKE ALL ON FUNCTION notifications.upsert_subscription(text,bigint,timestamptz,text,text,text,text,timestamptz) FROM PUBLIC",
        "GRANT EXECUTE ON FUNCTION notifications.upsert_subscription(text,bigint,timestamptz,text,text,text,text,timestamptz) TO opengym_api_runtime",
        "GRANT CREATE ON SCHEMA notifications TO opengym_notifications_executor",
        "ALTER FUNCTION notifications.upsert_subscription(text,bigint,timestamptz,text,text,text,text,timestamptz) OWNER TO opengym_notifications_executor",
        "REVOKE CREATE ON SCHEMA notifications FROM opengym_notifications_executor",
    ):
        op.execute(statement)


def downgrade():
    raise RuntimeError("PLATFORM_MIGRATION_FORWARD_ONLY")
