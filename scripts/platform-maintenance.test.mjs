import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { syntheticHarness } from './synthetic-harness.mjs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

// Public host CLI: malformed configuration must not reach Docker or alter files.
test('maintenance rejects an incomplete writer inventory before controlling services', t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-maintenance-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const config = join(root, 'operator.json');
  const source = JSON.stringify({ instance_id: 'synthetic-a', writers: [] });
  writeFileSync(config, source);
  const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
    '--config', config, '--reason', 'scheduled'], {
    encoding: 'utf8', timeout: 5000, env: { ...process.env, PATH: '' },
  });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /MAINTENANCE_CONFIG_INVALID/);
  assert.equal(readFileSync(config, 'utf8'), source);
  writeFileSync(config, JSON.stringify({ instance_id: 'synthetic-a', project: 'synthetic-a',
    project_directory: root, compose_files: [config], env_file: config,
    state_root: join(root, 'PRIVATE-PATH-SENTINEL'), writers: ['api'] }));
  const missing = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
    '--config', config, '--reason', 'scheduled'], { encoding: 'utf8', timeout: 5000, env: { ...process.env, PATH: '' } });
  assert.equal(missing.status, 1);
  assert.match(missing.stderr, /MAINTENANCE_FAILED/);
  assert.doesNotMatch(missing.stderr, /PRIVATE-PATH-SENTINEL|ENOENT/);
  for (const options of [[], ['--operation', '../other'], ['--operation', 'f'.repeat(32), '--force']]) {
    const misuse = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
      '--config', config, ...options], { encoding: 'utf8', timeout: 5000, env: { ...process.env, PATH: '' } });
    assert.equal(misuse.status, 2);
    assert.match(misuse.stderr, /MAINTENANCE_ARGUMENTS_INVALID/);
  }
});

test('maintenance overlay gives only ops the SQL capture credentials and state mount', async t => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-maintenance-config-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const state = join(temporary, 'state').replaceAll('\\', '/');
  const configFile = join(temporary, 'capture.json').replaceAll('\\', '/');
  const envFile = join(temporary, 'explicit.env');
  const instance = 'synthetic-maintenance';
  writeFileSync(configFile, '{}');
  writeFileSync(envFile, [
    `PLATFORM_SECRETS_DIR=${temporary.replaceAll('\\', '/')}`,
    `PLATFORM_INSTANCE_ID=${instance}`, `PLATFORM_MAINTENANCE_STATE_DIR=${state}`,
    `PLATFORM_BACKUP_CONFIG_FILE=${configFile}`,
    ...['WEB', 'RUNTIME', 'MIGRATE', 'OPS', 'DIAGNOSTICS'].map(role => `PLATFORM_${role}_DIGEST=${'a'.repeat(64)}`),
  ].join('\n'));
  const { docker } = syntheticHarness({ root });
  const model = JSON.parse(await docker(['compose', '--project-directory', root, '--env-file', envFile,
    '-p', instance, '--profile', 'tools', ...['docker-compose.yml', 'docker-compose.prod.yml',
      'docker-compose.maintenance.yml'].flatMap(file => ['-f', join(root, 'deploy', file)]), 'config', '--format', 'json']));
  assert.equal(model.services.db.labels['org.opengym.maintenance.instance'], instance);
  assert.equal(model.services.db.labels['org.opengym.maintenance.state'], state);
  assert.equal(model.services.ops.environment.PLATFORM_DB_PASSWORD_FILE, '/run/secrets/backup_password');
  assert.deepEqual(model.services.ops.secrets.map(secret => secret.source), ['backup_password']);
  assert.ok(model.services.ops.volumes.some(volume => volume.target === '/run/maintenance' && volume.type === 'bind'
    && volume.bind.create_host_path === false));
  assert.deepEqual(model.services.api.secrets.map(secret => secret.source), ['runtime_password', 'session_secret', 'coach_secret']);
  assert.ok(!model.services.api.volumes.some(volume => volume.target === '/run/maintenance'));
  assert.equal(model.services.api.environment.PLATFORM_MAINTENANCE_GATE_DIR, '/run/maintenance-gate');
  assert.equal(model.services.api.environment.PLATFORM_INSTANCE_ID, instance);
  assert.ok(model.services.api.volumes.some(volume => volume.target === '/run/maintenance-gate'
    && volume.source === `${state}/gate` && volume.read_only && volume.bind.create_host_path === false));
  assert.ok(!model.services.db.ports?.length);
});


test('host backup stops actual writers, leaves PostgreSQL available and captures all owners', () => backupProof());
test('host file mutation during the pause blocks the recovery set and retains the journal', () => backupProof('host-change'));
test('an external writer appearing during capture blocks restart and retains the journal', () => backupProof('late-writer'));
test('a source symlink blocks capture without following it into runtime secrets', () => backupProof('unsafe-link'));
test('media changed after the SQL snapshot cannot become a coherent recovery set', () => backupProof('media-change'));
test('selected secrets differing from the actual runtime cannot form a coherent recovery set', () => backupProof('runtime-secret'));
test('interrupted capture recovers owned services only after capture termination and compatibility', () => backupProof('recover'));
