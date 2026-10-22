import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, writeFile, rm, stat, chmod, symlink } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import pg from 'pg';
import { prepareIsolationFixture } from './isolation-fixture.mjs';

// Only run.mjs's guarded synthetic environment loads this group. No production endpoints.
const connection = { host: 'foundation-db', port: 5432, database: 'foundation_test',
  user: 'foundation_bootstrap', password: 'synthetic-foundation-only', ssl: false,
  connectionTimeoutMillis: 2_000, query_timeout: 3_000, statement_timeout: 2_000 };
// A declared synthetic application revision, not a claim about the checkout's Git HEAD.
const revision = '0123456789abcdef0123456789abcdef01234567';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');

function command(file, args) {
  const result = spawnSync(process.execPath, [file, ...args], { encoding: 'utf8', timeout: 30_000, killSignal: 'SIGKILL' });
  assert.ifError(result.error);
  assert.equal(result.signal, null, 'CLI must exit naturally, not time out');
  if (/synthetic-(?:foundation|migrator|runtime|training)-only|postgres(?:ql)?:\/\//i.test(result.stdout + result.stderr)) {
    throw new Error('Unsafe recovery diagnostics');
  }
  return result;
}

async function snapshot(db, schema) {
  return {
    rows: (await db.query(`SELECT id, owner_id, note FROM "${schema}".owner_probe ORDER BY id`)).rows,
    history: (await db.query('SELECT name FROM foundation.pgmigrations ORDER BY id')).rows,
    table: (await db.query('SELECT pg_get_userbyid(relowner) AS owner, relrowsecurity AS enabled, relforcerowsecurity AS forced FROM pg_class WHERE oid = $1::regclass', [`${schema}.owner_probe`])).rows,
    policies: (await db.query('SELECT polname, polcmd, polpermissive, ARRAY(SELECT rolname::text FROM pg_roles WHERE oid = ANY(polroles) ORDER BY rolname) AS roles, pg_get_expr(polqual, polrelid) AS using, pg_get_expr(polwithcheck, polrelid) AS check FROM pg_policy WHERE polrelid = $1::regclass ORDER BY polname', [`${schema}.owner_probe`])).rows,
    schema: (await db.query("SELECT pg_get_userbyid(nspowner) AS owner, has_schema_privilege('foundation_runtime', oid, 'CREATE') AS runtime_create, has_schema_privilege('foundation_training', oid, 'USAGE') AS training_usage FROM pg_namespace WHERE nspname = $1", [schema])).rows,
    grants: (await db.query("SELECT has_schema_privilege('foundation_runtime', $1, 'USAGE') AS usage, has_table_privilege('foundation_runtime', $2, 'SELECT') AS read, has_table_privilege('foundation_runtime', $2, 'INSERT') AS insert, has_table_privilege('foundation_runtime', $2, 'UPDATE') AS update, has_table_privilege('foundation_runtime', $2, 'DELETE') AS delete, has_table_privilege('foundation_runtime', $2, 'TRUNCATE') AS truncate, has_table_privilege('foundation_training', $2, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE') AS training", [schema, `${schema}.owner_probe`])).rows,
    database: (await db.query("SELECT has_database_privilege('foundation_runtime', current_database(), 'CONNECT') AS connect, has_database_privilege('foundation_runtime', current_database(), 'CREATE') AS create, has_database_privilege('foundation_runtime', current_database(), 'TEMP') AS temp")).rows,
  };
}

