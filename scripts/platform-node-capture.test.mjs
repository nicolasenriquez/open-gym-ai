import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash, createHmac } from 'node:crypto';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync, lstatSync, existsSync, rmSync, symlinkSync, linkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import http from 'node:http';
import test from 'node:test';
import { boundPort, sampleState } from '../api/test/helpers.mjs';
import { jpeg } from '../api/test/media-samples.mjs';
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
    async api(data = join(root, 'data'), env = {}) {
      const child = own(spawn(process.execPath, ['--input-type=module', '-e',
        "process.on('message',()=>{process.send('drain-started');if(!process.emit('SIGTERM'))process.exit(143)});await import('./api/server.js')"], { cwd: resolve('.'),
        env: { SystemRoot: process.env.SystemRoot ?? '', PORT: '0', DATA_DIR: data,
          ORIGIN: 'http://localhost:8080', RP_ID: 'localhost', PASSWORD_LOGIN: '1',
          COACH_DISABLED: '1', COACH_CREDENTIAL_DIR: join(root, 'protected-access'), AUDIT_LOG: '1', ...env },
        windowsHide: true, stdio: ['ignore', 'pipe', 'pipe', 'ipc'] }));
      child.stderr.resume();
      let output = '';
      child.stdout.on('data', d => { output += d; });
      const base = `http://127.0.0.1:${await boundPort(child)}`;
      return { child, base, output: () => output, async request(method, path, body, cookie) {
        return fetch(base + path, { method, headers: { 'Content-Type': 'application/json',
          Origin: 'http://localhost:8080', ...(cookie ? { Cookie: cookie } : {}) },
          body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(5000) });
      } };
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
    async signal() { const started = once(api.child, 'message'); api.child.send('drain'); await started; },
    async proof() { return JSON.parse(api.output().split(/\r?\n/).find(s => s.startsWith('NODE_DRAINED ')).slice(13)); },
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

test('Node drain waits for an accepted detached Coach job and captures its completed result', { timeout: 15_000 }, async t => {
  const f = fixture(t);
  let answer;
  const reached = new Promise(resolveReached => { answer = resolveReached; });
  const provider = http.createServer((req, res) => { req.resume(); req.on('end', () => answer(res)); });
  await new Promise(r => provider.listen(0, '127.0.0.1', r));
  t.after(() => { provider.close(); provider.closeAllConnections(); });
  writeFileSync(join(f.root, 'data/coach.json'), JSON.stringify({ enabled: true, provider: 'compatible',
    providerOptions: { compatible: { baseUrl: `http://127.0.0.1:${provider.address().port}` } }, models: { compatible: 'local-model' } }));
  writeFileSync(join(f.root, 'data/db.json'), JSON.stringify({ users: [{ id: 'drain-coach', name: 'Coach User' }], creds: [], subs: [], invites: [] }));
  writeFileSync(join(f.root, 'data/state-drain-coach.json'), JSON.stringify(sampleState()));
  const api = await f.api(undefined, { COACH_DISABLED: '0' }), control = processControl(f, api);
  const payload = `drain-coach:${Date.now() + 60_000}:0`;
  const cookie = `gymsid=${payload}.${createHmac('sha256', 'c'.repeat(64)).update(payload).digest('base64url')}`;
  const queued = await api.request('POST', '/api/coach/review', {}, cookie);
  assert.equal(queued.status, 202); await queued.json();
  const res = await reached;
  const started = once(api.child, 'message');
  const captured = drainAndCaptureNode({ ...f, api: control.identity, externalWritersStopped: () => true }, control);
  await started;
  assert.equal(stopped(api.child), false);
  assert.equal(existsSync(f.destination), false);
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify({ choices: [{ finish_reason: 'stop', message: { content: '{"coach_contract":1,"nochange":true,"reading":"Steady."}' } }] }));
  await captured;
  const record = JSON.parse(readFileSync(join(f.destination, 'data/coach/drain-coach.json'), 'utf8'));
  assert.equal(record.current, null);
  assert.equal(record.history.at(-1).outcome, 'nochange');
});

