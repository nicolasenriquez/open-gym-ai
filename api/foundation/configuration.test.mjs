import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cli = fileURLToPath(new URL('./environment.mjs', import.meta.url));
const versions = JSON.parse(readFileSync(new URL('./versions.json', import.meta.url)));

test('effective Compose config isolates Foundation despite inherited instance variables', t => {
  const cwd = mkdtempSync(join(tmpdir(), 'foundation-config-'));
  t.after(() => rmSync(cwd, { recursive: true, force: true }));
  writeFileSync(join(cwd, '.env'), 'COMPOSE_FILE=does-not-exist.yml\nPOSTGRES_PASSWORD=must-not-be-inherited\n');
  const result = spawnSync(process.execPath, [cli, 'config'], {
    encoding: 'utf8', cwd,
    env: { ...process.env, COMPOSE_FILE: 'does-not-exist.yml', COMPOSE_PROJECT_NAME: 'opengym',
      COMPOSE_ENV_FILES: 'does-not-exist.env',
      COMPOSE_PROFILES: 'real-instance', DATA_DIR: '/real-instance-data',
      POSTGRES_PASSWORD: 'must-not-be-inherited', DATABASE_URL: 'must-not-be-inherited' },
  });
  assert.equal(result.status, 0, result.stderr);
  const config = JSON.parse(result.stdout);
  assert.deepEqual(Object.keys(config.services ?? {}).sort(), ['foundation-db', 'foundation-test']);
  assert.equal(config.services['foundation-db'].image, versions.postgresImage);
  assert.equal(config.networks.private.internal, true);
  for (const service of Object.values(config.services)) {
    assert.ok(!service.ports?.length);
    assert.ok(!service.env_file?.length);
    assert.ok(!service.privileged);
    assert.ok(!service.network_mode);
    assert.deepEqual(Object.keys(service.networks), ['private']);
    assert.ok((service.volumes ?? []).every(volume => volume.type === 'volume'));
    assert.doesNotMatch(JSON.stringify(service), /must-not-be-inherited|real-instance-data/);
  }
  assert.equal(config.services['foundation-test'].build.args.NODE_IMAGE, versions.nodeImage);
  assert.equal(config.services['foundation-test'].user, '1000:1000');
  assert.equal(config.services['foundation-test'].read_only, true);
  assert.deepEqual(Object.keys(config.volumes), ['postgres-data']);
});
