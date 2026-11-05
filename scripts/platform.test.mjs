import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import { EventEmitter } from 'node:events';
import { syncBuiltinESMExports } from 'node:module';
import { runInNewContext } from 'node:vm';
import { writeFile } from 'node:fs/promises';
import { syntheticHarness } from './synthetic-harness.mjs';
import { spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const invoke = (...args) => spawnSync(process.execPath, ['scripts/platform.mjs', ...args], {
  encoding: 'utf8', timeout: 10_000, env: { ...process.env, PATH: '', COMPOSE_FILE: 'foreign.yml',
    DOCKER_HOST: process.platform === 'win32' ? 'npipe:////./pipe/opengym-platform-missing' : 'unix:///opengym-platform-missing.sock',
    DOCKER_CONTEXT: '', DOCKER_TLS_VERIFY: '', DOCKER_CERT_PATH: '' },
});

test('browser evidence collection requires one private run and preserves failed results', async t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-browser-collection-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const training = readFileSync('frontend/e2e/platform/training.mjs', 'utf8');
  assert.match(training, /mkdtemp\('\/tmp\/opengym-browser-evidence-'\)/);
  const harness = readFileSync('scripts/platform.mjs', 'utf8');
  const collector = harness.match(/`(const fs=require\('node:fs'\);[\s\S]*?)`/)[1];
  let output;
  const collect = () => runInNewContext(collector, {
    require: () => ({
      readdirSync: (path, options) => readdirSync(path === '/tmp' ? root : join(root, path.slice(5)), options),
      readFileSync: path => readFileSync(join(root, path.slice(5))),
    }),
    console: { log: value => { output = JSON.parse(value); } },
  });
  assert.throws(collect, /PLATFORM_BROWSER_EVIDENCE_DIRECTORY_INVALID/);
  const evidence = mkdtempSync(join(root, 'opengym-browser-evidence-'));
  const start = training.indexOf('  await writeFile(`${evidence}/result.json`');
  const tail = training.slice(start, training.indexOf('} finally {', start));
  for (const failed of [false, true]) {
    let notifications = 0;
    await runInNewContext('(async()=>{try {\n' + tail + '\n}})()', {
      writeFile, evidence, cases: ['login'], errors: [], stage: 'login',
      process: { versions: { node: '22.23.2' } }, browser: { version: () => 'test' },
      frontend: 'v1+platform-browser-proof', statuses: [], competitors: 0, dropped: false,
      control: async () => { if (++notifications === 1 && failed) throw new Error('notification failed'); },
      page: { screenshot: async () => {} }, console: { error: () => {} },
    });
    collect();
    const result = JSON.parse(Buffer.from(output.find(file => file.name === 'result.json').data, 'base64'));
    assert.equal(result.completed, !failed);
  }
  mkdtempSync(join(root, 'opengym-browser-evidence-'));
  assert.throws(collect, /PLATFORM_BROWSER_EVIDENCE_DIRECTORY_INVALID/);
});

test('synthetic cleanup treats project and service regex components literally', async t => {
  const project = 'test.project', service = 'api.worker';
  let name = '/testXproject-apiYworker-1';
  const calls = [];
  t.mock.method(childProcess, 'spawn', (_program, args) => {
    calls.push(args);
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    queueMicrotask(() => {
      let output = '';
      if (args[0] === 'container' && args[1] === 'ls') output = 'owned';
      if (args[0] === 'container' && args[1] === 'inspect') output = JSON.stringify([{
        Id: 'owned', Name: name, Config: { Labels: {
          'com.docker.compose.project': project, 'com.docker.compose.service': service,
          'org.opengym.test': 'synthetic',
        } },
      }]);
      child.stdout.emit('data', Buffer.from(output));
      child.emit('close', 0);
    });
    return child;
  });
  syncBuiltinESMExports();
  const harness = syntheticHarness({ root: process.cwd(), name: 'Test', label: 'org.opengym.test',
    services: [service], images: [], database: 'db' });
  try {
    for (const invalid of ['/testXproject-api.worker-1', '/test.project-apiYworker-1',
      '/test.project-api.worker-0', '/test.project-api.worker-run-abcdef']) {
      name = invalid;
      await assert.rejects(harness.cleanup(project), /Refusing unverified/);
      assert.equal(calls.some(args => args[1] === 'rm'), false);
    }
    assert.ok(calls.some(args => args.includes('name=^/?test\\.project[-_]')));
    for (const valid of ['/test.project-api.worker-1', '/test.project-api.worker-run-012345abcdef']) {
      name = valid;
      await harness.cleanup(project);
    }
    assert.equal(calls.filter(args => args[1] === 'rm').length, 2);
  } finally {
    t.mock.restoreAll();
    syncBuiltinESMExports();
  }
});