async function fixture(t) {
  for (const args of [['bootstrap'], ['up']]) assert.equal(command('migrate.mjs', args).status, 0, 'migration setup must pass before recovery assertions');
  const token = randomBytes(8).toString('hex');
  const schema = `foundation_isolation_${token}`;
  const target = `foundation_restore_${token}`;
  const root = await mkdtemp(join(tmpdir(), 'foundation-recovery-'));
  const backup = join(root, 'backup'), transfer = join(root, 'transfer'), keys = join(root, 'keys');
  for (const directory of [backup, transfer, keys]) await mkdir(directory, { mode: 0o700 });
  const secret = randomBytes(32), key = join(keys, 'key.bin'), wrong = join(keys, 'wrong.bin');
  await writeFile(key, secret, { mode: 0o600 });
  await writeFile(wrong, randomBytes(32), { mode: 0o600 });
  const source = new pg.Client(connection);
  await source.connect();
  let destination, created = false;
  t.after(async () => {
    try {
      if (destination) await destination.end();
      if (created) {
        assert.match(target, /^foundation_restore_[a-f0-9]{16}$/);
        assert.deepEqual((await source.query('SELECT pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname = $1', [target])).rows,
          [{ owner: 'foundation_bootstrap' }]);
        await source.query(`DROP DATABASE "${target}"`);
        assert.equal((await source.query('SELECT count(*)::integer AS count FROM pg_database WHERE datname = $1', [target])).rows[0].count, 0);
      }
      await source.query(`DROP SCHEMA IF EXISTS "${schema}" CASCADE`);
      assert.equal((await source.query('SELECT to_regnamespace($1) AS name', [schema])).rows[0].name, null);
    } finally { await source.end(); await rm(root, { recursive: true, force: true }); }
    assert.equal(existsSync(root), false);
    t.diagnostic('Recovery fixture cleanup PASS: owned database/schema and tmpfs artifacts/key absent; clients closed');
  });
  const migrator = new pg.Client({ ...connection, user: 'foundation_migrator', password: 'synthetic-migrator-only' });
  try { await migrator.connect(); await prepareIsolationFixture(migrator, schema); }
  finally { await migrator.end(); }
  await source.query(`CREATE DATABASE "${target}"`);
  created = true;
  destination = new pg.Client({ ...connection, database: target });
  await destination.connect();
  const before = await snapshot(source, schema);
  assert.deepEqual(before.rows, [{ id: 1, owner_id: 'owner-a', note: 'initial-a' }, { id: 2, owner_id: 'owner-b', note: 'initial-b' }]);
  assert.deepEqual(before.history, [{ name: '001-foundation' }]);
  assert.deepEqual(before.table, [{ owner: 'foundation_migrator', enabled: true, forced: true }]);
  assert.deepEqual(before.schema, [{ owner: 'foundation_migrator', runtime_create: false, training_usage: false }]);
  assert.deepEqual(before.policies.map(policy => policy.roles), [['foundation_runtime']]);
  assert.deepEqual(before.grants, [{ usage: true, read: true, insert: true, update: true, delete: true, truncate: false, training: false }]);
  assert.deepEqual(before.database, [{ connect: true, create: false, temp: false }]);
  return { schema, target, backup, transfer, key, wrong, secret, source, destination, before };
}

async function runtimeProof(database, schema) {
  const db = new pg.Client({ ...connection, database, user: 'foundation_runtime', password: 'synthetic-runtime-only' });
  try {
    await db.connect();
    for (const [owner, expected] of [['owner-a', [{ id: 1 }]], ['owner-b', [{ id: 2 }]], [null, []]]) {
      await db.query('BEGIN');
      try {
        if (owner !== null) await db.query("SELECT set_config('app.owner_id', $1, true)", [owner]);
        assert.deepEqual((await db.query(`SELECT id FROM "${schema}".owner_probe ORDER BY id`)).rows, expected);
        if (owner !== null) {
          const own = owner === 'owner-a' ? 1 : 2, foreign = own === 1 ? 2 : 1;
          assert.equal((await db.query(`UPDATE "${schema}".owner_probe SET note = 'restored-write' WHERE id = $1`, [own])).rowCount, 1);
          assert.equal((await db.query(`UPDATE "${schema}".owner_probe SET note = 'forbidden' WHERE id = $1`, [foreign])).rowCount, 0);
          assert.equal((await db.query(`DELETE FROM "${schema}".owner_probe WHERE id = $1`, [foreign])).rowCount, 0);
          await db.query(`INSERT INTO "${schema}".owner_probe VALUES (3, $1, 'restored-insert')`, [owner]);
          assert.equal((await db.query(`DELETE FROM "${schema}".owner_probe WHERE id = 3`)).rowCount, 1);
        }
        await db.query('SAVEPOINT denied_write');
        await assert.rejects(db.query(`INSERT INTO "${schema}".owner_probe VALUES (4, $1, 'forbidden')`,
          [owner === 'owner-a' ? 'owner-b' : 'owner-a']), { code: '42501' });
        await db.query('ROLLBACK TO SAVEPOINT denied_write');
      } finally { await db.query('ROLLBACK'); }
    }
    await assert.rejects(db.query(`TRUNCATE "${schema}".owner_probe`), { code: '42501' });
  } finally { await db.end(); }
  const training = new pg.Client({ ...connection, database, user: 'foundation_training', password: 'synthetic-training-only' });
  try {
    await training.connect();
    await training.query("SELECT set_config('app.owner_id', 'owner-a', false)");
    await assert.rejects(training.query(`SELECT * FROM "${schema}".owner_probe`), { code: '42501' });
  } finally { await training.end(); }
}

