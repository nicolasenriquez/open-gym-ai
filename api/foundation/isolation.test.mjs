import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import test from 'node:test';
import pg from 'pg';
import { createDatabase } from './pool.mjs';
import { prepareIsolationFixture } from './isolation-fixture.mjs';

// run.mjs checks the disposable target and pinned runtime before loading this group.
const connection = { host: 'foundation-db', port: 5432, database: 'foundation_test', ssl: false,
  connectionTimeoutMillis: 2_000, query_timeout: 3_000, statement_timeout: 2_000 };
const pid = async db => (await db.query('SELECT pg_backend_pid() AS pid')).rows[0].pid;
const owner = async db => (await db.query("SELECT nullif(current_setting('app.owner_id', true), '') AS owner")).rows[0].owner;

async function fixture(t) {
  const bootstrap = spawnSync(process.execPath, ['migrate.mjs', 'bootstrap'], { encoding: 'utf8', timeout: 8_000 });
  assert.equal(bootstrap.signal, null);
  assert.equal(bootstrap.status, 0, 'disposable bootstrap must succeed before isolation assertions');
  assert.doesNotMatch(bootstrap.stdout + bootstrap.stderr, /synthetic-(?:foundation|migrator|runtime|training)-only|postgres(?:ql)?:\/\//i);
  const schema = `foundation_isolation_${randomBytes(8).toString('hex')}`;
  const migrator = new pg.Client({ ...connection, user: 'foundation_migrator', password: 'synthetic-migrator-only' });
  const db = createDatabase({ ...connection, user: 'foundation_runtime', password: 'synthetic-runtime-only',
    max: 1, idleTimeoutMillis: 10_000 });
  await migrator.connect();
  let runtimePid;
  t.after(async () => {
    try { await db.close(); }
    finally {
      try {
        await migrator.query(`DROP SCHEMA IF EXISTS "${schema}" CASCADE`);
        assert.equal((await migrator.query('SELECT to_regnamespace($1) AS name', [schema])).rows[0].name, null);
        if (runtimePid !== undefined) {
          assert.equal((await migrator.query('SELECT count(*)::integer AS count FROM pg_stat_activity WHERE pid = $1', [runtimePid])).rows[0].count, 0);
        }
        t.diagnostic('Fixture cleanup PASS: schema absent; runtime connection closed');
      }
      finally { await migrator.end(); }
    }
  });
  await prepareIsolationFixture(migrator, schema);
  const identity = await db.query('SELECT current_user AS name, current_database() AS db');
  assert.deepEqual(identity.rows, [{ name: 'foundation_runtime', db: 'foundation_test' }]);
  runtimePid = await pid(db);
  assert.deepEqual((await migrator.query('SELECT pg_get_userbyid(relowner) AS owner FROM pg_class WHERE oid = $1::regclass', [`${schema}.owner_probe`])).rows,
    [{ owner: 'foundation_migrator' }]);
  assert.deepEqual((await db.query("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).rows,
    [{ rolsuper: false, rolbypassrls: false }]);
  return { db, schema };
}

// Trusted server work sets context locally; owner_id in a row is not authentication.
async function asOwner(db, value, work) {
  return db.transaction(async tx => {
    if (value !== null) await tx.query("SELECT set_config('app.owner_id', $1, true)", [value]);
    return work(tx);
  });
}

for (const [label, value, expected, otherId] of [
  ['A', 'owner-a', [{ id: 1, owner_id: 'owner-a' }], 2],
  ['B', 'owner-b', [{ id: 2, owner_id: 'owner-b' }], 1],
  ['missing context', null, [], 1],
  ['empty context', '', [], 1],
]) {
  test(`${label}: reads are scoped by the database without an application WHERE filter`, { timeout: 15_000 }, async t => {
    const { db, schema } = await fixture(t);
    const result = await asOwner(db, value, async tx => ({ active: await owner(tx),
      rows: (await tx.query(`SELECT id, owner_id FROM "${schema}".owner_probe ORDER BY id`)).rows }));
    assert.equal(result.active, value || null, 'trusted local context must be installed before checking visibility');
    assert.deepEqual(result.rows, expected, `${label}: unauthorized rows must not be visible`);
  });

  test(`${label}: cross-owner UPDATE and DELETE affect no rows`, { timeout: 15_000 }, async t => {
    const { db, schema } = await fixture(t);
    const result = await asOwner(db, value, async tx => ({ active: await owner(tx),
      updated: (await tx.query(`UPDATE "${schema}".owner_probe SET note = 'crossed' WHERE id = $1`, [otherId])).rowCount,
      deleted: (await tx.query(`DELETE FROM "${schema}".owner_probe WHERE id = $1`, [otherId])).rowCount }));
    assert.equal(result.active, value || null);
    assert.deepEqual([result.updated, result.deleted], [0, 0], `${label}: unauthorized writes must affect no rows`);
  });
}

for (const value of ['owner-a', null, '']) {
  test(`${value ?? 'missing context'}: INSERT cannot claim owner B`, { timeout: 15_000 }, async t => {
    const { db, schema } = await fixture(t);
    await assert.rejects(asOwner(db, value, tx => tx.query(`INSERT INTO "${schema}".owner_probe VALUES (3, 'owner-b', 'forged')`)),
      /Database operation failed/, 'a foreign owner or missing context must reject INSERT');
  });
}

for (const mode of ['commit', 'rollback', 'SQL error']) {
  test(`same runtime connection after ${mode}: B and missing context inherit no A access`, { timeout: 15_000 }, async t => {
    const { db, schema } = await fixture(t);
    const before = await pid(db);
    let a;
    let wrote = false;
    const work = asOwner(db, 'owner-a', async tx => {
      a = { pid: await pid(tx), owner: await owner(tx) };
      wrote = (await tx.query(`INSERT INTO "${schema}".owner_probe VALUES (3, 'owner-a', 'transient-a')`)).rowCount === 1;
      if (mode === 'rollback') throw new Error('intentional rollback');
      if (mode === 'SQL error') await tx.query('SELECT 1 / 0');
    });
    if (mode === 'commit') await work;
    else await assert.rejects(work, /Database operation failed/);
    assert.equal(wrote, true, 'A must reach its authorized write before commit/rollback/error');
    assert.deepEqual(a, { pid: before, owner: 'owner-a' });
    assert.equal(await pid(db), before);
    assert.equal(await owner(db), null, 'A context must disappear before reuse');
    const b = await asOwner(db, 'owner-b', async tx => ({ pid: await pid(tx), owner: await owner(tx),
      rows: (await tx.query(`SELECT id, owner_id FROM "${schema}".owner_probe ORDER BY id`)).rows }));
    assert.equal(b.pid, before);
    assert.equal(b.owner, 'owner-b');
    assert.equal(await owner(db), null, 'B context must disappear before context-free reuse');
    const missing = await asOwner(db, null, async tx => ({ pid: await pid(tx), owner: await owner(tx),
      rows: (await tx.query(`SELECT id, owner_id FROM "${schema}".owner_probe ORDER BY id`)).rows }));
    assert.equal(missing.pid, before);
    assert.equal(missing.owner, null);
    const persisted = await asOwner(db, 'owner-a', async tx =>
      (await tx.query(`SELECT id FROM "${schema}".owner_probe WHERE id = 3`)).rows);
    assert.deepEqual(persisted, mode === 'commit' ? [{ id: 3 }] : [], 'commit must persist; rollback/error must not');
    assert.deepEqual({ b: b.rows, missing: missing.rows }, { b: [{ id: 2, owner_id: 'owner-b' }], missing: [] },
      'same-PID reuse must expose neither previous-owner data nor rows without context');
  });
}

test('Training-only login cannot access the owner fixture even with a known owner context', { timeout: 15_000 }, async t => {
  const { db, schema } = await fixture(t);
  const roles = await db.query("SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolinherit FROM pg_roles WHERE rolname = 'foundation_training'");
  assert.deepEqual(roles.rows, [{ rolname: 'foundation_training', rolcanlogin: true, rolsuper: false,
    rolbypassrls: false, rolcreatedb: false, rolcreaterole: false, rolreplication: false, rolinherit: false }]);
  assert.equal((await db.query("SELECT count(*)::integer AS count FROM pg_auth_members WHERE member = 'foundation_training'::regrole")).rows[0].count, 0);
  assert.deepEqual((await db.query("SELECT has_schema_privilege('foundation_training', $1, 'USAGE') AS usage, has_table_privilege('foundation_training', $2, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE') AS access", [schema, `${schema}.owner_probe`])).rows,
    [{ usage: false, access: false }]);
  const training = new pg.Client({ ...connection, user: 'foundation_training', password: 'synthetic-training-only' });
  await training.connect();
  t.after(() => training.end());
  assert.deepEqual((await training.query('SELECT current_user AS name, 42 AS value')).rows,
    [{ name: 'foundation_training', value: 42 }]);
  assert.deepEqual((await training.query("SELECT has_database_privilege(current_database(), 'CONNECT') AS connect, has_database_privilege(current_database(), 'CREATE') AS create, has_database_privilege(current_database(), 'TEMP') AS temp")).rows,
    [{ connect: true, create: false, temp: false }]);
  for (const sql of [`SELECT * FROM "${schema}".owner_probe`,
    `INSERT INTO "${schema}".owner_probe VALUES (3, 'owner-a', 'forbidden')`,
    `UPDATE "${schema}".owner_probe SET note = 'forbidden' WHERE id = 1`,
    `DELETE FROM "${schema}".owner_probe WHERE id = 1`]) {
    await training.query('BEGIN');
    try {
      await training.query("SELECT set_config('app.owner_id', $1, true)", ['owner-a']);
      await assert.rejects(training.query(sql), { code: '42501' });
    } finally { await training.query('ROLLBACK'); }
  }
  for (const role of ['foundation_runtime', 'foundation_migrator', 'foundation_bootstrap']) {
    await assert.rejects(training.query(`SET ROLE ${role}`), { code: '42501' });
  }
});

test('runtime may update its own row but cannot reassign ownership, TRUNCATE or elevate privileges', { timeout: 15_000 }, async t => {
  const { db, schema } = await fixture(t);
  const updated = await asOwner(db, 'owner-a', async tx =>
    (await tx.query(`UPDATE "${schema}".owner_probe SET note = 'own-update' WHERE id = 1 RETURNING id, owner_id, note`)).rows);
  assert.deepEqual(updated, [{ id: 1, owner_id: 'owner-a', note: 'own-update' }]);
  for (const sql of [`UPDATE "${schema}".owner_probe SET owner_id = 'owner-b' WHERE id = 1`,
    `TRUNCATE "${schema}".owner_probe`, 'SET LOCAL ROLE foundation_migrator',
    'SET LOCAL ROLE foundation_bootstrap', 'ALTER ROLE foundation_runtime BYPASSRLS',
    'GRANT foundation_migrator TO foundation_runtime']) {
    await assert.rejects(asOwner(db, 'owner-a', tx => tx.query(sql)), /Database operation failed/);
  }
  assert.deepEqual(await asOwner(db, 'owner-a', async tx =>
    (await tx.query(`SELECT id, owner_id, note FROM "${schema}".owner_probe`)).rows),
  [{ id: 1, owner_id: 'owner-a', note: 'own-update' }]);
  assert.deepEqual(await asOwner(db, 'owner-b', async tx =>
    (await tx.query(`SELECT id, owner_id, note FROM "${schema}".owner_probe`)).rows),
  [{ id: 2, owner_id: 'owner-b', note: 'initial-b' }]);
});

for (const [value, originalId, initialNote] of [['owner-a', 1, 'initial-a'], ['owner-b', 2, 'initial-b']]) {
  test(`${value}: authorized CRUD persists on the same runtime connection`, { timeout: 15_000 }, async t => {
    const { db, schema } = await fixture(t);
    const before = await pid(db);
    const created = await asOwner(db, value, async tx =>
      (await tx.query(`INSERT INTO "${schema}".owner_probe VALUES (3, $1, 'created') RETURNING id`, [value])).rows);
    assert.deepEqual(created, [{ id: 3 }]);
    assert.equal(await pid(db), before);
    assert.equal(await owner(db), null);
    const rows = await asOwner(db, value, async tx =>
      (await tx.query(`SELECT id, owner_id, note FROM "${schema}".owner_probe ORDER BY id`)).rows);
    assert.deepEqual(rows, [{ id: originalId, owner_id: value, note: initialNote },
      { id: 3, owner_id: value, note: 'created' }]);
    const changed = await asOwner(db, value, async tx =>
      (await tx.query(`UPDATE "${schema}".owner_probe SET note = 'updated' WHERE id = 3`)).rowCount);
    assert.equal(changed, 1);
    assert.deepEqual(await asOwner(db, value, async tx =>
      (await tx.query(`SELECT note FROM "${schema}".owner_probe WHERE id = 3`)).rows), [{ note: 'updated' }]);
    const deleted = await asOwner(db, value, async tx =>
      (await tx.query(`DELETE FROM "${schema}".owner_probe WHERE id = 3 RETURNING id`)).rows);
    assert.deepEqual(deleted, [{ id: 3 }]);
    assert.deepEqual(await asOwner(db, value, async tx =>
      (await tx.query(`SELECT id, owner_id, note FROM "${schema}".owner_probe ORDER BY id`)).rows),
    [{ id: originalId, owner_id: value, note: initialNote }]);
    assert.equal(await pid(db), before);
    assert.equal(await owner(db), null);
  });
}

test('owner B cannot INSERT as A or reassign its existing row to A', { timeout: 15_000 }, async t => {
  const { db, schema } = await fixture(t);
  for (const sql of [`INSERT INTO "${schema}".owner_probe VALUES (3, 'owner-a', 'forged')`,
    `UPDATE "${schema}".owner_probe SET owner_id = 'owner-a' WHERE id = 2`]) {
    await assert.rejects(asOwner(db, 'owner-b', tx => tx.query(sql)), /Database operation failed/);
  }
  assert.deepEqual(await asOwner(db, 'owner-b', async tx =>
    (await tx.query(`SELECT id, owner_id, note FROM "${schema}".owner_probe`)).rows),
  [{ id: 2, owner_id: 'owner-b', note: 'initial-b' }]);
});

test('runtime owns no fixture objects and has only the required data privileges', { timeout: 15_000 }, async t => {
  const { db, schema } = await fixture(t);
  assert.deepEqual((await db.query('SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolinherit FROM pg_roles WHERE rolname = current_user')).rows,
    [{ rolcanlogin: true, rolsuper: false, rolbypassrls: false, rolcreatedb: false, rolcreaterole: false, rolreplication: false, rolinherit: false }]);
  assert.equal((await db.query('SELECT count(*)::integer AS count FROM pg_auth_members WHERE member = current_user::regrole')).rows[0].count, 0);
  assert.deepEqual((await db.query("SELECT pg_get_userbyid(nspowner) AS owner, has_schema_privilege(oid, 'USAGE') AS usage, has_schema_privilege(oid, 'CREATE') AS create FROM pg_namespace WHERE nspname = $1", [schema])).rows,
    [{ owner: 'foundation_migrator', usage: true, create: false }]);
  assert.deepEqual((await db.query("SELECT has_database_privilege(current_database(), 'CONNECT') AS connect, has_database_privilege(current_database(), 'CREATE') AS create, has_database_privilege(current_database(), 'TEMP') AS temp")).rows,
    [{ connect: true, create: false, temp: false }]);
  for (const privilege of ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'TRIGGER', 'REFERENCES']) {
    const allowed = (await db.query('SELECT has_table_privilege($1, $2) AS allowed', [`${schema}.owner_probe`, privilege])).rows[0].allowed;
    assert.equal(allowed, ['SELECT', 'INSERT', 'UPDATE', 'DELETE'].includes(privilege));
  }
  for (const sql of [`CREATE TABLE "${schema}".forbidden (id integer)`,
    `ALTER TABLE "${schema}".owner_probe ADD COLUMN forbidden integer`, `DROP TABLE "${schema}".owner_probe`]) {
    await assert.rejects(asOwner(db, 'owner-a', tx => tx.query(sql)), /Database operation failed/);
  }
});
