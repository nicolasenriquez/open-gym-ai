import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import { EventEmitter } from 'node:events';
import { syncBuiltinESMExports } from 'node:module';
import test from 'node:test';
import { syntheticHarness } from './synthetic-harness.mjs';

const harness = () => syntheticHarness({ root: process.cwd(), name: 'Test' });

test('captured success returns stdout only, even with stderr warnings', async () => {
  const output = await harness().execute(process.execPath, ['-e',
    'console.log(JSON.stringify({ok:true})); console.error("warning")']);
  assert.deepEqual(JSON.parse(output), { ok: true });
});

test('failed children retain separate stdout, stderr and exit status', async () => {
  await assert.rejects(harness().execute(process.execPath, ['-e',
    'console.log("proof-stdout"); console.error("proof-stderr"); process.exitCode=7']), error => {
    assert.match(error.stdout, /proof-stdout/);
    assert.match(error.stderr, /proof-stderr/);
    assert.equal(error.code, 7);
    assert.equal(error.signal, null);
    assert.equal(error.overflow, false);
    return true;
  });
});

test('missing executables and deadlines reject with their causes after close', async () => {
  await assert.rejects(harness().execute('opengym-missing-executable', []), error => {
    assert.equal(error.cause.code, 'ENOENT');
    assert.equal(error.stdout, '');
    assert.equal(error.stderr, '');
    return true;
  });
  await assert.rejects(harness().execute(process.execPath,
    ['-e', 'setInterval(()=>{},1000)'], false, 100), error => {
    assert.equal(error.aborted, true);
    assert.equal(error.cause.name, 'AbortError');
    return true;
  });
});

test('the aggregate capture limit bounds both diagnostic streams', async () => {
  await assert.rejects(harness().execute(process.execPath, ['-e',
    'process.stdout.write("prefix"); process.stderr.write("x".repeat(5*1024*1024))']), error => {
    assert.equal(error.overflow, true);
    assert.ok(Buffer.byteLength(error.stdout) + Buffer.byteLength(error.stderr) <= 4 * 1024 * 1024);
    return true;
  });
});

test('live output streams once and phase timings include failed steps and cleanup', async t => {
  const stdout = [], stderr = [], records = [];
  t.mock.method(process.stdout, 'write', data => { stdout.push(String(data)); return true; });
  t.mock.method(process.stderr, 'write', data => { stderr.push(String(data)); return true; });
  t.mock.method(console, 'log', value => { records.push(value); });
  t.mock.method(childProcess, 'spawn', (_program, args) => {
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    queueMicrotask(() => {
      const compose = args[0] === 'compose';
      const failed = compose && args.includes('run');
      if (compose) {
        child.stdout.emit('data', Buffer.from('live-out'));
        child.stderr.emit('data', Buffer.from('live-err'));
      }
      child.emit('close', failed ? 9 : 0, null);
    });
    return child;
  });
  syncBuiltinESMExports();
  try {
    const owner = syntheticHarness({ root: process.cwd(), name: 'Test', namespace: 'test' });
    await assert.rejects(owner.runProject(async step => {
      await step(['config', '--quiet']);
      await step(['run', 'proof']);
    }), /Docker compose failed/);
    assert.deepEqual(stdout, ['live-out', 'live-out']);
    assert.deepEqual(stderr, ['live-err', 'live-err']);
    const timings = records.filter(value => value.startsWith('{')).map(JSON.parse);
    assert.deepEqual(timings.map(value => value.phase), ['config', 'run', 'cleanup']);
    for (const value of timings) {
      assert.equal(value.code, 'SYNTHETIC_STEP_TIMING');
      assert.ok(value.duration_ms >= 0);
      assert.match(value.project, /^test-[a-f0-9]{16}$/);
      assert.deepEqual(Object.keys(value).sort(), ['code', 'duration_ms', 'phase', 'project']);
    }
  } finally {
    t.mock.restoreAll();
    syncBuiltinESMExports();
  }
});
