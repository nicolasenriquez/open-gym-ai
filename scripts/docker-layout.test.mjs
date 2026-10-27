import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../', import.meta.url));

test('deployment relocation preserves project ownership, root paths and isolated ports', t => {
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-compose-layout-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const envFile = join(temporary, 'synthetic.env');
  const digest = 'a'.repeat(64);
  const env = Object.fromEntries(Object.entries(process.env)
    .filter(([key]) => !/^(COMPOSE_|PLATFORM_)/i.test(key)));
  env.COMPOSE_DISABLE_ENV_FILE = 'true';
  const config = (files, project) => {
    const result = spawnSync('docker', ['compose', '--project-directory', root,
      '--env-file', envFile, ...files.flatMap(file => ['-f', join(root, 'deploy', file)]),
      '--profile', '*', ...(project ? ['-p', project] : []),
      'config', '--format', 'json'], { env, encoding: 'utf8', timeout: 30_000 });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
    return JSON.parse(result.stdout);
  };
  for (const [overlay, project, port, mode] of [
    ['dev', 'opengym-dev', '8081', 'dev'], ['prod', 'opengym-ops', '8080', 'ops'],
  ]) {
    writeFileSync(envFile, [
      `PLATFORM_WEB_PORT=${port}`, `PLATFORM_SECRETS_DIR=${temporary.replaceAll('\\', '/')}`,
      ...['WEB', 'RUNTIME', 'MIGRATE', 'OPS'].map(target => `PLATFORM_${target}_DIGEST=${digest}`),
    ].join('\n'));
    const selected = config(['docker-compose.yml', `docker-compose.${overlay}.yml`]);
    assert.equal(selected.name, project);
    assert.equal(selected.volumes['postgres-data'].name, `${project}_${mode}-postgres-data`);
    assert.equal(selected.networks.database.internal, true);
    assert.equal(selected.services.api.environment.PLATFORM_ENV, mode);
    assert.deepEqual(selected.services.web.ports.map(p => [p.host_ip, p.published, p.target]),
      [['127.0.0.1', port, 80]]);
    assert.ok(selected.services.api.healthcheck.test.join(' ').includes('/api/v1/health/ready'));
    for (const service of ['api', 'db']) assert.ok(!selected.services[service].ports?.length);
    assert.deepEqual(selected.services.bootstrap.profiles, ['setup']);
    assert.deepEqual(selected.services.migrate.profiles, ['tools']);
    if (overlay === 'dev') {
      assert.equal(resolve(selected.services.web.build.context), resolve(root));
      assert.equal(selected.services.web.build.dockerfile, 'web/Dockerfile');
      assert.equal(selected.services.web.build.args.VITE_API_PREFIX, '/api/v1');
      assert.equal(resolve(selected.services.api.build.context), resolve(root, 'backend'));
      assert.equal(resolve(selected.services.api.volumes[0].source), resolve(root, 'backend/src'));
    } else {
      for (const service of Object.values(selected.services)) assert.ok(!service.build);
      assert.equal(selected.services.api.image, `sha256:${digest}`);
    }
  }
  writeFileSync(envFile, '');
  for (const [file, project, context] of [
    ['docker-compose.test.yml', 'opengym-platform-test', 'backend'],
  ]) {
    const selected = config([file], project);
    assert.equal(selected.name, project);
    const runner = selected.services['platform-test'];
    assert.equal(resolve(runner.build.context), resolve(root, context));
    assert.equal(selected.networks.private.internal, true);
    for (const service of Object.values(selected.services)) assert.ok(!service.ports?.length);
  }
});

test('current verifier ignores inherited Compose configuration and keeps synthetic ownership', () => {
  const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'config'], {
    cwd: root, encoding: 'utf8', timeout: 30_000,
    env: { ...process.env, COMPOSE_PROFILES: 'foreign', COMPOSE_PROJECT_NAME: 'foreign', COMPOSE_FILE: 'foreign.yml' },
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const config = JSON.parse(result.stdout);
  assert.deepEqual(Object.keys(config.services), ['platform-contracts', 'platform-db', 'platform-test']);
  assert.equal(config.services['platform-test'].build.target, 'test');
  assert.deepEqual(config.networks.private.labels, {
    'com.docker.compose.service': 'private', 'org.opengym.platform': 'synthetic',
  });
  assert.deepEqual(config.volumes['postgres-data'].labels, {
    'com.docker.compose.service': 'platform-db', 'org.opengym.platform': 'synthetic',
  });
  assert.doesNotMatch(JSON.stringify(config), /foreign/);
});
