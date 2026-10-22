import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cli = fileURLToPath(new URL('./environment.mjs', import.meta.url));
const runner = fileURLToPath(new URL('./run.mjs', import.meta.url));

test('cleanup refuses a non-Foundation project before accessing Docker', () => {
  const result = spawnSync(process.execPath, [cli, 'cleanup', 'opengym'], {
    env: { ...process.env, PATH: '' }, encoding: 'utf8',
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Refusing non-test target/);
  assert.doesNotMatch(result.stderr, /ENOENT|not found/i);
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