test('Node drain timeout cannot publish a successful capture or restart the source', { timeout: 15_000 }, async t => {
  const f = fixture(t), api = await f.api(undefined, { NODE_DRAIN_TIMEOUT_MS: '50' });
  const req = http.request(`${api.base}/api/register/password`, { method: 'POST', headers: { 'Content-Length': 100 } });
  req.on('error', () => {}); req.write('{');
  t.after(() => req.destroy());
  await api.request('GET', '/api/config');
  const control = processControl(f, api);
  await assert.rejects(drainAndCaptureNode({ ...f, api: control.identity, externalWritersStopped: () => true }, control), /NODE_DRAIN_CAPTURE_REJECTED/);
  assert.equal(api.child.exitCode, 1);
  assert.doesNotMatch(api.output(), /NODE_DRAINED/);
  assert.equal(existsSync(f.destination), false);
});

test('Node drain finishes an admitted write before exiting and stops accepting new requests', { timeout: 15_000 }, async t => {
  const f = fixture(t), api = await f.api();
  const body = JSON.stringify({ name: 'Drained User', password: 'orchard bicycle summer 42!' });
  const result = new Promise((resolveResponse, reject) => {
    const req = http.request(`${api.base}/api/register/password`, { method: 'POST',
      headers: { Origin: 'http://localhost:8080', 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } }, res => {
      res.resume(); res.on('end', () => resolveResponse(res.statusCode));
    });
    req.on('error', reject);
    req.write(body.slice(0, -1));
    api.pendingRequest = req;
  });
  result.catch(() => {});
  await api.request('GET', '/api/config');
  const started = once(api.child, 'message');
  const closed = once(api.child, 'close');
  api.child.send('drain'); await started;
  assert.equal(stopped(api.child), false, 'accepted request must not be abandoned');
  api.pendingRequest.end(body.slice(-1));
  assert.equal(await result, 200);
  const [code, signal] = await closed;
  assert.equal(code, 0); assert.equal(signal, null);
  assert.equal(JSON.parse(readFileSync(join(f.root, 'data/db.json'), 'utf8')).users[0].name, 'Drained User');
  await assert.rejects(fetch(`${api.base}/api/config`));
});

test('Node capture preserves acknowledged HTTP state, media, secrets and configuration after all writers stop', async t => {
  const f = fixture(t), api = await f.api(), writer = await f.writer();
  const foreign = await f.writer(join(f.root, 'foreign.txt'));
  const registered = await api.request('POST', '/api/register/password', { name: 'Capture User', password: 'orchard bicycle summer 42!' });
  assert.equal(registered.status, 200);
  await registered.json();
  const cookie = registered.headers.getSetCookie().find(value => value.startsWith('gymsid=')).split(';')[0];
  const bytes = jpeg(), hash = createHash('sha256').update(bytes).digest('hex');
  const state = { unit: 'kg', routines: [], workouts: [{ id: 'acknowledged-1', d: '2026-11-03', entries: [] }],
    customEx: [{ id: 'custom-1', n: 'Synthetic image', custom: true,
      media: { hash, kind: 'image', mime: 'image/jpeg', size: bytes.length, width: 1, height: 1, at: 1 } }],
    active: { id: 'active-1' } };
  const saved = await api.request('PUT', '/api/data', { state }, cookie);
  assert.equal(saved.status, 200);
  await saved.json();
  const expected = await (await api.request('GET', '/api/data', undefined, cookie)).json();
  assert.equal(expected.state.workouts[0].id, 'acknowledged-1');
  assert.equal(expected.state.customEx[0].media.hash, hash);
  const user = JSON.parse(readFileSync(join(f.root, 'data/db.json'), 'utf8')).users[0].id;
  const uploaded = await fetch(`${api.base}/api/media/${hash}`, { method: 'PUT',
    headers: { Cookie: cookie, Origin: 'http://localhost:8080', 'Content-Type': 'image/jpeg' }, body: bytes });
  assert.equal(uploaded.status, 201); await uploaded.json();
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
  assert.equal(expected.state.active, undefined, 'Node state is not a backup of client-local active work');
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
  // Recover the source only; never start services on the captured copy.
  const resumed = await f.api();
  assert.deepEqual(await (await resumed.request('GET', '/api/data', undefined, cookie)).json(), expected);
  assert.deepEqual(readFileSync(join(f.destination, 'capture.json'), 'utf8'), JSON.stringify(receipt));
  await assert.rejects(captureStoppedNode({ ...f, writersStopped: () => true }), /NODE_CAPTURE_REJECTED/);
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
    if (!corrupted && existsSync(target)) { writeFileSync(target, 'corrupt-copy'); corrupted = true; }
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
  assert.equal((await recovered.request('GET', '/api/config')).status, 200);
});
