import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import pg from 'pg';

// Loaded only after run.mjs validates the disposable target and pinned runtime.
const connection = { host: 'foundation-db', port: 5432, database: 'foundation_test',
  user: 'foundation_bootstrap', password: 'synthetic-foundation-only', ssl: false,
  connectionTimeoutMillis: 2_000, query_timeout: 2_000, statement_timeout: 2_000 };
const processes = new WeakMap();

function launch(t, args, hold = false) {
  const child = spawn(process.execPath, ['migrate.mjs', ...args], {
    env: { ...process.env, FOUNDATION_MIGRATION_HOLD: hold ? '1' : '0' },
    stdio: ['ignore', 'pipe', 'pipe', 'ipc'], timeout: 8_000, killSignal: 'SIGKILL',
  });
  let output = '';
  const messages = [];
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { output += data; });
  const locked = Promise.withResolvers();
  child.on('message', message => {
    messages.push(message);
    if (message?.event === 'migration-locked') locked.resolve(message);
  });
  const done = new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (code, signal) => resolve({ code, signal, output, messages }));
  }).then(result => {
    if (/synthetic-(?:foundation|migrator|runtime)-only|postgres(?:ql)?:\/\//i.test(result.output)) {
      throw new Error('Unsafe migration diagnostics');
    }
    return result;
  });
  if (!processes.has(t)) processes.set(t, []);
  processes.get(t).push({ child, done });
  return {
    child, done,
    async waitForLock() {
      return Promise.race([locked.promise, done.then(result => {
        assert.equal(result.code, 0, result.output);
        assert.fail('migration process exited without the fixture signal proving an acquired lock');
      })]);
    },
  };
}

async function success(t, args) {
  const result = await launch(t, args).done;
  assert.equal(result.signal, null, 'the migration process must terminate naturally');
  assert.equal(result.code, 0, result.output);
}

async function fixture(t, controlled = false) {
  const directory = await mkdtemp(join(tmpdir(), 'foundation-migrations-'));
  const schema = `foundation_probe_${randomBytes(8).toString('hex')}`;
  const db = new pg.Client(connection);
  await db.connect();
  t.after(async () => {
    // Stop only this test's children before dropping a schema they might still lock.
    const children = processes.get(t) ?? [];
    for (const { child } of children) {
      if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
    }
    try { await Promise.all(children.map(({ done }) => done)); }
    finally {
      try { await db.query(`DROP SCHEMA IF EXISTS "${schema}" CASCADE`); }
      finally { await db.end(); await rm(directory, { recursive: true, force: true }); }
    }
  });
  const migrations = controlled ? [[ '001-held.cjs', `
exports.up = async pgm => {
  await pgm.db.query('CREATE TABLE held_probe (value integer NOT NULL)');
  if (process.env.FOUNDATION_MIGRATION_HOLD === '1') {
    const [state] = await pgm.db.select("SELECT pg_backend_pid() AS pid, EXISTS (SELECT 1 FROM pg_locks WHERE pid = pg_backend_pid() AND locktype = 'advisory' AND granted) AS locked");
    if (!state.locked) throw new Error('Migration entered without an advisory lock');
    const release = new Promise(resolve => process.once('message', message => {
      if (message?.event === 'release-migration') resolve();
    }));
    process.send({ event: 'migration-locked', pid: state.pid });
    await release;
  }
  pgm.sql('INSERT INTO held_probe VALUES (42)');
};
` ]] : [
    ['001-probe.cjs', "exports.up = pgm => pgm.sql('CREATE TABLE probe (id integer PRIMARY KEY)');\n"],
    ['002-detail.cjs', "exports.up = pgm => pgm.sql('ALTER TABLE probe ADD COLUMN detail text');\n"],
  ];
  for (const [name, source] of migrations) {
    const file = join(directory, name);
    await writeFile(file, source);
    const syntax = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' });
    assert.equal(syntax.status, 0, syntax.stderr);
  }
  return { db, schema, args: ['up', directory, schema] };
}

async function history(db, schema) {
  const { rows: [row] } = await db.query('SELECT to_regclass($1) AS table_name', [`${schema}.pgmigrations`]);
  if (row.table_name === null) return [];
  return (await db.query(`SELECT name FROM "${schema}".pgmigrations ORDER BY id`)).rows.map(row => row.name);
}

