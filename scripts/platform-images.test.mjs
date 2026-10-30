import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { syntheticHarness } from './synthetic-harness.mjs';

test('targets and real dev/ops Compose isolate credentials, networks and dependencies', async () => {
  const token = randomBytes(8).toString('hex');
  const project = `opengym-platform-test-${token}`;
  const { execute, docker, cleanup } = syntheticHarness({
    root: fileURLToPath(new URL('../', import.meta.url)), namespace: 'opengym-platform-test',
    label: 'org.opengym.platform', name: 'Platform',
    services: ['platform-runtime', 'platform-test', 'platform-migrate', 'platform-ops', 'platform-dev'],
    images: ['platform-runtime', 'platform-test', 'platform-migrate', 'platform-ops', 'platform-dev'], database: 'platform-db',
  });
  const image = `${project}-platform-runtime:local`;
  try {
    await execute('docker', ['build', '--platform', 'linux/amd64', '--target', 'runtime',
      '--label', `com.docker.compose.project=${project}`, '--label', 'com.docker.compose.service=platform-runtime',
      '--label', 'org.opengym.platform=synthetic', '-t', image, '-f', 'backend/Dockerfile', 'backend'], true);
    await docker(['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
      '--security-opt', 'no-new-privileges', image, '-c', `
import importlib.util, os, pathlib, shutil
assert os.getuid() == 1000
for executable in ('node', 'npm', 'uv', 'pip', 'claude', 'codex', 'bwrap', 'pg_dump'):
    assert shutil.which(executable) is None, executable
for module in ('pytest', 'ruff', 'mypy', 'pip'):
    assert importlib.util.find_spec(module) is None, module
assert not pathlib.Path('/app/tests').exists()
assert not pathlib.Path('/app/src/opengym_platform/runner.py').exists()
import fastapi, asyncpg, uvicorn, httpx
assert httpx.__version__ == '0.28.1'
from opengym_platform.coach.payload import ASSETS
assert ASSETS['library'] and ASSETS['prompts']['common']
print('PLATFORM_RUNTIME_ISOLATION_OK')
`], true);
    const testImage = `${project}-platform-test:local`;
    await docker(['build', '--platform', 'linux/amd64', '--target', 'test',
      '--label', `com.docker.compose.project=${project}`, '--label', 'com.docker.compose.service=platform-test',
      '--label', 'org.opengym.platform=synthetic', '-t', testImage, '-f', 'backend/Dockerfile', 'backend'], true);
    await docker(['run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
      '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', testImage, 'tests/platform/test_file_secrets.py'], true);
    for (const target of ['migrate', 'ops', 'dev']) {
      await docker(['build', '--platform', 'linux/amd64', '--target', target,
        '--label', `com.docker.compose.project=${project}`, '--label', `com.docker.compose.service=platform-${target}`,
        '--label', 'org.opengym.platform=synthetic', '-t', `${project}-platform-${target}:local`,
        '-f', 'backend/Dockerfile', 'backend'], true);
      const metadata = JSON.parse(await docker(['image', 'inspect', `${project}-platform-${target}:local`]))[0];
      assert.equal(metadata.Config.User, '1000:1000');
      await docker(['run', '--rm', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--entrypoint', '/app/.venv/bin/python',
        `${project}-platform-${target}:local`, '-c', `
import importlib.util, os, pathlib, shutil
assert os.getuid() == 1000
assert not pathlib.Path('/app/tests').exists()
for name in ('pytest', 'ruff', 'mypy', 'pip'):
    assert importlib.util.find_spec(name) is None
for name in ('node', 'npm', 'uv', 'pip', 'claude', 'codex', 'bwrap'):
    assert shutil.which(name) is None
`], true);
    }
    await docker(['run', '--rm', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
      '--security-opt', 'no-new-privileges', `${project}-platform-ops:local`], true);
    await deploymentProof({ project, image, docker });
  } finally {
    await cleanup(project);
  }
});

