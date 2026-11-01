-- Explicit privileged setup, not API startup or a schema migration.
-- Run on the selected instance as its bootstrap owner, then use psql \password
-- to set a separate secret for opengym_backup. Never grant this role to runtime.
BEGIN;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opengym_backup') THEN
        CREATE ROLE opengym_backup LOGIN;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'opengym_backup'
        AND (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication))
        OR EXISTS (SELECT FROM pg_auth_members WHERE roleid = 'opengym_backup'::regrole
            OR (member = 'opengym_backup'::regrole AND roleid <> 'pg_read_all_stats'::regrole)) THEN
        RAISE EXCEPTION 'BACKUP_ROLE_UNSAFE';
    END IF;
END $$;
ALTER ROLE opengym_backup NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT pg_read_all_stats TO opengym_backup WITH INHERIT TRUE, SET FALSE;
DO $$
DECLARE s text; t record;
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO opengym_backup', current_database());
    FOREACH s IN ARRAY ARRAY['public','identity','training','coach','administration','notifications','audit'] LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO opengym_backup', s);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO opengym_backup', s);
        EXECUTE format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA %I TO opengym_backup', s);
    END LOOP;
    FOR t IN SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE c.relkind='r' AND c.relrowsecurity AND n.nspname = ANY(
            ARRAY['identity','training','coach','administration','notifications','audit']) LOOP
        IF NOT EXISTS (SELECT FROM pg_policies WHERE schemaname=t.nspname
            AND tablename=t.relname AND policyname='backup_read') THEN
            EXECUTE format('CREATE POLICY backup_read ON %I.%I FOR SELECT TO opengym_backup USING (true)', t.nspname, t.relname);
        END IF;
    END LOOP;
END $$;
COMMIT;