test('encrypted backup transfers and restores both owners, history, ownership, grants and RLS into another database', { timeout: 90_000 }, async t => {
  const f = await fixture(t);
  const started = performance.now();
  assert.equal(command('recovery.mjs', ['backup', f.backup, f.key, revision]).status, 0);
  const backupMs = performance.now() - started;
  assert.deepEqual(await snapshot(f.source, f.schema), f.before);
  const encrypted = join(f.backup, 'backup.enc'), manifestFile = join(f.backup, 'manifest.json');
  assert.ok(existsSync(encrypted), 'backup must create an encrypted artifact, not merely connect');
  assert.ok(existsSync(manifestFile), 'backup must create its integrity/scope manifest');
  const manifestBytes = await readFile(manifestFile), manifest = JSON.parse(manifestBytes);
  assert.deepEqual((await readdir(f.backup)).sort(), ['backup.enc', 'manifest.json'], 'no plaintext dump or key on disk');
  assert.equal(manifest.formatVersion, 1);
  assert.equal(manifest.applicationRevision, revision);
  assert.deepEqual(manifest.schemaVersion, ['001-foundation']);
  assert.equal(manifest.databaseVersion, '18.6');
  assert.deepEqual(manifest.tools, { pg_dump: '18.6', pg_restore: '18.6' });
  assert.equal(manifest.sourceDatabase, 'foundation_test');
  assert.deepEqual(manifest.owners, ['owner-a', 'owner-b']);
  assert.deepEqual(manifest.roles, ['foundation_migrator', 'foundation_runtime', 'foundation_training']);
  assert.equal(manifest.cipher, 'aes-256-gcm');
  const bytes = await readFile(encrypted);
  const decipher = createDecipheriv('aes-256-gcm', f.secret, bytes.subarray(0, 12));
  decipher.setAAD(manifestBytes);
  decipher.setAuthTag(bytes.subarray(12, 28));
  const dump = Buffer.concat([decipher.update(bytes.subarray(28)), decipher.final()]);
  assert.equal(dump.subarray(0, 5).toString(), 'PGDMP');
  assert.equal(hash(dump), manifest.dumpSha256);
  for (const path of [encrypted, manifestFile, f.key]) assert.equal((await stat(path)).mode & 0o077, 0);
  const copyStarted = performance.now();
  assert.equal(command('recovery.mjs', ['copy', f.backup, f.transfer]).status, 0);
  const copyMs = performance.now() - copyStarted;
  assert.deepEqual((await readdir(f.transfer)).sort(), ['backup.enc', 'manifest.json']);
  for (const name of ['backup.enc', 'manifest.json']) assert.deepEqual(await readFile(join(f.transfer, name)), await readFile(join(f.backup, name)));
  assert.equal(existsSync(join(f.transfer, 'key.bin')), false);
  const restoreStarted = performance.now();
  assert.equal(command('recovery.mjs', ['restore', f.transfer, f.key, f.target]).status, 0);
  const restoreMs = performance.now() - restoreStarted;
  const verifyStarted = performance.now();
  assert.deepEqual(await snapshot(f.destination, f.schema), f.before);
  await runtimeProof(f.target, f.schema);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before, 'source data/history/permissions must remain intact');
  assert.deepEqual(await snapshot(f.destination, f.schema), f.before, 'runtime verification rolls back its writes');
  const verified = performance.now();
  t.diagnostic(JSON.stringify({ event: 'recovery-timing', unit: 'ms', rows: 2, owners: 2,
    archiveBytes: dump.length, encryptedBytes: bytes.length,
    backupMs, copyMs, restoreMs, verificationMs: verified - verifyStarted,
    restoreVerifiedMs: verified - restoreStarted, roundTripMs: verified - started,
    scope: 'synthetic-two-databases-one-cluster-same-host; excludes fixture setup and teardown' }));
});