async function deploymentProof({ project, image, docker }) {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-images-'));
  const versions = JSON.parse(readFileSync(join(root, 'backend/versions.json'), 'utf8'));
  const dockerfile = readFileSync(join(root, 'backend/Dockerfile'), 'utf8');
  for (const pin of [versions.pythonImage, versions.uvImage, versions.postgresImage]) {
    assert.ok(dockerfile.includes(`FROM ${pin}`));
  }
  const images = {};
  for (const target of ['runtime', 'migrate', 'ops']) {
    images[target] = JSON.parse(await docker(['image', 'inspect', `${project}-platform-${target}:local`]))[0].Id.slice(7);
  }
  const envFile = join(temporary, 'verify.env');
  const volumeNames = [];
  try {
    for (const environment of ['dev', 'ops']) {
      const secretRoot = join(temporary, environment);
      mkdirSync(secretRoot, { mode: 0o700 });
      for (const file of ['bootstrap_password', 'migrator_password', 'runtime_password', 'session_secret']) {
        writeFileSync(join(secretRoot, file), `synthetic-${environment}-${file}-${randomBytes(20).toString('hex')}'$$`, { mode: 0o444 });
      }
      writeFileSync(envFile, [
        `PLATFORM_WEB_PORT=${environment === 'dev' ? 8081 : 8080}`,
        `PLATFORM_SECRETS_DIR=${secretRoot.replaceAll('\\', '/')}`,
        `PLATFORM_WEB_DIGEST=${images.runtime}`, `PLATFORM_RUNTIME_DIGEST=${images.runtime}`,
        `PLATFORM_MIGRATE_DIGEST=${images.migrate}`, `PLATFORM_OPS_DIGEST=${images.ops}`,
        'INVITE_ONLY=1', 'ALLOW_GUEST=0', 'PASSWORD_LOGIN=true', 'DEFAULT_LANG=es-CL', 'MEDIA_UPLOADS=0',
      ].join('\n'));
      const instance = `opengym-platform-test-${randomBytes(8).toString('hex')}`;
      const owner = syntheticHarness({
        root, namespace: 'opengym-platform-test', label: 'org.opengym.platform', name: 'Platform',
        services: ['api', 'web', 'db', 'migrate', 'bootstrap', 'ops'], images: [], database: 'db',
        networkNames: ['app', 'database'], volumeName: `${environment}-postgres-data`,
        extraVolumes: { 'media-data': { name: `${environment}-media-data`, service: 'api' } },
      });
      const args = ['compose', '--project-directory', root, '--env-file', envFile, '-p', instance, '--profile', '*',
        '-f', join(root, 'deploy/docker-compose.yml'), '-f', join(root, `deploy/docker-compose.${environment === 'ops' ? 'prod' : 'dev'}.yml`)];
      for (const trustProxy of [undefined, '', '0', '1']) {
        const env = { ...process.env };
        delete env.TRUST_PROXY;
        if (trustProxy !== undefined) env.TRUST_PROXY = trustProxy;
        const resolved = JSON.parse(execFileSync(
          'docker', [...args, 'config', '--format', 'json'],
          { cwd: root, env, encoding: 'utf8', timeout: 30000 },
        ));
        assert.equal(resolved.services.api.environment.TRUST_PROXY, trustProxy || '0');
        assert.ok(resolved.services.api.command.includes('--no-proxy-headers'));
      }
      const config = JSON.parse(await docker([...args, 'config', '--format', 'json']));
      assert.equal(config.services.db.image, versions.postgresImage);
      assert.equal(config.networks.database.internal, true);
      assert.ok(!config.networks.app.internal);
      assert.deepEqual(Object.keys(config.services.web.networks), ['app']);
      assert.deepEqual(Object.keys(config.services.db.networks), ['database']);
      assert.deepEqual(Object.keys(config.services.api.networks).sort(), ['app', 'database']);
      assert.deepEqual(config.services.web.ports.map(port => [port.host_ip, port.published, port.target]), [['127.0.0.1', environment === 'dev' ? '8081' : '8080', 80]]);
      for (const [service, definition] of Object.entries(config.services)) {
        assert.ok(!definition.privileged && !definition.cap_add?.length);
        assert.ok(definition.read_only && definition.user !== '0');
        assert.deepEqual(definition.cap_drop, ['ALL']);
        if (service !== 'web') assert.ok(!definition.ports?.length);
        if (environment === 'ops') {
          assert.ok(!definition.build);
          if (service !== 'db') assert.match(definition.image, /^sha256:[a-f0-9]{64}$/);
          assert.ok(!definition.volumes?.some(volume => volume.type === 'bind'));
        }
      }
      assert.ok(config.services.api.command.includes('--no-proxy-headers'));
      assert.ok(config.services.api.volumes?.some(volume => volume.type === 'volume' && volume.source === 'media-data' && volume.target === '/data'));
      assert.deepEqual(config.services.api.secrets.map(secret => secret.source), ['runtime_password', 'session_secret']);
      assert.equal(config.services.api.environment.COACH_DISABLED, '0');
      assert.equal(config.services.migrate.secrets.length, 1);
      assert.equal(config.services.migrate.secrets[0].source, 'migrator_password');
      assert.ok(!config.services.ops.secrets?.length);
      if (environment === 'dev') {
        assert.equal(config.services.web.build.context, root.replace(/[\\/]$/, ''));
        assert.equal(config.services.web.build.dockerfile, 'web/Dockerfile');
        assert.equal(config.services.web.build.args.VITE_API_PREFIX, '/api/v1');
        assert.ok(config.services.api.command.includes('--reload'));
        assert.deepEqual(config.services.api.volumes.map(volume => volume.target).sort(), ['/app/src', '/data']);
      } else assert.ok(!config.services.api.command.includes('--reload'));
      volumeNames.push(config.volumes['postgres-data'].name);
      assert.equal(config.volumes['media-data'].name, `${instance}_${environment}-media-data`);
      assert.doesNotMatch(JSON.stringify(config), /docker\.sock|coach-auth|seccomp|FOUNDATION_DB_|PLATFORM_DB_PASSWORD"/);
      // Run the resolved topology with owned labels and prebuilt images; web is a network probe, not UI acceptance.
      for (const [service, definition] of Object.entries(config.services)) {
        delete definition.build;
        definition.image = service === 'db' ? versions.postgresImage
          : service === 'bootstrap' || service === 'migrate' ? `${project}-platform-migrate:local`
          : service === 'ops' ? `${project}-platform-ops:local` : image;
        definition.labels = { ...definition.labels, 'org.opengym.platform': 'synthetic' };
        definition.pull_policy = 'never';
      }
      for (const name of ['app', 'database']) config.networks[name].labels = {
        'org.opengym.platform': 'synthetic', 'com.docker.compose.service': name,
      };
      config.volumes['postgres-data'].labels = { 'org.opengym.platform': 'synthetic', 'com.docker.compose.service': 'db' };
      config.volumes['media-data'].labels = { 'org.opengym.platform': 'synthetic', 'com.docker.compose.service': 'api' };
      const configuration = join(temporary, `${environment}.json`);
      writeFileSync(configuration, JSON.stringify(config));
      const compose = [...args.slice(0, args.indexOf('-f')), '-f', configuration];
      try {
        await docker([...compose, 'up', '-d', '--wait', '--wait-timeout', '60', 'db'], true);
        await docker([...compose, 'run', '--rm', '--no-deps', 'bootstrap'], true);
        await docker([...compose, 'run', '--rm', '--no-deps', 'migrate'], true);
        await docker([...compose, 'up', '-d', '--no-deps', 'api'], true);
        await docker([...compose, 'exec', '-T', 'api', '/app/.venv/bin/python', '-c', `
import json, time, urllib.request, urllib.error, pathlib, os
assert os.getuid() == 1000
assert pathlib.Path('/data').stat().st_mode & 0o777 == 0o700
pathlib.Path('/data/synthetic-4-1').write_text('owned persistent media volume')
for attempt in range(100):
    try:
        with urllib.request.urlopen('http://127.0.0.1:3000/api/v1/health/ready', timeout=1) as response:
            assert json.load(response) == {'code': 'PLATFORM_READY_OK'}
        break
    except (OSError, urllib.error.URLError):
        time.sleep(0.1)
else:
    raise AssertionError('platform HTTP did not become ready')
with urllib.request.urlopen('http://127.0.0.1:3000/api/v1/health', timeout=1) as response:
    assert json.load(response) == {'ok': True, 'users': 0, 'writable': True}
with urllib.request.urlopen('http://127.0.0.1:3000/api/v1/config', timeout=1) as response:
    assert json.load(response) == {'invite_only': True, 'allow_guest': False, 'password_login': True, 'default_lang': 'es-CL'}
print('PLATFORM_COMPOSE_HTTP_OK')
`], true);
        await docker([...compose, 'run', '--rm', '--no-deps', '--entrypoint', '/app/.venv/bin/python', 'api', '-c', `
import asyncio, pathlib, asyncpg
assert pathlib.Path('/data/synthetic-4-1').read_text() == 'owned persistent media volume'
from opengym_platform.core.platform_settings import load_database
async def check():
    target = load_database('runtime')
    assert not pathlib.Path('/run/secrets/migrator_password').exists()
    assert not pathlib.Path('/run/secrets/bootstrap_password').exists()
    connection = await asyncpg.connect(host=target.host, database=target.database, user=target.user, password=target.password, ssl=False, timeout=5)
    try:
        assert await connection.fetchval('SELECT current_user') == 'opengym_api_runtime'
        assert await connection.fetchval('SELECT version_num FROM public.alembic_version') == 'p003_coach_lifecycle'
        try:
            await connection.execute('SET ROLE opengym_schema_owner')
        except asyncpg.InsufficientPrivilegeError:
            pass
        else:
            raise AssertionError('runtime assumed owner')
    finally:
        await connection.close(timeout=5)
asyncio.run(check())
print('PLATFORM_DEPLOYMENT_FILES_OK')
`], true);
        const db = JSON.parse(await docker(['container', 'inspect', `${instance}-db-1`]))[0];
        const address = Object.values(db.NetworkSettings.Networks)[0].IPAddress;
        await docker([...compose, 'run', '--rm', '--no-deps', '--entrypoint', '/app/.venv/bin/python', 'web', '-c', `
import socket, pathlib
assert not pathlib.Path('/run/secrets/database_password').exists()
try:
    socket.create_connection((${JSON.stringify(address)}, 5432), timeout=1).close()
except OSError:
    print('PLATFORM_WEB_DB_DENIED')
else:
    raise AssertionError('web reached the private database')
`], true);
      } finally {
        await owner.cleanup(instance);
      }
    }
    assert.notEqual(volumeNames[0], volumeNames[1]);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}
