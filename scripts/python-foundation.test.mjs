import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../', import.meta.url));
const cli = join(root, 'scripts/python-foundation.mjs');
const docker = (...args) => spawnSync('docker', args, { encoding: 'utf8', timeout: 30_000 });
const compose = (project, ...args) => spawnSync('docker', ['compose', '--project-directory', root,
  '--env-file', join(root, 'backend/empty.env'), '-f', join(root, 'compose.python-foundation.yml'), '-p', project, ...args], {
  encoding: 'utf8', timeout: 300_000,
  env: { ...Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith('COMPOSE_'))),
    COMPOSE_DISABLE_ENV_FILE: 'true' },
});
const ok = result => {
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
};
const inspect = (type, id) => JSON.parse(ok(docker(type, 'inspect', id)))[0];
function assertProjectEmpty(project) {
  for (const type of ['container', 'volume', 'network', 'image']) {
    for (const filter of [`label=com.docker.compose.project=${project}`,
      type === 'image' ? `reference=${project}-*` : `name=^/?${project}[-_]`]) {
      assert.equal(ok(docker(type, 'ls', '--quiet', ...(type === 'container' ? ['--all'] : []),
        '--filter', filter)), '', `no leftover ${type} for ${project}`);
    }
  }
}
function failureCheckout(t, python) {
  const checkout = mkdtempSync(join(tmpdir(), 'python-foundation-failure-'));
  t.after(() => rmSync(checkout, { recursive: true, force: true }));
  for (const file of ['scripts/python-foundation.mjs', 'compose.python-foundation.yml', 'backend/empty.env']) {
    mkdirSync(dirname(join(checkout, file)), { recursive: true });
    copyFileSync(join(root, file), join(checkout, file));
  }
  const versions = JSON.parse(readFileSync(join(root, 'backend/versions.json'), 'utf8'));
  // Real Docker/DB, deliberately failing disposable targets; never alter the working checkout.
  writeFileSync(join(checkout, 'backend/Dockerfile'), `FROM ${versions.pythonImage}\nENTRYPOINT ${JSON.stringify(['python', '-c', python])}\n`);
  writeFileSync(join(checkout, 'backend/Dockerfile.contracts'), `FROM ${versions.nodeImage}\nENTRYPOINT ["node", "-e", "console.log('FOUNDATION_FIXTURE_NODE_OK')"]\n`);
  writeFileSync(join(checkout, '.env'), 'COMPOSE_FILE=foreign-compose.yml\nPOSTGRES_PASSWORD=synthetic-poison-not-used\n');
  return join(checkout, 'scripts/python-foundation.mjs');
}
const invoke = (entry, args, options = {}) => {
  const result = spawnSync(process.execPath, [entry, ...args], {
    encoding: 'utf8', timeout: 30_000, ...options,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  assert.doesNotMatch(result.stderr, /MODULE_NOT_FOUND|SyntaxError/);
  return result;
};

test('cleanup rejects a foreign project before accessing Docker', () => {
  const result = invoke(cli, ['cleanup', 'opengym'], { env: { ...process.env, PATH: '' } });
  assert.equal(result.status, 1, 'foreign cleanup must fail, not report success');
  assert.match(result.stderr, /Refusing non-test target/);
  assert.doesNotMatch(result.stderr, /ENOENT|Docker unavailable|not found/i);
});

test('run rejects an unknown group before accessing Docker', () => {
  const result = invoke(cli, ['run', 'not-a-group'], { env: { ...process.env, PATH: '' } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unknown Python Foundation group/);
});

test('config excludes instance dotenv, Compose overrides, personal mounts and published ports', t => {
  const checkout = mkdtempSync(join(tmpdir(), 'python-foundation-config-'));
  t.after(() => rmSync(checkout, { recursive: true, force: true }));
  // Copy only CLI/config inputs; never expose the real checkout's .env to Compose.
  for (const path of ['scripts/python-foundation.mjs', 'compose.python-foundation.yml',
    'backend/empty.env', 'backend/versions.json', 'api/foundation/versions.json']) {
    if (!existsSync(join(root, path))) continue;
    mkdirSync(dirname(join(checkout, path)), { recursive: true });
    copyFileSync(join(root, path), join(checkout, path));
  }
  const cwd = join(checkout, 'caller');
  mkdirSync(cwd);
  const override = join(checkout, 'foreign-compose.yml');
  writeFileSync(override, 'services:\n  instance-leak:\n    image: synthetic-invalid:never-run\n    ports: ["18080:8080"]\n    volumes: ["./personal-data:/data"]\n');
  for (const dir of [checkout, cwd]) {
    writeFileSync(join(dir, '.env'), `COMPOSE_FILE=${override.replaceAll('\\', '/')}\nPOSTGRES_PASSWORD=dotenv-must-not-be-inherited\n`);
  }
  const envFile = join(checkout, 'foreign.env');
  writeFileSync(envFile, 'POSTGRES_PASSWORD=env-file-must-not-be-inherited\n');
  const result = invoke(join(checkout, 'scripts/python-foundation.mjs'), ['config'], {
    cwd, env: { ...process.env, COMPOSE_FILE: override, COMPOSE_PROJECT_NAME: 'opengym-personal',
      COMPOSE_ENV_FILES: envFile, COMPOSE_PROFILES: 'personal-profile',
      DATA_DIR: '/personal-data', POSTGRES_PASSWORD: 'shell-must-not-be-inherited',
      DATABASE_URL: 'shell-must-not-be-inherited', COACH_AUTH_DIR: '/personal-coach-auth' },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(result.stdout.trim(), 'config must emit the effective isolated Compose configuration');
  const config = JSON.parse(result.stdout);
  assert.match(config.name, /^opengym-python-foundation-test(?:-[a-f0-9]{16})?$/);
  const services = Object.values(config.services ?? {});
  assert.ok(services.length >= 2, 'configuration must include the real DB and test runner, not an empty plan');
  assert.ok(Object.keys(config.volumes ?? {}).length, 'configuration must declare its own volume');
  assert.ok(Object.keys(config.networks ?? {}).length, 'configuration must declare its own private network');
  for (const network of Object.values(config.networks)) assert.equal(network.internal, true);
  for (const resource of [...Object.values(config.networks), ...Object.values(config.volumes)]) {
    assert.ok(!resource.external, 'no external networks or volumes');
    assert.ok(resource.name?.startsWith(`${config.name}_`), 'resource names must belong to this test project');
  }
  assert.ok(!Object.keys(config.secrets ?? {}).length, 'no instance secrets');
  for (const service of services) {
    assert.ok(!service.ports?.length, 'no published ports');
    assert.ok(!service.env_file?.length, 'no inherited env files');
    assert.ok(!service.network_mode, 'no host or shared network namespace');
    assert.ok(!service.privileged);
    for (const volume of service.volumes ?? []) {
      assert.equal(volume.type, 'volume', 'no host bind mounts');
      assert.ok(config.volumes[volume.source], 'mounts must use declared project-owned volumes');
    }
    assert.ok(Object.keys(service.networks ?? {}).length, 'each service must use the private network');
    for (const name of Object.keys(service.networks)) assert.equal(config.networks[name]?.internal, true);
  }
  assert.doesNotMatch(JSON.stringify(config), /must-not-be-inherited|instance-leak|opengym-personal|personal-data|personal-coach-auth|docker\.sock/);
});

test('cleanup rejects mixed ownership before removing anything and preserves a foreign sentinel', t => {
  ok(docker('version', '--format', '{{.Server.Version}}'));
  const token = randomBytes(8).toString('hex');
  const project = `opengym-python-foundation-test-${token}`;
  const probeLabel = `org.opengym.python-foundation.probe=${token}`;
  const resources = [];
  t.after(() => {
    const errors = [];
    for (const { type, name, snapshot } of resources.reverse()) {
      try {
        const remaining = ok(docker(type, 'ls', '--quiet', ...(type === 'network' ? ['--no-trunc'] : []),
          '--filter', `label=${probeLabel}`)).split(/\s+/);
        const id = type === 'network' ? snapshot.Id : name;
        if (!remaining.includes(id)) continue;
        const item = JSON.parse(ok(docker(type, 'inspect', name)))[0];
        assert.equal(item.Labels['org.opengym.python-foundation.probe'], token, 'only remove this test\'s resources');
        ok(docker(type, 'rm', name));
      } catch (error) { errors.push(error); }
    }
    assert.equal(errors.length, 0, errors.map(error => error.message).join('\n'));
  });
  for (const [type, name, labels] of [
    ['volume', `${project}_postgres-data`, ['com.docker.compose.project=' + project,
      'com.docker.compose.volume=postgres-data', 'com.docker.compose.service=foundation-db',
      'org.opengym.python-foundation=synthetic']],
    ['network', `${project}_private`, ['com.docker.compose.project=' + project,
      'com.docker.compose.network=private', 'com.docker.compose.service=private',
      'org.opengym.python-foundation=foreign']],
    ['volume', `opengym-python-foundation-sentinel-${token}`, ['com.docker.compose.project=unrelated-' + token,
      'org.opengym.python-foundation=foreign']],
  ]) {
    ok(docker(type, 'create', ...(type === 'network' ? ['--internal'] : []),
      '--label', probeLabel, ...labels.flatMap(label => ['--label', label]), name));
    const snapshot = JSON.parse(ok(docker(type, 'inspect', name)))[0];
    assert.equal(snapshot.Labels['org.opengym.python-foundation.probe'], token);
    resources.push({ type, name, snapshot });
  }
  const result = invoke(cli, ['cleanup', project]);
  for (const { type, name, snapshot } of resources) {
    assert.deepEqual(JSON.parse(ok(docker(type, 'inspect', name)))[0], snapshot,
      `${type} ${name} must remain unchanged, including the foreign sentinel`);
  }
  console.log('Mixed-ownership preflight: owned volume, foreign network and unrelated sentinel unchanged');
  assert.equal(result.status, 1, 'mixed ownership must fail, not report successful cleanup');
  assert.match(result.stderr, /Refusing unverified .*resource/);
});

test('cleanup finds a project-named volume even when its project label is foreign', t => {
  const token = randomBytes(8).toString('hex');
  const project = `opengym-python-foundation-test-${token}`;
  const name = `${project}_postgres-data`;
  ok(docker('volume', 'create', '--label', `org.opengym.python-foundation.probe=${token}`,
    '--label', 'com.docker.compose.project=foreign-' + token,
    '--label', 'org.opengym.python-foundation=synthetic',
    '--label', 'com.docker.compose.service=foundation-db', '--label', 'com.docker.compose.volume=postgres-data', name));
  t.after(() => {
    const item = JSON.parse(ok(docker('volume', 'inspect', name)))[0];
    assert.equal(item.Labels['org.opengym.python-foundation.probe'], token);
    ok(docker('volume', 'rm', name));
  });
  const snapshot = JSON.parse(ok(docker('volume', 'inspect', name)))[0];
  const result = invoke(cli, ['cleanup', project]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Refusing unverified .*resource/);
  assert.deepEqual(JSON.parse(ok(docker('volume', 'inspect', name)))[0], snapshot);
});

for (const field of ['service', 'name']) {
  test(`cleanup rejects a synthetic volume with a mismatched ${field}`, t => {
    const token = randomBytes(8).toString('hex');
    const project = `opengym-python-foundation-test-${token}`;
    const name = `${project}_${field === 'name' ? 'unexpected' : 'postgres-data'}`;
    ok(docker('volume', 'create', '--label', `org.opengym.python-foundation.probe=${token}`,
      '--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.python-foundation=synthetic',
      '--label', `com.docker.compose.service=${field === 'service' ? 'foreign-service' : 'foundation-db'}`,
      '--label', 'com.docker.compose.volume=postgres-data', name));
    t.after(() => {
      assert.equal(inspect('volume', name).Labels['org.opengym.python-foundation.probe'], token);
      ok(docker('volume', 'rm', name));
    });
    const snapshot = inspect('volume', name);
    const result = invoke(cli, ['cleanup', project]);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Refusing unverified .*resource/);
    assert.deepEqual(inspect('volume', name), snapshot);
  });
}

test('contracts fails explicitly when its Docker endpoint is unavailable', () => {
  const result = invoke(cli, ['run', 'contracts'], { env: { ...process.env,
    DOCKER_HOST: 'tcp://127.0.0.1:1', DOCKER_CONTEXT: '', DOCKER_TLS_VERIFY: '', DOCKER_CERT_PATH: '' } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Docker (container failed|unavailable)/);
});

test('known unfinished groups fail explicitly instead of reporting successful proofs', () => {
  for (const group of ['all']) {
    const result = invoke(cli, ['run', group], { env: { ...process.env, PATH: '' } });
    assert.equal(result.status, 1, group);
    assert.match(result.stderr, /group not implemented/);
  }
});

test('run environment executes Python and Node targets and removes its own resources', () => {
  const result = invoke(cli, ['run', 'environment'], { timeout: 600_000, maxBuffer: 8 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /FOUNDATION_NODE_TARGET_OK/);
  assert.ok(result.stdout.includes('FOUNDATION_NODE_API_OK'), 'environment must prove ordinary API health without PostgreSQL');
  assert.match(result.stdout, /FOUNDATION_ENVIRONMENT_OK/);
  assert.match(result.stdout, /Python Foundation cleanup complete/);
  const project = result.stdout.match(/Python Foundation project: (opengym-python-foundation-test-[a-f0-9]{16})/)?.[1];
  assert.ok(project, 'print the exact project for bounded manual cleanup after hard kill');
  for (const type of ['container', 'volume', 'network', 'image']) {
    assert.equal(ok(docker(type, 'ls', '--quiet', ...(type === 'container' ? ['--all'] : []),
      '--filter', `label=com.docker.compose.project=${project}`)), '', `no leftover ${type}`);
  }
});

test('real containers enforce isolation and cleanup refuses a shared image before preserving the sentinel', t => {
  const token = randomBytes(8).toString('hex');
  const project = `opengym-python-foundation-test-${token}`;
  const sentinel = `opengym-python-foundation-sentinel-${token}`;
  const alias = `opengym-python-foundation-alias-${token}:sentinel`;
  assertProjectEmpty(project);
  ok(docker('volume', 'create', '--label', `org.opengym.python-foundation.probe=${token}`,
    '--label', `com.docker.compose.project=unrelated-${token}`, sentinel));
  const snapshot = inspect('volume', sentinel);
  let aliasImage;
  t.after(() => {
    try {
      if (aliasImage) {
        assert.equal(inspect('image', alias).Id, aliasImage);
        ok(docker('image', 'rm', alias));
      }
      const cleaned = invoke(cli, ['cleanup', project]);
      assert.equal(cleaned.status, 0, cleaned.stderr);
      assertProjectEmpty(project);
    } finally {
      assert.equal(inspect('volume', sentinel).Labels['org.opengym.python-foundation.probe'], token);
      ok(docker('volume', 'rm', sentinel));
    }
  });
  ok(compose(project, 'build', 'foundation-test', 'foundation-contracts'));
  ok(compose(project, 'up', '--detach', '--wait', '--wait-timeout', '60', 'foundation-db'));
  const containers = [['foundation-db', ok(compose(project, 'ps', '--quiet', 'foundation-db'))]];
  for (const service of ['foundation-test', 'foundation-contracts']) {
    // An idle probe with a finite lifetime, not a sleep used to guess readiness.
    containers.push([service, ok(compose(project, 'run', '--detach', '--no-deps', '--entrypoint', '/bin/sh',
      service, '-ec', 'exec sleep 300'))]);
  }
  for (const [service, id] of containers) {
    const item = inspect('container', id);
    assert.equal(item.State.Running, true);
    assert.equal(item.Config.User, '1000:1000');
    assert.equal(item.Config.Labels['com.docker.compose.project'], project);
    assert.equal(item.Config.Labels['com.docker.compose.service'], service);
    assert.equal(item.Config.Labels['org.opengym.python-foundation'], 'synthetic');
    assert.equal(item.HostConfig.ReadonlyRootfs, true);
    assert.equal(item.HostConfig.Privileged, false);
    assert.deepEqual(item.HostConfig.CapDrop, ['ALL']);
    assert.ok(item.HostConfig.SecurityOpt.includes('no-new-privileges:true'));
    assert.equal(Object.keys(item.HostConfig.PortBindings ?? {}).length, 0);
    // Docker also serializes named volumes in Binds; Mounts.Type below distinguishes host binds.
    for (const bind of item.HostConfig.Binds ?? []) {
      assert.equal(service, 'foundation-db');
      assert.equal(bind, `${project}_postgres-data:/var/lib/postgresql:rw`);
    }
    assert.deepEqual(Object.keys(item.NetworkSettings.Networks), [`${project}_private`]);
    assert.ok(item.HostConfig.Tmpfs['/tmp']);
    for (const options of Object.values(item.HostConfig.Tmpfs)) {
      for (const flag of ['noexec', 'nosuid', 'nodev']) assert.ok(options.split(',').includes(flag));
    }
    for (const mount of item.Mounts) {
      if (mount.Type === 'tmpfs') { assert.ok(item.HostConfig.Tmpfs[mount.Destination]); continue; }
      assert.equal(mount.Type, 'volume', 'no personal bind mounts or Docker socket');
      assert.equal(service, 'foundation-db');
      assert.equal(mount.Name, `${project}_postgres-data`);
      assert.equal(mount.Destination, '/var/lib/postgresql');
      assert.equal(mount.RW, true);
    }
    ok(docker('exec', id, 'sh', '-ec', `
      test "$(id -u)" = 1000; test "$(id -g)" = 1000
      grep -Eq '^CapEff:[[:space:]]+0000000000000000$' /proc/self/status
      grep -Eq '^NoNewPrivs:[[:space:]]+1$' /proc/self/status
      grep -Eq ' / [^ ]+ ro[, ]' /proc/mounts
      test "$(stat -f -c %T /tmp)" = tmpfs
      test ! -e /tmp/probe-${token}
      printf ${service} > /tmp/probe-${token}
      for flag in noexec nosuid nodev; do grep ' /tmp tmpfs ' /proc/mounts | grep -qw "$flag"; done
    `));
  }
  for (const [service, id] of containers) {
    ok(docker('exec', id, 'sh', '-ec', `grep -qx ${service} /tmp/probe-${token}; rm /tmp/probe-${token}`));
  }
  const network = inspect('network', `${project}_private`);
  const volume = inspect('volume', `${project}_postgres-data`);
  for (const item of [network, volume]) {
    assert.equal(item.Labels['com.docker.compose.project'], project);
    assert.equal(item.Labels['org.opengym.python-foundation'], 'synthetic');
  }
  assert.equal(network.Internal, true);
  assert.equal(network.Labels['com.docker.compose.network'], 'private');
  assert.equal(network.Labels['com.docker.compose.service'], 'private');
  assert.equal(Object.keys(network.Containers).length, 3);
  assert.equal(volume.Labels['com.docker.compose.service'], 'foundation-db');
  assert.equal(volume.Labels['com.docker.compose.volume'], 'postgres-data');
  for (const service of ['foundation-test', 'foundation-contracts']) {
    const item = inspect('image', `${project}-${service}:local`);
    assert.equal(item.Config.Labels['com.docker.compose.project'], project);
    assert.equal(item.Config.Labels['com.docker.compose.service'], service);
    assert.equal(item.Config.Labels['org.opengym.python-foundation'], 'synthetic');
    assert.deepEqual(item.RepoTags, [`${project}-${service}:local`]);
  }
  assert.equal(ok(docker('exec', containers[0][1], 'psql', '-U', 'python_foundation_bootstrap',
    '-d', 'python_foundation_test', '-Atc', "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")), '0');

  const image = `${project}-foundation-test:local`;
  assert.equal(ok(docker('image', 'ls', '--quiet', '--filter', `reference=${alias}`)), '');
  aliasImage = inspect('image', image).Id;
  ok(docker('image', 'tag', image, alias));
  const rejected = invoke(cli, ['cleanup', project]);
  assert.equal(rejected.status, 1);
  assert.match(rejected.stderr, /Refusing unverified .*resource/);
  for (const [, id] of containers) assert.equal(inspect('container', id).State.Running, true);
  assert.deepEqual(inspect('volume', volume.Name), volume, 'preflight must not remove even verified resources');
  assert.deepEqual(inspect('volume', sentinel), snapshot);
  assert.equal(inspect('image', alias).Id, aliasImage);
  ok(docker('image', 'rm', alias));
  aliasImage = undefined;
  const cleaned = invoke(cli, ['cleanup', project]);
  assert.equal(cleaned.status, 0, cleaned.stderr);
  assertProjectEmpty(project);
  assert.deepEqual(inspect('volume', sentinel), snapshot);
  console.log('Real isolation: UID/GID 1000, read-only root, private tmpfs/network/volume; shared-tag preflight and sentinel preserved');
});

test('a deliberate test failure after DB startup returns nonzero, cleans up and preserves a foreign sentinel', t => {
  const entry = failureCheckout(t, "import socket,sys; socket.create_connection(('foundation-db',5432),5).close(); print('FOUNDATION_EXPECTED_TEST_FAILURE',file=sys.stderr,flush=True); sys.exit(23)");
  const token = randomBytes(8).toString('hex');
  const sentinel = `opengym-python-foundation-sentinel-${token}`;
  ok(docker('volume', 'create', '--label', `org.opengym.python-foundation.probe=${token}`,
    '--label', `com.docker.compose.project=unrelated-${token}`, sentinel));
  const snapshot = inspect('volume', sentinel);
  let project;
  t.after(() => {
    try {
      if (project) {
        const cleaned = invoke(cli, ['cleanup', project]);
        assert.equal(cleaned.status, 0, cleaned.stderr);
        assertProjectEmpty(project);
      }
    } finally {
      assert.equal(inspect('volume', sentinel).Labels['org.opengym.python-foundation.probe'], token);
      ok(docker('volume', 'rm', sentinel));
    }
  });
  const result = invoke(entry, ['run', 'environment'], { timeout: 600_000, maxBuffer: 8 * 1024 * 1024,
    env: { ...process.env, COMPOSE_FILE: 'foreign-compose.yml', COMPOSE_PROJECT_NAME: 'opengym-personal',
      POSTGRES_PASSWORD: 'synthetic-poison-not-used', DATA_DIR: '/not-a-real-data-directory' } });
  project = result.stdout.match(/Python Foundation project: (opengym-python-foundation-test-[a-f0-9]{16})/)?.[1];
  assert.ok(project);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /FOUNDATION_EXPECTED_TEST_FAILURE/);
  assert.match(result.stdout, /FOUNDATION_FIXTURE_NODE_OK/);
  assert.match(result.stdout, /Python Foundation cleanup complete/);
  assert.doesNotMatch(result.stdout, /FOUNDATION_ENVIRONMENT_OK/);
  assertProjectEmpty(project);
  assert.deepEqual(inspect('volume', sentinel), snapshot);
  console.log('Deliberate target failure after a real DB connection: exit 1, automatic cleanup, sentinel unchanged');
});

test('the real Node target rejects an API process that exits before readiness without crediting success', t => {
  const entry = failureCheckout(t, "raise SystemExit('FOUNDATION_PYTHON_MUST_NOT_RUN')");
  const checkout = dirname(dirname(entry));
  const versions = JSON.parse(readFileSync(join(root, 'backend/versions.json'), 'utf8'));
  for (const file of ['contracts-run.mjs', 'versions.json']) copyFileSync(join(root, 'backend', file), join(checkout, 'backend', file));
  writeFileSync(join(checkout, 'backend/api-start-failure.js'), 'process.exit(23);\n');
  writeFileSync(join(checkout, 'backend/Dockerfile.contracts'), `FROM ${versions.nodeImage}\nWORKDIR /app\nCOPY backend/contracts-run.mjs backend/versions.json ./\nCOPY backend/api-start-failure.js ./api/server.js\nENTRYPOINT ["node", "contracts-run.mjs"]\n`);
  let project;
  t.after(() => {
    if (project) {
      const cleaned = invoke(cli, ['cleanup', project]);
      assert.equal(cleaned.status, 0, cleaned.stderr);
      assertProjectEmpty(project);
    }
  });
  const result = invoke(entry, ['run', 'environment'], { timeout: 600_000, maxBuffer: 8 * 1024 * 1024 });
  project = result.stdout.match(/Python Foundation project: (opengym-python-foundation-test-[a-f0-9]{16})/)?.[1];
  assert.ok(project);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /FOUNDATION_NODE_TARGET_FAILED/);
  assert.doesNotMatch(result.stdout, /FOUNDATION_NODE_API_OK|FOUNDATION_NODE_TARGET_OK|FOUNDATION_ENVIRONMENT_OK/);
  assert.doesNotMatch(result.stderr, /FOUNDATION_PYTHON_MUST_NOT_RUN/);
  assert.match(result.stdout, /Python Foundation cleanup complete/);
  assertProjectEmpty(project);
});

test('hard kill leaves only its own resources and the printed project supports explicit cleanup', async t => {
  const entry = failureCheckout(t, "import socket,threading,sys; socket.create_connection(('foundation-db',5432),5).close(); print('FOUNDATION_INTERRUPT_READY',flush=True); threading.Event().wait(120); sys.exit(23)");
  const child = spawn(process.execPath, [entry, 'run', 'environment'], { stdio: ['ignore', 'pipe', 'pipe'] });
  const closed = new Promise(resolve => child.once('close', (code, signal) => resolve({ code, signal })));
  let project;
  let output = '';
  t.after(async () => {
    child.kill('SIGKILL');
    await closed;
    if (project) {
      const cleaned = invoke(cli, ['cleanup', project]);
      assert.equal(cleaned.status, 0, cleaned.stderr);
      assertProjectEmpty(project);
    }
  });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('CLI did not reach the coordinated interruption point')), 180_000);
    const failed = () => { clearTimeout(timer); reject(new Error('CLI exited before the interruption point')); };
    child.once('error', failed);
    child.once('exit', failed);
    child.stderr.resume();
    child.stdout.on('data', chunk => {
      output += chunk;
      project ??= output.match(/Python Foundation project: (opengym-python-foundation-test-[a-f0-9]{16})/)?.[1];
      if (output.length > 8 * 1024 * 1024) { failed(); child.kill('SIGKILL'); return; }
      if (output.includes('FOUNDATION_INTERRUPT_READY')) { clearTimeout(timer); resolve(); }
    });
  });
  assert.ok(project);
  assert.ok(child.kill('SIGKILL'));
  assert.equal((await closed).signal, 'SIGKILL');
  assert.doesNotMatch(output, /Python Foundation cleanup complete/);
  assert.ok(ok(docker('container', 'ls', '--quiet', '--filter', `label=com.docker.compose.project=${project}`)),
    'real DB/probe resources must still exist after hard kill, not a no-op cleanup proof');
  const cleaned = invoke(cli, ['cleanup', project]);
  assert.equal(cleaned.status, 0, cleaned.stderr);
  assertProjectEmpty(project);
  console.log('Coordinated SIGKILL: resources remained, exact-project manual cleanup removed them');
});