// Independently sealed authentication controls, NOT pg_dump output or a successful backup.
async function controlBundle(f, directory) {
  const dump = Buffer.from('PGDMP-synthetic-authentication-control-only');
  const manifest = { formatVersion: 1, applicationRevision: revision, schemaVersion: ['001-foundation'],
    databaseVersion: '18.6', tools: { pg_dump: '18.6', pg_restore: '18.6' }, sourceDatabase: 'foundation_test',
    owners: ['owner-a', 'owner-b'], roles: ['foundation_migrator', 'foundation_runtime', 'foundation_training'],
    cipher: 'aes-256-gcm', dumpSha256: hash(dump) };
  const metadata = Buffer.from(JSON.stringify(manifest));
  const nonce = randomBytes(12), cipher = createCipheriv('aes-256-gcm', f.secret, nonce);
  cipher.setAAD(metadata);
  const ciphertext = Buffer.concat([cipher.update(dump), cipher.final()]);
  const bytes = Buffer.concat([nonce, cipher.getAuthTag(), ciphertext]);
  const decipher = createDecipheriv('aes-256-gcm', f.secret, nonce);
  decipher.setAAD(metadata); decipher.setAuthTag(bytes.subarray(12, 28));
  assert.deepEqual(Buffer.concat([decipher.update(bytes.subarray(28)), decipher.final()]), dump);
  await writeFile(join(directory, 'manifest.json'), metadata, { mode: 0o600 });
  await writeFile(join(directory, 'backup.enc'), bytes, { mode: 0o600 });
}

const targetState = async db => ({
  routines: (await db.query("SELECT n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' ORDER BY 1, 2")).rows,
  relations: (await db.query("SELECT n.nspname, c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' ORDER BY 1, 2")).rows,
  schemas: (await db.query("SELECT nspname, pg_get_userbyid(nspowner) AS owner, nspacl::text AS acl FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema' ORDER BY nspname")).rows,
  database: (await db.query('SELECT pg_get_userbyid(datdba) AS owner, datacl::text AS acl FROM pg_database WHERE datname = current_database()')).rows,
});

test('copy transfers only the encrypted artifact and manifest to a distinct directory', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  await controlBundle(f, f.backup);
  const result = command('recovery.mjs', ['copy', f.backup, f.transfer]);
  assert.equal(result.status, 0);
  assert.ok(existsSync(join(f.transfer, 'backup.enc')), 'copy must create the transferred artifact');
  assert.deepEqual((await readdir(f.transfer)).sort(), ['backup.enc', 'manifest.json']);
  for (const name of ['backup.enc', 'manifest.json']) assert.deepEqual(await readFile(join(f.transfer, name)), await readFile(join(f.backup, name)));
  assert.equal(existsSync(join(f.transfer, 'key.bin')), false);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before);
});

for (const problem of ['wrong key', 'corrupt artifact', 'altered manifest']) {
  test(`${problem}: restore rejects authentication before touching the isolated target`, { timeout: 60_000 }, async t => {
    const f = await fixture(t);
    await controlBundle(f, f.transfer);
    if (problem === 'corrupt artifact') {
      const file = join(f.transfer, 'backup.enc'), bytes = await readFile(file);
      bytes[bytes.length - 1] ^= 1;
      await writeFile(file, bytes);
    } else if (problem === 'altered manifest') {
      const file = join(f.transfer, 'manifest.json');
      const manifest = JSON.parse(await readFile(file));
      manifest.applicationRevision = 'f'.repeat(40);
      await writeFile(file, JSON.stringify(manifest));
    } else assert.equal(f.secret.equals(await readFile(f.wrong)), false);
    const beforeTarget = await targetState(f.destination);
    assert.deepEqual(beforeTarget.relations, []);
    const result = command('recovery.mjs', ['restore', f.transfer, problem === 'wrong key' ? f.wrong : f.key, f.target]);
    assert.deepEqual(await targetState(f.destination), beforeTarget, 'no unverified schema/data or ACL change may be applied');
    assert.deepEqual(await snapshot(f.source, f.schema), f.before);
    assert.equal(result.status, 1, `${problem} must be rejected, not reported as successful`);
    assert.equal(result.stderr.trim(), 'Recovery verification failed');
  });
}