test('committed Foundation migration is infrastructure only and reruns without replay', { timeout: 15_000 }, async t => {
  const { db } = await fixture(t);
  await success(t, ['bootstrap']);
  await success(t, ['bootstrap']);
  await success(t, ['up']);
  await success(t, ['up']);
  assert.deepEqual(await history(db, 'foundation'), ['001-foundation']);
  const schema = await db.query("SELECT pg_get_userbyid(nspowner) AS owner, has_schema_privilege('foundation_runtime', oid, 'USAGE') AS usage, has_schema_privilege('foundation_runtime', oid, 'CREATE') AS create FROM pg_namespace WHERE nspname = 'foundation'");
  assert.deepEqual(schema.rows, [{ owner: 'foundation_migrator', usage: true, create: false }]);
  const tables = await db.query("SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'foundation'");
  assert.deepEqual(tables.rows, [{ tablename: 'pgmigrations', tableowner: 'foundation_migrator' }]);
  assert.equal((await db.query("SELECT has_table_privilege('foundation_runtime', 'foundation.pgmigrations', 'INSERT, UPDATE, DELETE, TRUNCATE') AS writes")).rows[0].writes, false);
});

test('empty database and an applied test prefix converge to one unreplayed history', { timeout: 20_000 }, async t => {
  const empty = await fixture(t);
  const prefix = await fixture(t);
  await success(t, ['bootstrap']);
  await success(t, empty.args);
  await success(t, [...prefix.args, '1']);
  const before = await history(prefix.db, prefix.schema);
  await success(t, prefix.args);
  await success(t, empty.args);
  assert.deepEqual(before, ['001-probe'], 'the prefix must actually have been applied');
  for (const item of [empty, prefix]) {
    assert.deepEqual(await history(item.db, item.schema), ['001-probe', '002-detail']);
    const columns = await item.db.query('SELECT column_name FROM information_schema.columns WHERE table_schema = $1 AND table_name = $2 ORDER BY ordinal_position', [item.schema, 'probe']);
    assert.deepEqual(columns.rows.map(row => row.column_name), ['id', 'detail']);
  }
});

