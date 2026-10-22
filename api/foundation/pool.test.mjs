import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import test from 'node:test';
import { inspect } from 'node:util';
import { createDatabase } from './pool.mjs';

// run.mjs validates the disposable target and pinned runtime before loading this file.
const options = {
  host: 'foundation-db', port: 5432, database: 'foundation_test',
  user: 'foundation_bootstrap', password: 'synthetic-foundation-only', ssl: false,
  max: 1, connectionTimeoutMillis: 300, idleTimeoutMillis: 500,
  statement_timeout: 1_000, query_timeout: 2_000,
};
const pid = async db => (await db.query('SELECT pg_backend_pid() AS pid')).rows[0].pid;
const owner = async db => (await db.query("SELECT nullif(current_setting('app.owner_id', true), '') AS owner")).rows[0].owner;

test('configuration rejects unbounded limits and TLS verification bypasses before connecting', async () => {
  for (const change of [
    { max: 0 }, { connectionTimeoutMillis: 0 }, { idleTimeoutMillis: -1 },
    { statement_timeout: Infinity }, { query_timeout: 0 }, { lock_timeout: 0 },
    { ssl: { rejectUnauthorized: false } }, { ssl: { checkServerIdentity: () => undefined } },
    { connectionString: 'postgres://synthetic:secret@invalid/test?sslmode=no-verify' },
  ]) {
    let db;
    try {
      assert.throws(() => { db = createDatabase({ ...options, ...change }); }, /configuration/i);
    } finally { if (db) await db.close(); }
  }
  const previous = process.env.NODE_TLS_REJECT_UNAUTHORIZED;
  try {
    process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
    assert.throws(() => createDatabase(options), /configuration/i);
  } finally {
    if (previous === undefined) delete process.env.NODE_TLS_REJECT_UNAUTHORIZED;
    else process.env.NODE_TLS_REJECT_UNAUTHORIZED = previous;
  }
});

test('failed transaction rolls back its write before the same connection is reused', { timeout: 10_000 }, async t => {
  const db = createDatabase(options);
  t.after(async () => {
    try { await db.query('DROP TABLE IF EXISTS foundation_pool_probe'); }
    finally { await db.close(); }
  });
  await db.query('CREATE TABLE foundation_pool_probe (value text NOT NULL)');
  const before = await pid(db);
  let reachedFailure = false;
  await assert.rejects(db.transaction(async tx => {
    assert.equal(await pid(tx), before);
    await tx.query('INSERT INTO foundation_pool_probe VALUES ($1)', ['must-roll-back']);
    assert.deepEqual((await tx.query('SELECT value FROM foundation_pool_probe')).rows, [{ value: 'must-roll-back' }]);
    reachedFailure = true;
    throw new Error('synthetic work failure');
  }));
  assert.equal(reachedFailure, true, 'the callback must write and reach the intended failure');
  assert.equal(await pid(db), before, 'max=1 must reuse the tested connection');
  assert.deepEqual((await db.query('SELECT value FROM foundation_pool_probe')).rows, [],
    'a rejected transaction must leave no durable write');
  await db.transaction(tx => tx.query('INSERT INTO foundation_pool_probe VALUES ($1)', ['next-write']));
  assert.deepEqual((await db.query('SELECT value FROM foundation_pool_probe')).rows, [{ value: 'next-write' }]);
});

for (const fail of [false, true]) {
  test(`transaction-local context lasts for the work and disappears after ${fail ? 'failure' : 'commit'}`, { timeout: 10_000 }, async t => {
    const db = createDatabase(options);
    t.after(() => db.close());
    const before = await pid(db);
    let reachedEnd = false;
    const work = db.transaction(async tx => {
      assert.equal(await pid(tx), before);
      await tx.query("SELECT set_config('app.owner_id', $1, true)", ['owner-a']);
      assert.equal(await owner(tx), 'owner-a', 'local context must survive until the transaction ends');
      reachedEnd = true;
      if (fail) throw new Error('synthetic context failure');
    });
    if (fail) await assert.rejects(work, error => {
      if (!reachedEnd) throw error;
      return true;
    });
    else await work;
    assert.equal(reachedEnd, true, 'an earlier callback assertion must not masquerade as the intended failure');
    assert.equal(await pid(db), before);
    assert.equal(await owner(db), null, 'the next borrower must have no previous owner');
  });
}

test('saturated pool times out, recovers its capacity and closes', { timeout: 10_000 }, async t => {
  const db = createDatabase(options);
  t.after(() => db.close());
  const entered = Promise.withResolvers();
  const release = Promise.withResolvers();
  const held = db.transaction(async tx => {
    await tx.query('SELECT 1');
    entered.resolve();
    await release.promise;
  });
  // Forward setup failure so waiting for the acquisition cannot conceal it.
  held.catch(entered.reject);
  try {
    await entered.promise;
    const started = performance.now();
    await assert.rejects(db.query('SELECT 1'), /timeout/i);
    assert.ok(performance.now() - started < 2_000, 'acquisition must have a finite bound');
  } finally {
    release.resolve();
    await held;
  }
  assert.equal((await db.query('SELECT 42 AS value')).rows[0].value, 42);
});

