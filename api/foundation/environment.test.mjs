import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cli = fileURLToPath(new URL('./environment.mjs', import.meta.url));
const runner = fileURLToPath(new URL('./run.mjs', import.meta.url));
const migrator = fileURLToPath(new URL('./migrate.mjs', import.meta.url));
const recovery = fileURLToPath(new URL('./recovery.mjs', import.meta.url));

test('cleanup refuses a non-Foundation project before accessing Docker', () => {
  const result = spawnSync(process.execPath, [cli, 'cleanup', 'opengym'], {
    env: { ...process.env, PATH: '' }, encoding: 'utf8',
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Refusing non-test target/);
  assert.doesNotMatch(result.stderr, /ENOENT|not found/i);
});

test('recovery refuses external hosts and unsafe artifact paths before loading the driver', () => {
  const synthetic = { ...process.env, PGHOST: 'foundation-db', PGPORT: '5432',
    PGDATABASE: 'foundation_test', PGUSER: 'foundation_bootstrap', PGPASSWORD: 'synthetic-foundation-only' };
  for (const [args, env, message] of [
    [['backup', '/tmp/foundation-recovery-probe/backup', '/tmp/foundation-recovery-probe/keys/key.bin', '0'.repeat(40)],
      { ...synthetic, PGHOST: 'external.invalid', PGPASSWORD: 'do-not-log-this' }, 'Refusing non-test database target'],
    [['restore', '/real/backup', '/real/key', 'foundation_test'], synthetic, 'Invalid recovery arguments'],
  ]) {
    const result = spawnSync(process.execPath, [recovery, ...args], { env, encoding: 'utf8', timeout: 2_000 });
    assert.equal(result.status, 1);
    assert.ok(result.stderr.includes(message));
    assert.doesNotMatch(result.stderr, /external.invalid|do-not-log-this|synthetic-foundation-only|ERR_MODULE_NOT_FOUND/);
  }
});

test('runner refuses a database target outside the synthetic service before connecting', () => {
  const result = spawnSync(process.execPath, [runner, 'environment'], {
    env: { ...process.env, PGHOST: 'real-database.example', PGDATABASE: 'foundation_test',
      PGPORT: '5432', PGUSER: 'foundation_bootstrap', PGPASSWORD: 'do-not-log-this' },
    encoding: 'utf8',
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Refusing non-test database target/);
  assert.doesNotMatch(result.stderr, /real-database|do-not-log-this/);
});

test('migration process rejects external targets and invalid fixture arguments before connecting', () => {
  const synthetic = { ...process.env, PGHOST: 'foundation-db', PGPORT: '5432',
    PGDATABASE: 'foundation_test', PGUSER: 'foundation_bootstrap', PGPASSWORD: 'synthetic-foundation-only' };
  for (const [args, env, message] of [
    [['bootstrap'], { ...synthetic, PGHOST: 'external.invalid', PGPASSWORD: 'do-not-log-this' }, 'Refusing non-test database target'],
    [['up', '/real/migrations', 'public'], synthetic, 'Invalid migration arguments'],
    [['up', '/tmp/foundation-migrations-probe/../elsewhere', 'foundation_probe_0123456789abcdef'], synthetic, 'Invalid migration arguments'],
    [['up', '/tmp/foundation-migrations-probe', 'foundation_probe_0123456789abcdef', '9007199254740992'], synthetic, 'Invalid migration arguments'],
    [['bootstrap', 'extra'], synthetic, 'Invalid migration arguments'],
  ]) {
    const result = spawnSync(process.execPath, [migrator, ...args], { env, encoding: 'utf8', timeout: 2_000 });
    assert.equal(result.status, 1);
    assert.ok(result.stderr.includes(message));
    assert.doesNotMatch(result.stderr, /external.invalid|do-not-log-this|synthetic-foundation-only|ERR_MODULE_NOT_FOUND/);
  }
});