test('restore refuses the source database as an unsafe destination without modifying it', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  await controlBundle(f, f.transfer);
  const beforeTarget = await targetState(f.destination);
  const result = command('recovery.mjs', ['restore', f.transfer, f.key, 'foundation_test']);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before, 'protected source must remain unchanged');
  assert.deepEqual(await targetState(f.destination), beforeTarget);
  assert.equal(result.status, 1, 'restore must explicitly reject a destination outside its generated test target');
  assert.equal(result.stderr.trim(), 'Refusing non-test restore target');
});

test('restore refuses a generated target containing only a routine, preserving its contents and ACLs', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  assert.equal(command('recovery.mjs', ['backup', f.backup, f.key, revision]).status, 0);
  await f.destination.query('CREATE FUNCTION public.existing_probe() RETURNS integer LANGUAGE sql AS $$ SELECT 7 $$');
  const beforeTarget = await targetState(f.destination);
  const result = command('recovery.mjs', ['restore', f.backup, f.key, f.target]);
  assert.equal(result.status, 1, 'a database with a routine is not an empty restore target');
  assert.equal(result.stderr.trim(), 'Refusing non-test restore target');
  assert.deepEqual(await targetState(f.destination), beforeTarget);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before);
});

test('backup rejects a public or symlinked key without creating artifacts', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  await chmod(f.key, 0o644);
  let result = command('recovery.mjs', ['backup', f.backup, f.key, revision]);
  assert.equal(result.status, 1);
  assert.equal(result.stderr.trim(), 'Invalid recovery arguments');
  await chmod(f.key, 0o600);
  await rm(f.wrong);
  await symlink(f.key, f.wrong);
  result = command('recovery.mjs', ['backup', f.backup, f.wrong, revision]);
  assert.equal(result.status, 1);
  assert.equal(result.stderr.trim(), 'Invalid recovery arguments');
  assert.deepEqual(await readdir(f.backup), []);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before);
});

test('copy refuses to overwrite an existing transfer bundle', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  await controlBundle(f, f.backup);
  await controlBundle(f, f.transfer);
  const before = await readFile(join(f.transfer, 'backup.enc'));
  const result = command('recovery.mjs', ['copy', f.backup, f.transfer]);
  assert.equal(result.status, 1);
  assert.equal(result.stderr.trim(), 'Invalid recovery arguments');
  assert.deepEqual(await readFile(join(f.transfer, 'backup.enc')), before);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before);
});

test('authenticated bytes that are not a valid custom archive never reach the target', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  await controlBundle(f, f.transfer);
  const before = await targetState(f.destination);
  const result = command('recovery.mjs', ['restore', f.transfer, f.key, f.target]);
  assert.equal(result.status, 1);
  assert.equal(result.stderr.trim(), 'Recovery verification failed');
  assert.deepEqual(await targetState(f.destination), before);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before);
});

test('restore refuses a generated database owned by another role', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  assert.equal(command('recovery.mjs', ['backup', f.backup, f.key, revision]).status, 0);
  await f.source.query(`ALTER DATABASE "${f.target}" OWNER TO foundation_migrator`);
  try {
    const before = await targetState(f.destination);
    const result = command('recovery.mjs', ['restore', f.backup, f.key, f.target]);
    assert.equal(result.status, 1);
    assert.equal(result.stderr.trim(), 'Refusing non-test restore target');
    assert.deepEqual(await targetState(f.destination), before);
    assert.deepEqual(await snapshot(f.source, f.schema), f.before);
  } finally { await f.source.query(`ALTER DATABASE "${f.target}" OWNER TO foundation_bootstrap`); }
});

test('restore refuses preexisting database grants rather than retaining excess runtime privileges', { timeout: 60_000 }, async t => {
  const f = await fixture(t);
  assert.equal(command('recovery.mjs', ['backup', f.backup, f.key, revision]).status, 0);
  await f.source.query(`GRANT CREATE ON DATABASE "${f.target}" TO foundation_runtime`);
  const before = await targetState(f.destination);
  const result = command('recovery.mjs', ['restore', f.backup, f.key, f.target]);
  assert.equal(result.status, 1, 'restore must not retain existing excess database privileges');
  assert.equal(result.stderr.trim(), 'Refusing non-test restore target');
  assert.deepEqual(await targetState(f.destination), before);
  assert.deepEqual(await snapshot(f.source, f.schema), f.before);
});
