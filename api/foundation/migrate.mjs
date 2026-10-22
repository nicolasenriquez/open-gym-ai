import { realpath } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

// Public credentials and fixed target belong only to the disposable Foundation stack.
const [action, directory, schema, count, ...extra] = process.argv.slice(2);
try {
  if (process.env.PGHOST !== 'foundation-db' || process.env.PGPORT !== '5432'
    || process.env.PGDATABASE !== 'foundation_test' || process.env.PGUSER !== 'foundation_bootstrap'
    || process.env.PGPASSWORD !== 'synthetic-foundation-only') throw new Error('Refusing non-test database target');
  if (extra.length || !['bootstrap', 'up'].includes(action)
    || (action === 'bootstrap' && directory !== undefined)
    || (action === 'up' && directory === undefined && (schema !== undefined || count !== undefined))
    || (action === 'up' && directory !== undefined && (!/^\/tmp\/foundation-migrations-[a-zA-Z0-9]+$/.test(directory)
      || !/^foundation_probe_[a-f0-9]{16}$/.test(schema ?? '')
      || (count !== undefined && (!/^[1-9][0-9]*$/.test(count) || !Number.isSafeInteger(Number(count))))))) {
    throw new Error('Invalid migration arguments');
  }
  if (directory && await realpath(directory) !== directory) throw new Error('Invalid migration arguments');
  const { default: pg } = await import('pg');
  const client = new pg.Client({ host: 'foundation-db', port: 5432, database: 'foundation_test',
    user: action === 'bootstrap' ? 'foundation_bootstrap' : 'foundation_migrator',
    password: action === 'bootstrap' ? process.env.PGPASSWORD : 'synthetic-migrator-only', ssl: false,
    connectionTimeoutMillis: 2_000, query_timeout: 5_000, statement_timeout: 5_000, lock_timeout: 2_000 });
  client.on('error', () => { console.error('Foundation connection failed'); process.exitCode = 1; });
  try {
    await client.connect();
    if (action === 'bootstrap') {
      await client.query(`BEGIN;
        SELECT pg_advisory_xact_lock(728321);
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'foundation_migrator') THEN
            CREATE ROLE foundation_migrator LOGIN PASSWORD 'synthetic-migrator-only';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'foundation_runtime') THEN
            CREATE ROLE foundation_runtime LOGIN PASSWORD 'synthetic-runtime-only';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'foundation_training') THEN
            CREATE ROLE foundation_training LOGIN PASSWORD 'synthetic-training-only';
          END IF;
        END $$;
        ALTER ROLE foundation_migrator NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
        ALTER ROLE foundation_runtime NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
        ALTER ROLE foundation_training NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
        REVOKE ALL ON DATABASE foundation_test FROM PUBLIC;
        REVOKE ALL ON SCHEMA public FROM PUBLIC;
        GRANT CONNECT, CREATE ON DATABASE foundation_test TO foundation_migrator;
        GRANT CONNECT ON DATABASE foundation_test TO foundation_runtime;
        GRANT CONNECT ON DATABASE foundation_test TO foundation_training;
        COMMIT;`);
      console.log(JSON.stringify({ event: 'bootstrap-complete' }));
    } else {
      const { runner } = await import('node-pg-migrate');
      const targetSchema = schema ?? 'foundation';
      const applied = await runner({ dbClient: client,
        dir: directory ?? fileURLToPath(new URL('./migrations/', import.meta.url)),
        schema: targetSchema, createSchema: true,
        migrationsSchema: targetSchema, migrationsTable: 'pgmigrations', direction: 'up',
        count: count === undefined ? undefined : Number(count), checkOrder: true,
        noLock: false, advisoryLockMode: 'fail', singleTransaction: true, fake: false,
        // Driver SQL/errors may contain credentials or payload; expose only a safe outcome.
        log: () => {} });
      console.log(JSON.stringify({ event: 'migrations-complete', applied: applied.length }));
    }
  } finally { await client.end(); }
} catch (error) {
  console.error(['Refusing non-test database target', 'Invalid migration arguments'].includes(error.message)
    ? error.message : 'Foundation migration failed');
  process.exitCode = 1;
}
