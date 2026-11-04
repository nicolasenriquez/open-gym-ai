// Explicit producer, not default test discovery: /app/node-capture-fixtures is an owned volume.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { boundPort } from '../api/test/helpers.mjs';
import { jpeg } from '../api/test/media-samples.mjs';
import { captureStoppedNode } from './platform-node-capture.mjs';

test('produce a stopped real Node capture and an unrepresentable frozen fixture for isolated import', async t => {
  const root = '/app/node-capture-fixtures';
  const data = join(root, 'source'), configuration = join(root, 'configuration');
  const protectedAccess = join(root, 'protected-access'), client = join(root, 'client-export');
  for (const path of [data, configuration, protectedAccess, client]) mkdirSync(path, { mode: 0o700 });
  writeFileSync(join(data, 'secret'), 'c'.repeat(64), { mode: 0o600 });
  writeFileSync(join(configuration, 'release.json'), '{"revision":"synthetic-node-source"}');
  writeFileSync(join(protectedAccess, 'token'), 'SYNTHETIC_DEFERRED_TOKEN');
  writeFileSync(join(client, 'pending.json'), '{"synthetic":true,"active":{"id":"local-active"},"dirty":true}');
  const child = spawn(process.execPath, ['api/server.js'], { cwd: '/app', windowsHide: true,
    env: { PORT: '0', DATA_DIR: data, COACH_CREDENTIAL_DIR: protectedAccess, COACH_DISABLED: '1',
      ORIGIN: 'http://localhost:8080', RP_ID: 'localhost', PASSWORD_LOGIN: '1', AUDIT_LOG: '0' },
    stdio: ['ignore', 'pipe', 'pipe'] });
  child.stderr.resume();
  const stop = async () => {
    if (child.exitCode !== null || child.signalCode !== null) return;
    const closed = once(child, 'close'); child.kill('SIGTERM'); await closed;
  };
  t.after(stop);
  const base = `http://127.0.0.1:${await boundPort(child)}`;
  const request = (method, path, body, cookie) => fetch(base + path, { method,
    headers: { Origin: 'http://localhost:8080', 'Content-Type': 'application/json', ...(cookie ? { Cookie: cookie } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(5000) });
  const image = jpeg(), hash = createHash('sha256').update(image).digest('hex');
  const users = [];
  for (const [name, workout] of [['Capture Alice', 'acknowledged-A'], ['Capture Bob', 'acknowledged-B']]) {
    const registration = await request('POST', '/api/register/password', { name, password: 'orchard bicycle summer 42!' });
    assert.equal(registration.status, 200); await registration.json();
    const cookie = registration.headers.getSetCookie().find(value => value.startsWith('gymsid=')).split(';')[0];
    const state = { unit: 'kg', routines: [], workouts: [{ id: workout, d: '2026-11-03', entries: [] }],
      customEx: name === 'Capture Alice' ? [{ id: 'custom-image', n: 'Synthetic', custom: true,
        media: { hash, kind: 'image', mime: 'image/jpeg', size: image.length, width: 1, height: 1, at: 1 } }] : [] };
    const saved = await request('PUT', '/api/data', { state, wid: `write-${workout}` }, cookie);
    assert.equal(saved.status, 200); await saved.json();
    const readback = await (await request('GET', '/api/data', undefined, cookie)).json();
    assert.equal(readback.state.workouts[0].id, workout);
    const user = JSON.parse(readFileSync(join(data, 'db.json'), 'utf8')).users.find(user => user.name === name);
    users.push({ id: user.id, name, workout, rev: readback.rev });
    if (name === 'Capture Alice') {
      const uploaded = await fetch(`${base}/api/media/${hash}`, { method: 'PUT',
        headers: { Cookie: cookie, Origin: 'http://localhost:8080', 'Content-Type': 'image/jpeg' }, body: image,
        signal: AbortSignal.timeout(5000) });
      assert.equal(uploaded.status, 201); await uploaded.json();
    }
  }
  const sourceCutoffAt = new Date().toISOString();
  await stop();
  const sources = [{ name: 'data', path: data }, { name: 'configuration', path: configuration },
    { name: 'protected-access', path: protectedAccess }, { name: 'client-export', path: client }];
  const receipt = await captureStoppedNode({ sources, destination: join(root, 'capture'), sourceCutoffAt,
    writersStopped: () => child.exitCode !== null || child.signalCode !== null });
  assert.equal(receipt.importAuthorized, false);
  // A separate corrupt legacy fixture is captured as bytes; never normalize it into valid data.
  const invalid = join(root, 'invalid-source'); cpSync(data, invalid, { recursive: true, errorOnExist: true, force: false });
  writeFileSync(join(invalid, 'db.json'), '{"users":[],"users":[]}');
  await captureStoppedNode({ sources: [{ name: 'data', path: invalid }, { name: 'configuration', path: configuration }],
    destination: join(root, 'invalid-capture'), sourceCutoffAt, writersStopped: () => true });
  writeFileSync(join(root, 'expected.json'), JSON.stringify({ users, hash, mediaHex: image.toString('hex'), sourceCutoffAt }), { mode: 0o600 });
});
