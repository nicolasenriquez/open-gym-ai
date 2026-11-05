import assert from 'node:assert/strict';
import fs from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { closeSync, mkdtempSync, mkdirSync, openSync, writeFileSync, readFileSync, readdirSync, lstatSync, existsSync, rmSync, symlinkSync, linkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';
import { captureStoppedNode } from './platform-node-capture.mjs';
import { drainAndCaptureNode } from './platform-node-drain.mjs';

const stopped = child => child.exitCode !== null || child.signalCode !== null;
async function stop(child) {
  if (stopped(child)) return;
  const closed = once(child, 'close');
  child.kill('SIGTERM');
  await closed;
}

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'opengym-node-capture-'));
  const sources = ['data', 'configuration', 'protected-access', 'client-export'].map(name => {
    const path = join(root, name); mkdirSync(path, { mode: 0o700 }); return { name, path };
  });
  const children = [];
  t.after(async () => {
    for (const child of children) await stop(child);
    assert.equal(resolve(root).startsWith(resolve(tmpdir()) + '\\') || resolve(root).startsWith(resolve(tmpdir()) + '/'), true);
    rmSync(root, { recursive: true, force: true });
  });
  writeFileSync(join(root, 'data/secret'), 'c'.repeat(64), { mode: 0o600 });
  writeFileSync(join(root, 'data/db.json'), '{"users":[],"creds":[],"subs":[],"invites":[]}');
  writeFileSync(join(root, 'configuration/release.json'), '{"revision":"synthetic-source","image":"synthetic-node-image"}');
  writeFileSync(join(root, 'configuration/writer.txt'), 'before');
  writeFileSync(join(root, 'protected-access/deferred-token'), 'SYNTHETIC_PRIVATE_TOKEN');
  writeFileSync(join(root, 'client-export/pending.json'), JSON.stringify({
    synthetic: true, active: { id: 'local-active-1' }, dirty: true, pendingWriteId: 'local-pending-1',
  }));
  const own = child => { children.push(child); return child; };
  return { root, sources, own, destination: join(root, 'capture'), sourceCutoffAt: new Date().toISOString(),
    async api() {
      // Protocol fixture only: capture tooling verifies the proof, not retired business logic.
      const child = own(spawn(process.execPath, ['-e', `
        process.on('message', message => {
          process.send('drain-started');
          process.stdout.write('NODE_DRAINED ' + JSON.stringify({version:1,pid:process.pid,finishedAt:message.finishedAt}) + '\\n', () => process.exit(0));
        });
        process.send('ready');
      `], { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe', 'ipc'] }));
      let output = '';
      child.stdout.on('data', d => { output += d; });
      child.stderr.resume();
      await once(child, 'message');
      return { child, output: () => output };
    },
    async writer(file = join(root, 'configuration/writer.txt')) {
      const child = own(spawn(process.execPath, ['-e',
        "const fs=require('node:fs');process.on('message',v=>{fs.writeFileSync(process.argv[1],v);process.send('written')});process.send('ready')", file],
        { windowsHide: true, env: { SystemRoot: process.env.SystemRoot ?? '' }, stdio: ['ignore', 'ignore', 'ignore', 'ipc'] }));
      await once(child, 'message');
      return child;
    },
  };
}

function processControl(f, api) {
  const identity = { id: 'a'.repeat(64), image: `sha256:${'b'.repeat(64)}`,
    project: 'synthetic', startedAt: new Date().toISOString() };
  return { identity,
    async inspect() { return { ...identity, dataRoot: join(f.root, 'data'), running: !stopped(api.child),
      pid: stopped(api.child) ? 0 : api.child.pid, exitCode: api.child.exitCode }; },
    async signal() { const started = once(api.child, 'message'); api.child.send({ finishedAt: new Date().toISOString() }); await started; },
    async proof() {
      if (!api.child.stdout.readableEnded) await once(api.child.stdout, 'end');
      return JSON.parse(api.output().split(/\r?\n/).find(s => s.startsWith('NODE_DRAINED ')).slice(13));
    },
    async noOtherContainers() { return true; },
  };
}

test('Node drain adapter checks identities and external writers before stopping and capturing', { timeout: 15_000 }, async t => {
  const f = fixture(t), api = await f.api(), writer = await f.writer();
  const control = processControl(f, api);
  const options = { ...f, api: control.identity, externalWritersStopped: () => stopped(writer) };
  await assert.rejects(drainAndCaptureNode(options, control), /NODE_DRAIN_CAPTURE_REJECTED/);
  assert.equal(stopped(api.child), false);
  await stop(writer);
  await assert.rejects(drainAndCaptureNode({ ...options, api: { ...control.identity, image: `sha256:${'c'.repeat(64)}` } }, control), /NODE_DRAIN_CAPTURE_REJECTED/);
  await assert.rejects(drainAndCaptureNode({ ...options, destination: f.root }, control), /NODE_DRAIN_CAPTURE_REJECTED/);
  assert.equal(stopped(api.child), false, 'invalid preflight must not stop the source');
  const result = await drainAndCaptureNode(options, control);
  assert.equal(stopped(api.child), true);
  assert.equal(api.child.exitCode, 0);
  assert.equal(result.receipt.sourceCutoffAt, result.drain.finishedAt);
  assert.equal(result.cutoverAuthorized, false);
  assert.equal(result.realGateCompleted, false);
  assert.equal(readFileSync(join(f.destination, 'data/secret'), 'utf8'), 'c'.repeat(64));
});

test('Frozen-source capture preserves documents, media, secrets and configuration after all writers stop', async t => {
  const f = fixture(t), api = await f.api(), writer = await f.writer();
  const foreign = await f.writer(join(f.root, 'foreign.txt'));
  const bytes = Buffer.from([0xff, 0xd8, 0xff, 0xe0]), hash = createHash('sha256').update(bytes).digest('hex');
  const user = 'A';
  const state = { _rev: 7, _wid: 'frozen-write', workouts: [{ id: 'acknowledged-1' }],
    customEx: [{ id: 'custom-1', media: { hash } }] };
  writeFileSync(join(f.root, 'data/db.json'), JSON.stringify({ users: [{ id: user, name: 'Capture User' }] }));
  writeFileSync(join(f.root, 'data/state-A.json'), JSON.stringify(state));
  mkdirSync(join(f.root, 'data/uploads/A'), { recursive: true });
  writeFileSync(join(f.root, `data/uploads/A/${hash}.jpg`), bytes);
  const writersStopped = () => stopped(api.child) && stopped(writer);
  await assert.rejects(captureStoppedNode({ ...f, writersStopped }), /NODE_CAPTURE_REJECTED/);
  assert.equal(existsSync(f.destination), false);
  await stop(api.child);
  await assert.rejects(captureStoppedNode({ ...f, writersStopped }), /NODE_CAPTURE_REJECTED/);
  assert.equal(existsSync(f.destination), false, 'stopping only HTTP does not stop the other writer');
  await stop(writer);
  const receipt = await captureStoppedNode({ ...f, writersStopped });
  assert.equal(receipt.operationalAcceptance, false);
  assert.equal(receipt.importAuthorized, false);
  const capturedState = JSON.parse(readFileSync(join(f.destination, `data/state-${user}.json`), 'utf8'));
  assert.equal(capturedState.workouts[0].id, 'acknowledged-1');
  assert.equal(capturedState.customEx[0].media.hash, hash);
  assert.equal(capturedState.active, undefined, 'client-local active work is separate from the frozen source');
  const capturedClient = JSON.parse(readFileSync(join(f.destination, 'client-export/pending.json'), 'utf8'));
  assert.equal(capturedClient.active.id, 'local-active-1');
  assert.equal(capturedClient.dirty, true);
  assert.equal(capturedClient.pendingWriteId, 'local-pending-1');
  assert.deepEqual(readFileSync(join(f.destination, `data/uploads/${user}/${hash}.jpg`)), bytes);
  assert.equal(readFileSync(join(f.destination, 'data/secret'), 'utf8'), 'c'.repeat(64));
  assert.equal(readFileSync(join(f.destination, 'protected-access/deferred-token'), 'utf8'), 'SYNTHETIC_PRIVATE_TOKEN');
  for (const file of receipt.files) {
    assert.equal(createHash('sha256').update(readFileSync(join(f.destination, file.path))).digest('hex'), file.sha256);
    if (process.platform !== 'win32') assert.equal(lstatSync(join(f.destination, file.path)).mode & 0o777, 0o600);
  }
  if (process.platform !== 'win32') {
    for (const name of ['', ...receipt.directories]) assert.equal(lstatSync(join(f.destination, name)).mode & 0o777, 0o700);
  }
  assert.equal(stopped(foreign), false, 'unrelated process is never stopped');
  assert.deepEqual(JSON.parse(readFileSync(join(f.root, 'data/state-A.json'), 'utf8')), state);
  assert.deepEqual(readFileSync(join(f.destination, 'capture.json'), 'utf8'), JSON.stringify(receipt));
  await assert.rejects(captureStoppedNode({ ...f, writersStopped: () => true }), /NODE_CAPTURE_REJECTED/);
});

test('Node capture validates descriptor link counts before and after inventory reads', async t => {
  const f = fixture(t), stat = fs.fstatSync;
  for (const phase of ['before', 'after']) {
    let stats = 0;
    t.mock.method(fs, 'fstatSync', (...args) => {
      const info = stat(...args);
      if (++stats === (phase === 'before' ? 1 : 2)) return Object.assign(Object.create(info), { nlink: 2n });
      return info;
    });
    syncBuiltinESMExports();
    try {
      await assert.rejects(captureStoppedNode({ ...f, writersStopped: () => true }), /NODE_CAPTURE_REJECTED/);
      assert.equal(existsSync(f.destination), false);
    } finally {
      t.mock.restoreAll();
      syncBuiltinESMExports();
    }
  }
});

test('Node capture rejects a changed source and keeps its partial copy without a success receipt', async t => {
  const f = fixture(t), writer = await f.writer();
  let changed = false;
  const writersStopped = async () => {
    if (!changed && existsSync(join(f.destination, 'data/db.json'))) {
      changed = true;
      const written = once(writer, 'message'); writer.send('changed-after-copy'); await written;
    }
    return true; // An external writer violates custody despite the reported stop proof.
  };
  await assert.rejects(captureStoppedNode({ ...f, writersStopped }), /NODE_CAPTURE_REJECTED/);
  assert.equal(changed, true);
  assert.equal(existsSync(f.destination), true);
  assert.equal(existsSync(join(f.destination, 'capture.json')), false);
  assert.equal(readFileSync(join(f.root, 'configuration/writer.txt'), 'utf8'), 'changed-after-copy');
});

test('Node capture never follows links or reuses overlapping or occupied destinations', async t => {
  const f = fixture(t), writersStopped = () => true;
  for (const destination of [join(f.root, 'data/nested'), f.root]) {
    await assert.rejects(captureStoppedNode({ ...f, destination, writersStopped }), /NODE_CAPTURE_REJECTED/);
  }
  const outside = join(f.root, 'outside'); mkdirSync(outside);
  writeFileSync(join(outside, 'private'), 'SYNTHETIC_FOREIGN');
  symlinkSync(outside, join(f.root, 'data/linked'), process.platform === 'win32' ? 'junction' : 'dir');
  await assert.rejects(captureStoppedNode({ ...f, writersStopped }), /NODE_CAPTURE_REJECTED/);
  assert.equal(existsSync(f.destination), false);
  rmSync(join(f.root, 'data/linked'));
  linkSync(join(outside, 'private'), join(f.root, 'data/hardlink'));
  await assert.rejects(captureStoppedNode({ ...f, writersStopped }), /NODE_CAPTURE_REJECTED/);
  assert.equal(existsSync(f.destination), false);
  assert.equal(readFileSync(join(outside, 'private'), 'utf8'), 'SYNTHETIC_FOREIGN');
});

test('Node capture leaves an interrupted copy quarantined and never restarts a writer', async t => {
  const f = fixture(t);
  let checks = 0;
  await assert.rejects(captureStoppedNode({ ...f, writersStopped: () => ++checks < 3 }), /NODE_CAPTURE_REJECTED/);
  assert.equal(existsSync(f.destination), true);
  assert.equal(existsSync(join(f.destination, 'capture.json')), false);
  const before = readdirSync(f.destination);
  await assert.rejects(captureStoppedNode({ ...f, writersStopped: () => true }), /NODE_CAPTURE_REJECTED/);
  assert.deepEqual(readdirSync(f.destination), before);
  assert.equal(readFileSync(join(f.root, 'data/db.json'), 'utf8'), '{"users":[],"creds":[],"subs":[],"invites":[]}');
});

test('Node capture rejects destination corruption and missing required recovery material', async t => {
  const f = fixture(t);
  let corrupted = false;
  await assert.rejects(captureStoppedNode({ ...f, writersStopped: () => {
    const target = join(f.destination, 'data/db.json');
    if (!corrupted) {
      let fd;
      try {
        fd = openSync(target, 'r+');
        writeFileSync(fd, 'corrupt-copy');
        corrupted = true;
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      } finally {
        if (fd !== undefined) closeSync(fd);
      }
    }
    return true;
  } }), /NODE_CAPTURE_REJECTED/);
  assert.equal(corrupted, true);
  assert.equal(existsSync(join(f.destination, 'capture.json')), false);
  const missing = fixture(t);
  rmSync(join(missing.root, 'data/secret'));
  await assert.rejects(captureStoppedNode({ ...missing, writersStopped: () => true }), /NODE_CAPTURE_REJECTED/);
  assert.equal(existsSync(missing.destination), false);
});

test('copying an older frozen Node source never rejuvenates its declared data cutoff', async t => {
  const f = fixture(t), sourceCutoffAt = '2020-01-02T03:04:05.000Z';
  const receipt = await captureStoppedNode({ ...f, sourceCutoffAt, writersStopped: () => true });
  assert.equal(receipt.sourceCutoffAt, sourceCutoffAt);
  assert.equal(receipt.importAuthorized, false);
});

test('a killed Node capture controller leaves the source stopped and its partial destination unreusable', { timeout: 30_000 }, async t => {
  const f = fixture(t), api = await f.api();
  await stop(api.child);
  const code = `
    const {captureStoppedNode} = await import(${JSON.stringify(pathToFileURL(resolve('scripts/platform-node-capture.mjs')).href)});
    const fs = await import('node:fs');
    await captureStoppedNode({sources:${JSON.stringify(f.sources)},destination:${JSON.stringify(f.destination)},sourceCutoffAt:${JSON.stringify(f.sourceCutoffAt)},
      writersStopped:async()=>{if(fs.existsSync(${JSON.stringify(join(f.destination, 'data/db.json'))})){process.send('partial');await new Promise(()=>{});}return true;}});
  `;
  const controller = f.own(spawn(process.execPath, ['--input-type=module', '-e', code], {
    windowsHide: true, env: { SystemRoot: process.env.SystemRoot ?? '' }, stdio: ['ignore', 'ignore', 'ignore', 'ipc'],
  }));
  assert.deepEqual(await once(controller, 'message'), ['partial', undefined]);
  const closed = once(controller, 'close');
  controller.kill('SIGKILL'); await closed;
  assert.equal(stopped(api.child), true);
  assert.equal(existsSync(f.destination), true);
  assert.equal(existsSync(join(f.destination, 'data/db.json')), true);
  assert.equal(existsSync(join(f.destination, 'capture.json')), false);
  await assert.rejects(captureStoppedNode({ ...f, writersStopped: () => true }), /NODE_CAPTURE_REJECTED/);
  // Explicit recovery uses only the source; a failed copy is never promoted or resumed.
  const recovered = await f.api();
  assert.equal(stopped(recovered.child), false);
});