test('bootstrap separates role attributes, memberships, ownership and effective runtime privileges', { timeout: 15_000 }, async t => {
  const { db, schema, args } = await fixture(t);
  await success(t, ['bootstrap']);
  await success(t, args);
  const roles = await db.query("SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolinherit FROM pg_roles WHERE rolname IN ('foundation_runtime', 'foundation_migrator') ORDER BY rolname");
  assert.deepEqual(roles.rows, ['foundation_migrator', 'foundation_runtime'].map(rolname => ({
    rolname, rolcanlogin: true, rolsuper: false, rolbypassrls: false,
    rolcreatedb: false, rolcreaterole: false, rolreplication: false, rolinherit: false,
  })));
  assert.equal((await db.query("SELECT count(*)::integer AS count FROM pg_auth_members WHERE member IN (SELECT oid FROM pg_roles WHERE rolname IN ('foundation_runtime', 'foundation_migrator'))")).rows[0].count, 0);
  assert.deepEqual((await db.query(`SELECT pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname = $1`, [schema])).rows,
    [{ owner: 'foundation_migrator' }]);
  for (const sql of ["SELECT count(*)::integer AS count FROM pg_namespace WHERE nspowner = 'foundation_runtime'::regrole",
    "SELECT count(*)::integer AS count FROM pg_class WHERE relowner = 'foundation_runtime'::regrole",
    "SELECT count(*)::integer AS count FROM pg_database WHERE datdba = 'foundation_runtime'::regrole"]) {
    assert.equal((await db.query(sql)).rows[0].count, 0, 'runtime must not own database/schema/relations');
  }
  // Give genuine DML and schema visibility so DDL denial is not just missing USAGE.
  await db.query(`GRANT USAGE ON SCHEMA "${schema}" TO foundation_runtime`);
  await db.query(`GRANT SELECT, INSERT, UPDATE, DELETE ON "${schema}".probe TO foundation_runtime`);
  const runtime = new pg.Client({ ...connection, user: 'foundation_runtime', password: 'synthetic-runtime-only' });
  await runtime.connect();
  t.after(() => runtime.end());
  assert.equal((await runtime.query('SELECT current_user AS name')).rows[0].name, 'foundation_runtime');
  assert.deepEqual((await runtime.query("SELECT has_database_privilege(current_database(), 'CONNECT') AS connect, has_database_privilege(current_database(), 'CREATE') AS create, has_database_privilege(current_database(), 'TEMP') AS temp, has_schema_privilege('public', 'CREATE') AS public_create")).rows,
    [{ connect: true, create: false, temp: false, public_create: false }]);
  await runtime.query(`INSERT INTO "${schema}".probe (id) VALUES (42)`);
  assert.deepEqual((await runtime.query(`SELECT id FROM "${schema}".probe`)).rows, [{ id: 42 }]);
  for (const sql of [`CREATE TABLE "${schema}".forbidden (id integer)`,
    `ALTER TABLE "${schema}".probe ADD COLUMN forbidden integer`, `DROP TABLE "${schema}".probe`,
    `TRUNCATE "${schema}".probe`, `ALTER SCHEMA "${schema}" RENAME TO foundation_forbidden`,
    `DROP SCHEMA "${schema}" CASCADE`, `CREATE SCHEMA foundation_forbidden`,
    'CREATE TABLE public.foundation_forbidden (id integer)', 'CREATE TEMP TABLE foundation_forbidden (id integer)',
    'SET ROLE foundation_migrator', 'SET ROLE foundation_bootstrap',
    'ALTER ROLE foundation_runtime SUPERUSER', 'GRANT foundation_migrator TO foundation_runtime',
    `INSERT INTO "${schema}".pgmigrations (name, run_on) VALUES ('fake', now())`]) {
    await assert.rejects(runtime.query(sql), { code: '42501' });
  }
  assert.deepEqual((await runtime.query(`SELECT id FROM "${schema}".probe`)).rows, [{ id: 42 }]);
  assert.deepEqual(await history(db, schema), ['001-probe', '002-detail']);
});

test('a real SQL failure rolls back all pending work, preserves the applied prefix and reruns unchanged', { timeout: 20_000 }, async t => {
  const { db, schema, args } = await fixture(t);
  await success(t, ['bootstrap']);
  await success(t, [...args, '1']);
  await db.query(`INSERT INTO "${schema}".probe (id) VALUES (7)`);
  const file = join(args[1], '003-fail.cjs');
  await writeFile(file, `exports.up = async pgm => {
    const [state] = await pgm.db.select('SELECT pg_backend_pid() AS pid');
    await pgm.db.query('CREATE TABLE failed_probe (value integer NOT NULL)');
    await pgm.db.query('INSERT INTO failed_probe VALUES (42)');
    try { await pgm.db.query('INSERT INTO probe (id) VALUES (7)'); }
    catch (error) {
      process.send({ event: 'migration-sql-error', code: error.code, pid: state.pid });
      throw error;
    }
  };\n`);
  const syntax = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' });
  assert.equal(syntax.status, 0, syntax.stderr);
  const failed = await launch(t, args).done;
  assert.equal(failed.signal, null, 'SQL failure must close and exit without a timeout kill');
  assert.equal(failed.code, 1);
  assert.equal(failed.output.trim(), 'Foundation migration failed');
  assert.equal(failed.messages.length, 1);
  const [error] = failed.messages;
  assert.equal(error.event, 'migration-sql-error');
  assert.equal(error.code, '23505', 'the failure must be PostgreSQL unique_violation, not setup/import');
  assert.ok(Number.isInteger(error.pid));
  assert.deepEqual(await history(db, schema), ['001-probe']);
  assert.equal((await db.query('SELECT to_regclass($1) AS name', [`${schema}.failed_probe`])).rows[0].name, null);
  assert.deepEqual((await db.query('SELECT column_name FROM information_schema.columns WHERE table_schema = $1 AND table_name = $2 ORDER BY ordinal_position', [schema, 'probe'])).rows,
    [{ column_name: 'id' }], 'the preceding pending ALTER must also roll back');
  assert.deepEqual((await db.query(`SELECT id FROM "${schema}".probe`)).rows, [{ id: 7 }]);
  assert.equal((await db.query('SELECT count(*)::integer AS count FROM pg_stat_activity WHERE pid = $1', [error.pid])).rows[0].count, 0);
  assert.equal((await db.query("SELECT count(*)::integer AS count FROM pg_locks WHERE pid = $1 AND locktype = 'advisory'", [error.pid])).rows[0].count, 0);
  // Remove only the input conflict; do not edit the failed file or migration history.
  await db.query(`DELETE FROM "${schema}".probe WHERE id = 7`);
  await success(t, args);
  await success(t, args);
  assert.deepEqual(await history(db, schema), ['001-probe', '002-detail', '003-fail']);
  assert.deepEqual((await db.query(`SELECT value FROM "${schema}".failed_probe`)).rows, [{ value: 42 }]);
  assert.deepEqual((await db.query(`SELECT id, detail FROM "${schema}".probe`)).rows, [{ id: 7, detail: null }]);
});

