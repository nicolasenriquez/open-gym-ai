import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

test('packaged smoke rejects unavailable Docker instead of claiming success', () => {
  const script = fileURLToPath(new URL('./smoke-web-api.mjs', import.meta.url));
  const result = spawnSync(process.execPath, [script], {
    encoding: 'utf8', timeout: 15000,
    env: { ...process.env, DOCKER_CONTEXT: '', DOCKER_HOST: 'tcp://127.0.0.1:1',
      DOCKER_TLS_VERIFY: '', DOCKER_CERT_PATH: '' },
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /CI_SMOKE_FAILED/);
  assert.doesNotMatch(result.stdout, /CI_SMOKE_OK/);
});
