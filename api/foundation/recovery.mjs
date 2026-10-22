import { spawnSync } from 'node:child_process';
import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';
import { lstat, realpath, readdir, readFile, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';

const [action, first, second, third, ...extra] = process.argv.slice(2);
const roles = ['foundation_migrator', 'foundation_runtime', 'foundation_training'];
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const connection = { host: 'foundation-db', port: 5432, database: 'foundation_test',
  user: 'foundation_bootstrap', password: 'synthetic-foundation-only', ssl: false,
  connectionTimeoutMillis: 2_000, query_timeout: 5_000, statement_timeout: 5_000, lock_timeout: 2_000 };

async function privatePath(path, directory = false) {
  const info = await lstat(path);
  if (await realpath(path) !== path || info.uid !== process.getuid() || (info.mode & 0o077)
    || (directory ? !info.isDirectory() : !info.isFile() || info.nlink !== 1)) throw new Error('Invalid recovery arguments');
}

async function bundle(directory, empty = false) {
  await privatePath(dirname(directory), true);
  await privatePath(directory, true);
  const names = (await readdir(directory)).sort();
  if (JSON.stringify(names) !== JSON.stringify(empty ? [] : ['backup.enc', 'manifest.json'])) throw new Error('Invalid recovery arguments');
  if (!empty) for (const name of names) await privatePath(join(directory, name));
}

// shortcut: dumps stay in memory (32 MiB tool output), use streaming before larger fixtures.
// No inherited libpq service, DSN, options, SSL overrides or subprocess diagnostics.
function tool(name, args, database = 'foundation_test', input) {
  const result = spawnSync(`/usr/lib/postgresql/18/bin/${name}`, args, {
    env: { PATH: '/usr/bin:/bin', LANG: 'C', HOME: '/nonexistent',
      PGHOST: connection.host, PGPORT: '5432', PGDATABASE: database,
      PGUSER: connection.user, PGPASSWORD: connection.password, PGSSLMODE: 'disable',
      PGCONNECT_TIMEOUT: '2', PGOPTIONS: '-c statement_timeout=15000 -c lock_timeout=2000' },
    input, timeout: 20_000, killSignal: 'SIGKILL', maxBuffer: 32 * 1024 * 1024,
  });
  if (result.error || result.signal || result.status !== 0 || result.stderr.length) throw new Error('Foundation recovery failed');
  return result.stdout;
}

async function restrictedRoles(db) {
  const result = await db.query(`SELECT rolname FROM pg_roles WHERE rolname = ANY($1::text[])
    AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
    AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit ORDER BY rolname`, [roles]);
  const memberships = await db.query('SELECT 1 FROM pg_auth_members WHERE member IN (SELECT oid FROM pg_roles WHERE rolname = ANY($1::text[]))', [roles]);
  if (JSON.stringify(result.rows.map(row => row.rolname)) !== JSON.stringify(roles) || memberships.rowCount) throw new Error('Foundation recovery failed');
}

try {
  if (process.env.PGHOST !== connection.host || process.env.PGPORT !== '5432'
    || process.env.PGDATABASE !== connection.database || process.env.PGUSER !== connection.user
    || process.env.PGPASSWORD !== connection.password) throw new Error('Refusing non-test database target');
  const directoryPattern = /^\/tmp\/foundation-recovery-[A-Za-z0-9]+\/(backup|transfer)$/;
  const keyPattern = /^\/tmp\/foundation-recovery-[A-Za-z0-9]+\/keys\/(key|wrong)\.bin$/;
  if (extra.length || !directoryPattern.test(first ?? '')
    || action === 'backup' && (!keyPattern.test(second ?? '') || !/^[a-f0-9]{40}$/.test(third ?? ''))
    || action === 'copy' && (!directoryPattern.test(second ?? '') || third !== undefined || first === second)
    || action === 'restore' && (!keyPattern.test(second ?? '') || third === undefined)
    || !['backup', 'copy', 'restore'].includes(action)) throw new Error('Invalid recovery arguments');
  if (action === 'restore' && !/^foundation_restore_[a-f0-9]{16}$/.test(third)) throw new Error('Refusing non-test restore target');
  process.umask(0o077);
  await bundle(first, action === 'backup');
  if (action === 'copy') {
    await bundle(second, true);
    for (const name of ['backup.enc', 'manifest.json']) {
      await writeFile(join(second, name), await readFile(join(first, name)), { mode: 0o600, flag: 'wx' });
    }
  } else {
    await privatePath(dirname(dirname(second)), true);
    await privatePath(dirname(second), true);
    await privatePath(second);
    const key = await readFile(second);
    if (key.length !== 32) throw new Error('Recovery verification failed');
    const tools = {};
    for (const name of ['pg_dump', 'pg_restore']) {
      if (!new RegExp(`^${name} \\(PostgreSQL\\) 18\\.6(?: |\\r?\\n|$)`).test(tool(name, ['--version']).toString())) throw new Error('Foundation recovery failed');
      tools[name] = '18.6';
    }
    const { default: pg } = await import('pg');
    if (action === 'backup') {
      const db = new pg.Client(connection);
      let dump, metadata;
      try {
        await db.connect();
        await restrictedRoles(db);
        await db.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
        const version = (await db.query('SHOW server_version')).rows[0].server_version.split(' ')[0];
        if (version !== '18.6') throw new Error('Foundation recovery failed');
        const snapshot = (await db.query('SELECT pg_export_snapshot() AS id')).rows[0].id;
        const history = (await db.query('SELECT name FROM foundation.pgmigrations ORDER BY id')).rows.map(row => row.name);
        const fixtures = (await db.query("SELECT nspname FROM pg_namespace WHERE nspname ~ '^foundation_isolation_[a-f0-9]{16}$' ORDER BY nspname")).rows;
        const owners = new Set();
        for (const { nspname } of fixtures) {
          for (const row of (await db.query(`SELECT DISTINCT owner_id FROM "${nspname}".owner_probe`)).rows) owners.add(row.owner_id);
        }
        dump = tool('pg_dump', ['--format=custom', '--no-password', `--snapshot=${snapshot}`]);
        metadata = Buffer.from(JSON.stringify({ formatVersion: 1, applicationRevision: third,
          schemaVersion: history, databaseVersion: version, tools, sourceDatabase: connection.database,
          owners: [...owners].sort(), roles, cipher: 'aes-256-gcm', dumpSha256: hash(dump) }));
        await db.query('COMMIT');
      } finally { await db.end(); }
      const nonce = randomBytes(12), cipher = createCipheriv('aes-256-gcm', key, nonce);
      cipher.setAAD(metadata);
      const encrypted = Buffer.concat([cipher.update(dump), cipher.final()]);
      await writeFile(join(first, 'backup.enc'), Buffer.concat([nonce, cipher.getAuthTag(), encrypted]), { flag: 'wx', mode: 0o600 });
      await writeFile(join(first, 'manifest.json'), metadata, { flag: 'wx', mode: 0o600 });
    } else {
      let dump;
      try {
        const metadata = await readFile(join(first, 'manifest.json'));
        const bytes = await readFile(join(first, 'backup.enc'));
        const decipher = createDecipheriv('aes-256-gcm', key, bytes.subarray(0, 12));
        decipher.setAAD(metadata); decipher.setAuthTag(bytes.subarray(12, 28));
        dump = Buffer.concat([decipher.update(bytes.subarray(28)), decipher.final()]);
        const manifest = JSON.parse(metadata);
        if (manifest.formatVersion !== 1 || manifest.sourceDatabase !== connection.database
          || manifest.databaseVersion !== '18.6' || manifest.cipher !== 'aes-256-gcm'
          || JSON.stringify(manifest.roles) !== JSON.stringify(roles)
          || JSON.stringify(manifest.tools) !== JSON.stringify(tools)
          || !/^[a-f0-9]{40}$/.test(manifest.applicationRevision)
          || !Array.isArray(manifest.schemaVersion) || !Array.isArray(manifest.owners)
          || manifest.dumpSha256 !== hash(dump) || dump.subarray(0, 5).toString() !== 'PGDMP') throw new Error();
        tool('pg_restore', ['--list'], third, dump);
      } catch { throw new Error('Recovery verification failed'); }
      const db = new pg.Client({ ...connection, database: third });
      try {
        await db.connect();
        await db.query('SELECT pg_advisory_lock(728322)');
        const target = (await db.query('SELECT pg_get_userbyid(datdba) AS owner, datacl IS NULL AS pristine FROM pg_database WHERE datname = current_database()')).rows[0];
        const schemas = (await db.query("SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN ('information_schema', 'public')")).rowCount;
        const objects = (await db.query(`SELECT 1 FROM (
          SELECT relnamespace AS ns FROM pg_class UNION ALL
          SELECT pronamespace FROM pg_proc UNION ALL SELECT typnamespace FROM pg_type
        ) objects JOIN pg_namespace n ON n.oid=objects.ns
          WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' LIMIT 1`)).rowCount;
        if (target.owner !== connection.user || !target.pristine || schemas || objects) throw new Error('Refusing non-test restore target');
        await restrictedRoles(db);
        tool('pg_restore', ['--no-password', '--single-transaction', '--exit-on-error', '--dbname', third], third, dump);
        // pg_restore without --create preserves the chosen target; database ACLs are explicit.
        await db.query(`BEGIN;
          REVOKE ALL ON DATABASE "${third}" FROM PUBLIC;
          GRANT CONNECT, CREATE ON DATABASE "${third}" TO foundation_migrator;
          GRANT CONNECT ON DATABASE "${third}" TO foundation_runtime, foundation_training;
          COMMIT;`);
      } finally { await db.end(); }
    }
  }
  console.log(JSON.stringify({ event: `recovery-${action}-complete` }));
} catch (error) {
  console.error(['Refusing non-test database target', 'Invalid recovery arguments',
    'Refusing non-test restore target', 'Recovery verification failed'].includes(error.message)
    ? error.message : 'Foundation recovery failed');
  process.exitCode = 1;
}
