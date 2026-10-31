import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { copyFileSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../', import.meta.url));
const versions = JSON.parse(readFileSync(join(root, 'backend/versions.json'), 'utf8'));
const invoke = (command, args, options = {}) => spawnSync(command, args, {
  cwd: root, encoding: 'utf8', timeout: 300_000, maxBuffer: 8 * 1024 * 1024, ...options,
});
const ok = result => {
  assert.ifError(result.error);
  assert.equal(result.status, 0, 'command failed; inspect the retained build evidence');
  return result.stdout.trim();
};

for (const target of ['python', 'contracts']) test(`${target}: owned cold/repeated/source/test/metadata/manifest cache probes`, t => {
  const token = randomBytes(8).toString('hex');
  const builder = `opengym-platform-build-${token}`;
  const fixture = mkdtempSync(join(tmpdir(), 'opengym-platform-build-'));
  const evidence = mkdtempSync(join(tmpdir(), `opengym-platform-${target}-evidence-`));
  console.log(JSON.stringify({ code: 'PLATFORM_BUILD_EVIDENCE', target, builder, evidence }));
  const tags = new Set();
  let created = false;
  t.after(() => {
    try {
      for (const tag of tags) {
        const image = JSON.parse(ok(invoke('docker', ['image', 'inspect', tag])))[0];
        assert.equal(image.Config.Labels['org.opengym.platform.build-probe'], token);
        assert.ok(image.RepoTags.every(name => tags.has(name)), 'refuse a shared probe image');
        ok(invoke('docker', ['image', 'rm', tag]));
      }
    } finally {
      if (created) ok(invoke('docker', ['buildx', 'rm', builder]));
      rmSync(fixture, { recursive: true, force: true });
    }
    for (const type of ['container', 'volume']) {
      assert.equal(ok(invoke('docker', [type, 'ls', '--quiet', ...(type === 'container' ? ['--all'] : []),
        '--filter', `name=buildx_buildkit_${builder}`])), '');
    }
    assert.equal(ok(invoke('docker', ['image', 'ls', '--quiet', '--filter', `label=org.opengym.platform.build-probe=${token}`])), '');
  });
  // Only selected non-ignored build inputs, never dotenv, ignored files or personal data.
  const files = ok(invoke('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'])).split('\0').filter(file => file && existsSync(join(root, file)));
  const allowed = /^(?:shared\/|catalogue\/|backend\/|api\/(?:[^/]+\.(?:js|json|yaml)$|coach\/|test\/|scripts\/check-core-loadable\.mjs$)|frontend\/(?:(?:package\.json|pnpm-lock\.yaml|index\.html|capacitor\.config\.json)$|vite\.config\.js$|src\/|scripts\/|public\/|android\/|ios\/)|scripts\/(?:build-api-docs|build-coach-assets|build-coach-library|shared-client.test|formats-and-bundles.test)\.mjs$|scripts\/catalogue\/|LICENSE$|\.dockerignore$)/;
  for (const file of files.filter(file => allowed.test(file))) {
    assert.ok(lstatSync(join(root, file)).isFile(), 'build inputs must not follow links');
    mkdirSync(dirname(join(fixture, file)), { recursive: true });
    copyFileSync(join(root, file), join(fixture, file));
  }
  ok(invoke('docker', ['buildx', 'create', '--name', builder, '--driver', 'docker-container',
    '--driver-opt', `image=${versions.buildkitImage}`]));
  created = true;
  const revision = ok(invoke('git', ['rev-parse', 'HEAD']));
  writeFileSync(join(evidence, 'context.json'), JSON.stringify({ revision, target, builder,
    platform: 'linux/amd64', versions, scope: 'selected working inputs plus probe-only mutations; no shared cache or production proof' }, null, 2));
  const context = target === 'python' ? join(fixture, 'backend') : fixture;
  const dockerfile = join(fixture, 'backend', target === 'python' ? 'Dockerfile' : 'Dockerfile.contracts');
  function build(phase, cached, expected = 0) {
    const tag = `opengym-platform-build-${token}:${phase}`;
    const args = ['buildx', 'build', '--builder', builder, '--platform', 'linux/amd64', '--progress=plain',
      ...(target === 'python' ? ['--target', 'test'] : []), '--load', '--tag', tag, '--label', `org.opengym.platform.build-probe=${token}`, '-f', dockerfile, context];
    const started = performance.now();
    const result = invoke('docker', args);
    const log = result.stdout + result.stderr;
    writeFileSync(join(evidence, `${phase}.log`), log);
    writeFileSync(join(evidence, `${phase}.json`), JSON.stringify({ command: ['docker', ...args],
      seconds: (performance.now() - started) / 1000, status: result.status, cache: phase === 'cold' ? 'new isolated builder, empty layer/package caches' : 'same owned builder' }, null, 2));
    assert.ifError(result.error);
    if (result.status === 0) tags.add(tag);
    assert.equal(result.status, expected, `${target}/${phase}: inspect ${evidence}`);
    if (expected !== 0) {
      assert.match(log, target === 'python' ? /lockfile.*needs to be updated|lockfile.*not up.to.date/i : /OUTDATED_LOCKFILE|outdated lockfile|not up.to.date|doesn.t match/i);
      return;
    }
    const installs = [...new Map([...log.matchAll(/^#(\d+) .*RUN --mount=.*(?:uv lock --check|pnpm install).*$/gm)]
      .map(match => [match[1], match])).values()];
    assert.equal(installs.length, target === 'python' ? 1 : 2, 'identify actual dependency steps, not timing guesses');
    for (const match of installs) {
      const expectedCache = phase === 'manifest' && target === 'contracts' ? !match[0].includes('--no-optional') : cached;
      assert.equal(new RegExp(`^#${match[1]} CACHED$`, 'm').test(log), expectedCache, `${phase}: dependency layer ${match[1]}`);
    }
    ok(invoke('docker', ['run', '--rm', '--network', 'none', '--user', '1000:1000', '--read-only',
      '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=67108864',
      '--entrypoint', target === 'python' ? '/app/.venv/bin/python' : 'node', tag,
      ...(target === 'python' ? ['-c', "import asyncpg,fastapi; from opengym_platform.application import create_app"] :
        ['-e', "require('node:assert/strict').equal(process.versions.node, '22.23.2'); require('/app/api/node_modules/undici')"]) ]));
  }
  build('cold', false);
  build('repeat', true);
  for (const [phase, file] of [
    ['source', target === 'python' ? 'backend/src/opengym_platform/core/database.py' : 'api/server.js'],
    ['test', target === 'python' ? 'backend/tests/platform/test_lifecycle.py' : 'api/test/password.test.js'],
    ['metadata', target === 'python' ? 'backend/Dockerfile' : 'backend/Dockerfile.contracts'],
  ]) {
    const path = join(fixture, file);
    const original = readFileSync(path, 'utf8');
    writeFileSync(path, original + (phase === 'metadata' ? '\nLABEL org.opengym.cache-probe="metadata"\n' :
      target === 'python' ? '\n# cache probe\n' : '\n// cache probe\n'));
    try { build(phase, true); } finally { writeFileSync(path, original); }
  }
  const manifest = join(fixture, target === 'python' ? 'backend/pyproject.toml' : 'api/package.json');
  const lock = join(fixture, target === 'python' ? 'backend/uv.lock' : 'api/pnpm-lock.yaml');
  const originalManifest = readFileSync(manifest, 'utf8');
  const originalLock = readFileSync(lock, 'utf8');
  if (target === 'python') {
    writeFileSync(manifest, originalManifest.replace('fastapi==0.161.1', 'fastapi===0.161.1'));
    writeFileSync(lock, originalLock.replace('name = "fastapi", specifier = "==0.161.1"', 'name = "fastapi", specifier = "===0.161.1"'));
  } else {
    const pkg = JSON.parse(originalManifest);
    const entries = [...originalLock.matchAll(
      /^      undici:\r?\n        specifier: ([^\r\n]+)\r?\n        version: (\d+\.\d+\.\d+)\r?$/gm
    )];
    assert.equal(entries.length, 1, 'expected one supported Undici importer entry');
    const [entry, specifier, version] = entries[0];
    assert.equal(specifier, pkg.dependencies.undici);
    const exact = specifier === version ? `=${version}` : version;
    pkg.dependencies.undici = exact;
    writeFileSync(manifest, JSON.stringify(pkg, null, 2));
    writeFileSync(lock, originalLock.replace(
      entry, entry.replace(`specifier: ${specifier}`, `specifier: ${exact}`)
    ));
  }
  try {
    // Same installed versions, coherent changed constraints: no dependency upgrade.
    build('manifest', false);
  } finally {
    writeFileSync(manifest, originalManifest);
    writeFileSync(lock, originalLock);
  }
  if (target === 'python') {
    writeFileSync(manifest, originalManifest.replace('version = "0.0.0"', 'version = "0.0.1"'));
  } else {
    const pkg = JSON.parse(originalManifest);
    delete pkg.dependencies.undici;
    writeFileSync(manifest, JSON.stringify(pkg, null, 2));
  }
  build('inconsistent', false, 1);
  assert.equal(readFileSync(lock, 'utf8'), originalLock, 'failed frozen build must not update its lock');
});
