import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const invoke = (program, args, options = {}) => spawnSync(program, args, {
  encoding: 'utf8', timeout: 60_000, ...options,
});
const docker = (...args) => invoke('docker', args);
const ok = result => {
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
};
const cli = (...args) => invoke(process.execPath, ['scripts/platform.mjs', ...args]);
const inspect = (type, name) => JSON.parse(ok(docker(type, 'inspect', name)))[0];

test('ownership: mixed labels preserve every resource and foreign/protected sentinels; owned cleanup succeeds', t => {
  const token = randomBytes(8).toString('hex');
  const project = `opengym-platform-test-${token}`;
  const probe = `org.opengym.platform.probe=${token}`;
  const created = [];
  t.after(() => {
    for (const [type, name] of created.reverse()) {
      const ids = ok(docker(type, 'ls', '--quiet', '--filter', `label=${probe}`));
      if (!ids) continue;
      const item = inspect(type, name);
      assert.equal(item.Labels['org.opengym.platform.probe'], token);
      ok(docker(type, 'rm', name));
    }
  });
  for (const [type, name, labels] of [
    ['volume', `${project}_postgres-data`, ['com.docker.compose.project=' + project,
      'com.docker.compose.volume=postgres-data', 'com.docker.compose.service=platform-db', 'org.opengym.platform=synthetic']],
    ['network', `${project}_private`, ['com.docker.compose.project=' + project,
      'com.docker.compose.network=private', 'com.docker.compose.service=private', 'org.opengym.platform=foreign']],
    ['volume', `opengym-platform-sentinel-${token}`, ['org.opengym.platform=protected-recovery']],
  ]) {
    ok(docker(type, 'create', ...(type === 'network' ? ['--internal'] : []), '--label', probe,
      ...labels.flatMap(label => ['--label', label]), name));
    created.push([type, name]);
  }
  const before = created.map(([type, name]) => inspect(type, name));
  const result = cli('cleanup', project);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Refusing unverified Platform resource/);
  created.forEach(([type, name], i) => assert.deepEqual(inspect(type, name), before[i]));
  ok(docker('network', 'rm', `${project}_private`));
  created.splice(1, 1);
  ok(cli('cleanup', project));
  created.shift();
  assert.equal(docker('volume', 'inspect', `${project}_postgres-data`).status, 1);
  assert.deepEqual(inspect('volume', created[0][1]), before[2]);
});

test('ownership: project-named resources with foreign project labels block cleanup', t => {
  const token = randomBytes(8).toString('hex');
  const project = `opengym-platform-test-${token}`;
  const name = `${project}_postgres-data`;
  ok(docker('volume', 'create', '--label', `org.opengym.platform.probe=${token}`,
    '--label', 'com.docker.compose.project=foreign', name));
  t.after(() => {
    assert.equal(inspect('volume', name).Labels['org.opengym.platform.probe'], token);
    ok(docker('volume', 'rm', name));
  });
  assert.equal(cli('cleanup', project).status, 1);
  assert.equal(inspect('volume', name).Labels['com.docker.compose.project'], 'foreign');
});

test('ownership: a shared image is never untagged or removed', t => {
  const token = randomBytes(8).toString('hex');
  const project = `opengym-platform-test-${token}`;
  const tag = `${project}-platform-contracts:local`;
  const other = `opengym-platform-protected-${token}:local`;
  ok(invoke('docker', ['build', '--quiet', '--tag', tag, '--label', `com.docker.compose.project=${project}`,
    '--label', 'org.opengym.platform=synthetic', '--label', 'com.docker.compose.service=platform-contracts', '-'],
  { input: `FROM scratch\nLABEL org.opengym.platform.probe=${token}\n` }));
  t.after(() => {
    for (const name of [other, tag]) {
      assert.equal(inspect('image', name).Config.Labels['org.opengym.platform.probe'], token);
      ok(docker('image', 'rm', name));
    }
  });
  ok(docker('image', 'tag', tag, other));
  const before = inspect('image', tag);
  assert.equal(cli('cleanup', project).status, 1);
  assert.deepEqual(inspect('image', tag), before);
  assert.deepEqual(inspect('image', other), before);
});

test('ownership: resolved config ignores foreign dotenv/Compose settings and has no instance access', t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-platform-config-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const path of ['scripts/platform.mjs', 'scripts/platform-baseline.mjs', 'scripts/synthetic-harness.mjs',
    'deploy/docker-compose.test.yml', 'backend/empty.env']) {
    mkdirSync(join(root, path, '..'), { recursive: true });
    cpSync(path, join(root, path));
  }
  writeFileSync(join(root, '.env'), 'COMPOSE_FILE=foreign.yml\nCOMPOSE_PROJECT_NAME=foreign\n');
  const result = invoke(process.execPath, ['scripts/platform.mjs', 'config'], {
    cwd: root, env: { ...process.env, COMPOSE_FILE: 'foreign.yml', COMPOSE_PROJECT_NAME: 'foreign',
      COMPOSE_PROFILES: 'foreign', COMPOSE_ENV_FILES: 'foreign.env', DATA_DIR: '/personal', DATABASE_URL: 'personal' },
  });
  const config = JSON.parse(ok(result));
  assert.equal(config.name, 'opengym-platform-test');
  assert.equal(config.networks.private.internal, true);
  assert.deepEqual(Object.keys(config.services), ['platform-browser', 'platform-contracts', 'platform-db', 'platform-test']);
  for (const name of ['platform-browser', 'platform-contracts', 'platform-test']) {
    const service = config.services[name];
    assert.equal(service.user, '1000:1000');
    assert.equal(service.read_only, true);
    assert.ok(!service.ports?.length && !service.volumes?.length && !service.env_file?.length);
    assert.ok(!service.privileged && !service.cap_add?.length);
    assert.deepEqual(service.cap_drop, ['ALL']);
    assert.match(service.security_opt.join(' '), /no-new-privileges/);
  }
  const database = config.services['platform-db'];
  assert.equal(database.user, '1000:1000');
  assert.equal(database.read_only, true);
  assert.ok(!database.ports?.length && !database.env_file?.length);
  assert.deepEqual(database.volumes.map(volume => volume.type), ['volume']);
  assert.ok(!database.privileged && !database.cap_add?.length);
  assert.deepEqual(database.cap_drop, ['ALL']);
  assert.match(database.security_opt.join(' '), /no-new-privileges/);
  assert.doesNotMatch(JSON.stringify(config), /foreign|personal|docker\.sock/);
  assert.match(readFileSync('backend/Dockerfile.contracts', 'utf8'), /node:22\.23\.2.*@sha256:/);
});