test('verification scripts do not recreate the retired task directory', () => {
  function check(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const file = join(directory, entry.name);
      if (entry.isDirectory()) check(file);
      else if (entry.name.endsWith('.mjs') && file !== join('scripts', 'platform.test.mjs')) {
        const source = readFileSync(file, 'utf8').replaceAll("'.scratch/proof.json'", "''");
        assert.doesNotMatch(source, /['"`][^'"`\r\n]*\.scratch/, file);
      }
    }
  }
  check('scripts');
});

test('ownership: foreign and Foundation cleanup targets are rejected before Docker', () => {
  for (const target of ['opengym', 'opengym-python-foundation-test-aaaaaaaaaaaaaaaa']) {
    const result = invoke('cleanup', target);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Refusing non-test target/);
  }
});

test('undelivered suites, cases and malformed commands return usage exit 2 before Docker', () => {
  for (const args of [[], ['verify'], ['verify', 'future_browser'], ['verify', 'harness', '--case', 'future'],
    ['verify', 'harness', '--case'], ['verify', 'harness', '--config', 'foreign.json'], ['verify', 'unknown'],
    ['verify', 'shared_client', '--case', 'future_formats']]) {
    const result = invoke(...args);
    assert.equal(result.status, 2);
    assert.doesNotMatch(result.stderr, /Docker|ENOENT|SyntaxError|MODULE_NOT_FOUND/);
  }
});

test('gate evidence flags reject missing, repeated and unknown arguments before reading files', () => {
  for (const options of [
    ['--case', 'pre_cutover', '--evidence'],
    ['--case', 'authorized_cutover', '--evidence'],
    ['--case', 'authorized_cutover', '--evidence', 'foreign.json', '--evidence', 'other.json'],
    ['--case', 'acceptance', '--evidence', 'foreign.json'],
    ['--case', 'pre_cutover', '--evidence', 'foreign.json', '--evidence', 'other.json'],
    ['--case', 'pre_cutover', '--evidence', 'foreign.json', '--config', 'foreign.json'],
  ]) {
    const result = invoke('verify', 'gates', ...options);
    assert.equal(result.status, 2);
    assert.doesNotMatch(result.stderr, /Docker|ENOENT|PLATFORM_GATE_EVIDENCE_REJECTED/);
  }
});

test('a missing Docker prerequisite fails without crediting a contract or shared-client proof', () => {
  for (const [suite, selected] of [['contracts', 'python_routes'], ['shared_client', 'canonical_sources'], ['shared_client', 'formats_and_bundles']]) {
    const result = invoke('verify', suite, '--case', selected);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Docker (unavailable|container failed)/);
    assert.doesNotMatch(result.stdout, /PLATFORM_CASE_OK/);
  }
});

test('retired transition baseline cannot be invoked or credited', () => {
  const result = invoke('verify', 'contracts', '--case', 'baseline');
  assert.equal(result.status, 2);
  assert.doesNotMatch(result.stdout, /PLATFORM_CASE_OK/);
});