test('terminated transaction connection is rejected and replaced for the next operation', { timeout: 10_000 }, async t => {
  const db = createDatabase(options);
  t.after(() => db.close());
  const before = await pid(db);
  let rejection;
  await assert.rejects(db.transaction(async tx => {
    // Terminate only this leased backend in the disposable database.
    await tx.query('SELECT pg_terminate_backend(pg_backend_pid())');
  }), error => {
    rejection = error;
    return true;
  });
  assert.doesNotMatch(String(rejection), /synthetic-foundation-only|postgres(?:ql)?:\/\//i);
  let next;
  await assert.doesNotReject(async () => { next = await pid(db); },
    'the next operation must recover after the broken connection');
  assert.notEqual(next, before, 'a broken connection must not be handed out again');
  assert.equal((await db.query('SELECT 42 AS value')).rows[0].value, 42);
});

test('explicit close releases connections and rejects later work', { timeout: 10_000 }, async () => {
  const db = createDatabase(options);
  try {
    assert.equal((await db.query('SELECT 42 AS value')).rows[0].value, 42);
  } finally {
    await db.close();
  }
  await assert.rejects(db.query('SELECT 1'));
});

test('query and callback failures expose no server details, payloads or nested secrets', { timeout: 10_000 }, async t => {
  const db = createDatabase(options);
  t.after(() => db.close());
  const secret = 'synthetic-private-payload';
  const safe = error => {
    assert.doesNotMatch(inspect(error, { depth: null }), /synthetic-private-payload|synthetic-foundation-only|postgres:\/\//);
    assert.match(error.message, /^Database /);
    return true;
  };
  await assert.rejects(db.query('SELECT $1::integer', [secret]), safe);
  await assert.rejects(db.transaction(async tx => {
    await assert.rejects(tx.query('SELECT $1::integer', [secret]), safe);
    throw new Error(`postgres://synthetic:${secret}@invalid/test`);
  }), safe);
  assert.equal((await db.query('SELECT 42 AS value')).rows[0].value, 42);
});

test('a caught SQL failure cannot report a rolled-back transaction as committed', { timeout: 10_000 }, async t => {
  const db = createDatabase(options);
  t.after(() => db.close());
  let caught = false;
  await assert.rejects(db.transaction(async tx => {
    try { await tx.query('SELECT 1 / 0'); }
    catch { caught = true; }
    return 'must-not-report-success';
  }));
  assert.equal(caught, true);
  assert.equal((await db.query('SELECT 42 AS value')).rows[0].value, 42);
});

test('a transaction query handle cannot outlive its callback and reach the next borrower', { timeout: 10_000 }, async t => {
  const db = createDatabase(options);
  t.after(() => db.close());
  let previous;
  await db.transaction(async tx => { previous = tx; await tx.query('SELECT 1'); });
  await assert.rejects(previous.query("SELECT set_config('app.owner_id', 'stale-owner', false)"));
  assert.equal(await owner(db), null);
});

test('default server limits are finite and statement cancellation leaves a reusable connection', { timeout: 10_000 }, async t => {
  const { max, connectionTimeoutMillis, idleTimeoutMillis, statement_timeout, query_timeout, ...connection } = options;
  const defaults = createDatabase(connection);
  t.after(() => defaults.close());
  const settings = await defaults.query("SELECT current_setting('statement_timeout') AS statement, current_setting('lock_timeout') AS lock");
  assert.deepEqual(settings.rows, [{ statement: '5s', lock: '2s' }]);
  const db = createDatabase({ ...options, statement_timeout: 50 });
  t.after(() => db.close());
  const before = await pid(db);
  const started = performance.now();
  await assert.rejects(db.transaction(tx => tx.query('SELECT pg_sleep(2)')));
  assert.ok(performance.now() - started < 2_000);
  assert.equal(await pid(db), before);
  assert.equal((await db.query('SELECT 42 AS value')).rows[0].value, 42);
});

test('client query timeout discards uncertain transaction connection and recovers', { timeout: 10_000 }, async t => {
  const db = createDatabase({ ...options, query_timeout: 50 });
  t.after(() => db.close());
  const before = await pid(db);
  const started = performance.now();
  await assert.rejects(db.transaction(tx => tx.query('SELECT pg_sleep(2)')), /timeout/i);
  assert.ok(performance.now() - started < 1_000);
  assert.notEqual(await pid(db), before);
  assert.equal(await owner(db), null);
});