for (const mode of ['concurrent', 'process', 'connection']) {
  test({ concurrent: 'a second process fails while the first holds the migration lock; history records it once',
    process: 'interrupted locked migration leaves no partial work and can be rerun',
    connection: 'terminated database connection rolls back, releases its lock and permits a clean rerun' }[mode],
  { timeout: 20_000 }, async t => {
    const { db, schema, args } = await fixture(t, true);
    await success(t, ['bootstrap']);
    const first = launch(t, args, true);
    const signal = await first.waitForLock();
    assert.ok(Number.isInteger(signal.pid));
    assert.deepEqual((await db.query('SELECT usename, datname FROM pg_stat_activity WHERE pid = $1', [signal.pid])).rows,
      [{ usename: 'foundation_migrator', datname: 'foundation_test' }]);
    assert.equal((await db.query("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid = $1 AND locktype = 'advisory' AND granted) AS held", [signal.pid])).rows[0].held, true);
    if (mode !== 'concurrent') {
      if (mode === 'process') first.child.kill('SIGTERM');
      else {
        assert.equal((await db.query('SELECT pg_terminate_backend($1, 1000) AS terminated', [signal.pid])).rows[0].terminated, true);
        // Release only the fixture's JavaScript gate; the database session is already dead.
        first.child.send({ event: 'release-migration' });
      }
      const result = await first.done;
      assert.equal(result.signal, mode === 'process' ? 'SIGTERM' : null);
      if (mode === 'connection') {
        assert.equal(result.code, 1, 'connection failure must exit explicitly, not hang until SIGKILL');
        assert.match(result.output, /Foundation migration failed/);
        assert.doesNotMatch(result.output, /synthetic-(?:foundation|migrator|runtime)-only|postgres(?:ql)?:\/\/|INSERT INTO|CREATE TABLE/i);
      }
      assert.deepEqual(await history(db, schema), []);
      assert.equal((await db.query('SELECT to_regclass($1) AS name', [`${schema}.held_probe`])).rows[0].name, null);
      assert.equal((await db.query("SELECT count(*)::integer AS count FROM pg_locks WHERE pid = $1 AND locktype = 'advisory' AND granted", [signal.pid])).rows[0].count, 0);
      await success(t, args);
    } else {
      const second = await launch(t, args).done;
      assert.equal(second.signal, null);
      assert.equal(second.code, 1, 'competing runner must fail explicitly, not apply or time out');
      assert.equal(second.output.trim(), 'Foundation migration failed');
      assert.deepEqual(await history(db, schema), []);
      first.child.send({ event: 'release-migration' });
      const result = await first.done;
      assert.equal(result.code, 0, result.output);
      assert.equal(result.signal, null);
      await success(t, args);
    }
    assert.deepEqual(await history(db, schema), ['001-held']);
    assert.deepEqual((await db.query(`SELECT value FROM "${schema}".held_probe`)).rows, [{ value: 42 }]);
    assert.equal((await db.query('SELECT count(*)::integer AS count FROM pg_stat_activity WHERE pid = $1', [signal.pid])).rows[0].count, 0);
    assert.equal((await db.query("SELECT count(*)::integer AS count FROM pg_locks WHERE pid = $1 AND locktype = 'advisory'", [signal.pid])).rows[0].count, 0);
  });
}