async function verifyFixture(t, entries, { options = [], execute, failEvidence = false } = {}) {
  const directory = mkdtempSync(join(tmpdir(), 'opengym-verifier-fixture-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const calls = [], steps = [], output = [], errors = [];
  const process = { argv: ['node', 'platform.mjs', 'verify', 'harness', ...options], env: {} };
  const source = readFileSync('scripts/platform.mjs', 'utf8')
    .replace(/^import .*\r?\n/gm, '')
    .replaceAll('import.meta.url', JSON.stringify(new URL('./platform.mjs', import.meta.url).href));
  await runInNewContext(`(async () => {${source}\n})()`, {
    process, URL, fileURLToPath, join, assert,
    readFileSync: () => JSON.stringify({ harness: entries }),
    mkdtempSync: failEvidence ? () => { throw new Error('unwritable evidence'); } : mkdtempSync,
    writeFileSync, tmpdir: () => directory,
    console: { log: value => output.push(value), error: value => errors.push(value) },
    syntheticHarness: () => ({
      execute: async (_program, args) => { calls.push(Array.from(args)); return execute ? execute(args) : '# tests 1\n# pass 1\n'; },
      runProject: async work => work(async args => { steps.push(Array.from(args)); }, 'fixture'),
    }),
  });
  return { directory, calls, steps, output, errors, status: process.exitCode ?? 0 };
}

test('identical host proofs run once per invocation without changing case selection', async t => {
  const entries = [
    { id: 'one', target: 'host', command: ['proof.mjs'] },
    { id: 'two', target: 'host', command: ['proof.mjs'] },
    { id: 'other', target: 'host', command: ['other.mjs'] },
  ];
  for (let attempt = 0; attempt < 2; attempt++) {
    const result = await verifyFixture(t, entries);
    assert.equal(result.status, 0);
    assert.deepEqual(result.calls, [['proof.mjs'], ['other.mjs']]);
    assert.deepEqual(result.output.map(value => JSON.parse(value).case), ['one', 'two', 'other']);
  }
  const selected = await verifyFixture(t, entries, { options: ['--case', 'two'] });
  assert.deepEqual(selected.calls, [['proof.mjs']]);
  assert.deepEqual(selected.output.map(value => JSON.parse(value).case), ['two']);
});

test('host proof failures retain bounded diagnostics and never credit aliases', async t => {
  const entries = ['one', 'two'].map(id => ({ id, target: 'host', command: ['proof.mjs'] }));
  for (const proof of ['', '# tests 1\n# skipped 1\n', new Error('child failed')]) {
    if (proof instanceof Error) Object.assign(proof, {
      stdout: 'proof-stdout', stderr: 'proof-stderr', code: 7, signal: null,
    });
    const result = await verifyFixture(t, entries, { execute: () => {
      if (proof instanceof Error) throw proof;
      return proof;
    } });
    assert.equal(result.status, 1);
    assert.equal(result.calls.length, 1);
    assert.equal(result.output.length, 0);
    const evidence = join(result.directory, readdirSync(result.directory)[0]);
    assert.equal(readFileSync(join(evidence, 'stdout.log'), 'utf8'), proof.stdout ?? proof);
    assert.equal(readFileSync(join(evidence, 'stderr.log'), 'utf8'), proof.stderr ?? '');
    assert.deepEqual(JSON.parse(readFileSync(join(evidence, 'result.json'))), {
      suite: 'harness', case: 'one', code: proof.code ?? null, signal: null,
      overflow: false, aborted: false,
    });
  }
  const result = await verifyFixture(t, entries, {
    execute: () => { throw new Error('original failure'); }, failEvidence: true,
  });
  assert.equal(result.status, 1);
  assert.equal(result.output.length, 0);
  assert.deepEqual(result.errors, ['PLATFORM_FAILURE_LOG_UNAVAILABLE', 'original failure']);
});

test('Python batches use one pytest process with all declared paths in order', async t => {
  const result = await verifyFixture(t, [
    { id: 'one', target: 'platform-test', command: ['tests/one.py'] },
    { id: 'two', target: 'platform-test', command: ['tests/two.py', 'tests/three.py'] },
  ]);
  assert.equal(result.status, 0);
  assert.deepEqual(result.steps, [
    ['config', '--quiet'], ['build', 'platform-test'],
    ['up', '--detach', '--wait', '--wait-timeout', '60', 'platform-db'],
    ['run', '--rm', '--no-deps', 'platform-test', 'tests/one.py', 'tests/two.py', 'tests/three.py'],
  ]);
  assert.equal(result.output.length, 2);
});

test('empty output, skipped proofs and failed commands never receive a passing case marker', t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-platform-proof-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'scripts'));
  mkdirSync(join(root, 'backend'));
  for (const file of ['platform.mjs', 'synthetic-harness.mjs']) {
    cpSync(join('scripts', file), join(root, 'scripts', file));
  }
  writeFileSync(join(root, 'required.test.mjs'), "import test from 'node:test'; test('required proof', { skip: true }, () => {});\n");
  for (const command of [['-e', ''], ['--test', 'required.test.mjs'], ['-e', 'process.exitCode = 1']]) {
    writeFileSync(join(root, 'backend/platform-suites.json'), JSON.stringify({
      harness: [{ id: 'ownership', target: 'host', command }],
    }));
    const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'verify', 'harness'], {
      cwd: root, encoding: 'utf8', timeout: 10_000,
      env: { ...process.env, TMPDIR: root, TEMP: root, TMP: root },
    });
    assert.equal(result.status, 1);
    assert.doesNotMatch(result.stdout, /PLATFORM_CASE_OK/);
  }
});
