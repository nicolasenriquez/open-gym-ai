import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const invoke = (...args) => spawnSync(process.execPath, ['scripts/platform.mjs', ...args], {
  encoding: 'utf8', timeout: 10_000, env: { ...process.env, PATH: '', COMPOSE_FILE: 'foreign.yml',
    DOCKER_HOST: process.platform === 'win32' ? 'npipe:////./pipe/opengym-platform-missing' : 'unix:///opengym-platform-missing.sock',
    DOCKER_CONTEXT: '', DOCKER_TLS_VERIFY: '', DOCKER_CERT_PATH: '' },
});

test('ownership: foreign and Foundation cleanup targets are rejected before Docker', () => {
  for (const target of ['opengym', 'opengym-python-foundation-test-aaaaaaaaaaaaaaaa']) {
    const result = invoke('cleanup', target);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Refusing non-test target/);
  }
});

test('undelivered suites, cases and malformed commands return usage exit 2 before Docker', () => {
  for (const args of [[], ['verify'], ['verify', 'training_browser'], ['verify', 'harness', '--case', 'future'],
    ['verify', 'harness', '--case'], ['verify', 'harness', '--config', 'foreign.json'], ['verify', 'unknown']]) {
    const result = invoke(...args);
    assert.equal(result.status, 2);
    assert.doesNotMatch(result.stderr, /Docker|ENOENT|SyntaxError|MODULE_NOT_FOUND/);
  }
});

test('a missing Docker prerequisite fails without crediting a contract proof', () => {
  const result = invoke('verify', 'contracts', '--case', 'baseline');
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Docker (unavailable|container failed)/);
  assert.doesNotMatch(result.stdout, /PLATFORM_CASE_OK/);
});

test('frozen expectations reject changed fixtures instead of regenerating them', t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-baseline-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'scripts'));
  cpSync('scripts/platform-baseline.mjs', join(root, 'scripts/platform-baseline.mjs'));
  const manifest = JSON.parse(readFileSync('backend/contracts/port-baseline.v1.json', 'utf8'));
  for (const path of Object.keys(manifest.files)) {
    const destination = join(root, path);
    mkdirSync(join(destination, '..'), { recursive: true });
    cpSync(path, destination);
  }
  cpSync('backend/contracts/port-baseline.v1.json', join(root, 'backend/contracts/port-baseline.v1.json'));
  const check = () => spawnSync(process.execPath, ['scripts/platform-baseline.mjs'], { cwd: root, encoding: 'utf8' });
  assert.equal(check().status, 0);
  const fixture = join(root, 'backend/contracts/http-baseline.v1.json');
  writeFileSync(fixture, readFileSync(fixture, 'utf8').replace('not signed in', 'different error'));
  assert.equal(check().status, 1);
  assert.match(check().stderr, /PLATFORM_BASELINE_REJECTED/);
});

test('empty output, skipped proofs and failed commands never receive a passing case marker', t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-platform-proof-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'scripts'));
  mkdirSync(join(root, 'backend'));
  for (const file of ['platform.mjs', 'platform-baseline.mjs', 'synthetic-harness.mjs']) {
    cpSync(join('scripts', file), join(root, 'scripts', file));
  }
  writeFileSync(join(root, 'required.test.mjs'), "import test from 'node:test'; test('required proof', { skip: true }, () => {});\n");
  for (const command of [['-e', ''], ['--test', 'required.test.mjs'], ['-e', 'process.exitCode = 1']]) {
    writeFileSync(join(root, 'backend/platform-suites.json'), JSON.stringify({
      harness: [{ id: 'ownership', target: 'host', command }],
    }));
    const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'verify', 'harness'], {
      cwd: root, encoding: 'utf8', timeout: 10_000,
    });
    assert.equal(result.status, 1);
    assert.doesNotMatch(result.stdout, /PLATFORM_CASE_OK/);
  }
});
