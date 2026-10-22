import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cli = fileURLToPath(new URL('./environment.mjs', import.meta.url));
const { nodeImage } = JSON.parse(readFileSync(new URL('./versions.json', import.meta.url)));
const docker = (...args) => spawnSync('docker', args, { encoding: 'utf8', timeout: 30_000 });
const ok = result => { assert.equal(result.status, 0, result.stderr); return result.stdout.trim(); };

test('all fails explicitly without PostgreSQL instead of skipping proofs', { timeout: 240_000 }, () => {
  const project = `opengym-foundation-test-${randomBytes(8).toString('hex')}`;
  const image = `${project}-foundation-test:latest`;
  try {
    const built = spawnSync('docker', ['build', '--label', `com.docker.compose.project=${project}`,
      '--label', 'com.docker.compose.service=foundation-test', '-t', image,
      fileURLToPath(new URL('.', import.meta.url))], { encoding: 'utf8', timeout: 180_000 });
    assert.equal(built.status, 0, built.stderr);
    const result = docker('run', '--rm', '--network', 'none', '--read-only', '--user', '1000:1000',
      '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp',
      '--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.foundation=synthetic',
      '--label', 'com.docker.compose.service=foundation-test',
      '-e', 'PGHOST=foundation-db', '-e', 'PGPORT=5432', '-e', 'PGDATABASE=foundation_test',
      '-e', 'PGUSER=foundation_bootstrap', '-e', 'PGPASSWORD=synthetic-foundation-only', image, 'all');
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Foundation environment check failed/);
    assert.doesNotMatch(result.stdout, /# pass|# skipped|Foundation environment ready/);
    console.log('Unavailable database: explicit exit 1; no proofs skipped or credited');
  } finally {
    const cleaned = spawnSync(process.execPath, [cli, 'cleanup', project], { encoding: 'utf8', timeout: 30_000 });
    assert.equal(cleaned.status, 0, cleaned.stderr);
    for (const type of ['container', 'volume', 'network', 'image']) {
      const args = [type, 'ls', '--quiet', '--filter', `label=com.docker.compose.project=${project}`];
      if (type === 'container') args.push('--all');
      assert.equal(ok(docker(...args)), '', `${type} must not remain after missing-database proof`);
    }
  }
});

test('cleanup removes only the identified synthetic containers, volume and network', () => {
  const project = `opengym-foundation-test-${randomBytes(8).toString('hex')}`;
  const volume = `${project}_postgres-data`;
  const network = `${project}_private`;
  const sentinel = `${project}_unrelated`;
  const labels = ['--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.foundation=synthetic'];
  let container;
  try {
    ok(docker('volume', 'create', ...labels, volume));
    ok(docker('volume', 'create', sentinel));
    ok(docker('network', 'create', '--internal', ...labels, network));
    container = ok(docker('create', ...labels, '--label', 'com.docker.compose.service=foundation-db',
      '--network', network, '--mount', `type=volume,source=${volume},target=/scratch`, nodeImage, 'true'));
    const result = spawnSync(process.execPath, [cli, 'cleanup', project], { encoding: 'utf8', timeout: 30_000 });
    assert.equal(result.status, 0, result.stderr);
    assert.notEqual(docker('volume', 'inspect', volume).status, 0, 'owned volume must be removed');
    assert.notEqual(docker('network', 'inspect', network).status, 0, 'owned network must be removed');
    assert.notEqual(docker('container', 'inspect', container).status, 0, 'owned container must be removed');
    assert.equal(docker('volume', 'inspect', sentinel).status, 0, 'unrelated volume must survive');
  } finally {
    if (container) docker('container', 'rm', '--force', container);
    docker('volume', 'rm', volume, sentinel);
    docker('network', 'rm', network);
  }
});

test('cleanup refuses mixed-ownership resources before deleting any of them', () => {
  const project = `opengym-foundation-test-${randomBytes(8).toString('hex')}`;
  const volume = `${project}_postgres-data`;
  const network = `${project}_private`;
  try {
    ok(docker('volume', 'create', '--label', `com.docker.compose.project=${project}`,
      '--label', 'org.opengym.foundation=synthetic', volume));
    ok(docker('network', 'create', '--label', `com.docker.compose.project=${project}`, network));
    const result = spawnSync(process.execPath, [cli, 'cleanup', project], { encoding: 'utf8', timeout: 30_000 });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Refusing unverified Foundation resource/);
    assert.equal(docker('volume', 'inspect', volume).status, 0, 'validated resource must survive preflight rejection');
    assert.equal(docker('network', 'inspect', network).status, 0, 'unverified resource must survive');
  } finally {
    docker('volume', 'rm', volume);
    docker('network', 'rm', network);
  }
});

test('all runs every required proof on real PostgreSQL then removes its own resources', { timeout: 300_000 }, () => {
  const result = spawnSync(process.execPath, [cli, 'run', 'all'], {
    encoding: 'utf8', timeout: 290_000,
    env: { ...process.env, COMPOSE_PROJECT_NAME: 'opengym', COMPOSE_FILE: 'docker-compose.yml',
      PGHOST: 'real-database.example', DATABASE_URL: 'must-not-be-inherited' },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Foundation environment ready: Node 22\.23\.2; PostgreSQL 18\.6/);
  for (const count of [4, 12, 7, 20]) assert.match(result.stdout, new RegExp(`# pass ${count}\\b`));
  assert.equal((result.stdout.match(/# pass 12\b/g) ?? []).length, 2, 'pool and recovery must both run');
  assert.doesNotMatch(result.stdout, /# (?:fail|skipped|cancelled) [1-9]/);
  assert.match(result.stdout, /Foundation cleanup complete/);
  const project = result.stdout.match(/Foundation project: (opengym-foundation-test-[a-f0-9]{16})/)?.[1];
  assert.ok(project);
  for (const type of ['container', 'volume', 'network', 'image']) {
    const args = [type, 'ls', '--quiet', '--filter', `label=com.docker.compose.project=${project}`];
    if (type === 'container') args.push('--all');
    assert.equal(ok(docker(...args)), '', `${type} must not remain after run`);
  }
});
