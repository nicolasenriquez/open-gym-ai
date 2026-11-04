// Explicit frozen-file producer, not a second business API or default test discovery.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { captureStoppedNode } from './platform-node-capture.mjs';

test('produce independent frozen legacy files and an unrepresentable source for isolated import', async () => {
  const root = '/app/node-capture-fixtures';
  const data = join(root, 'source'), configuration = join(root, 'configuration');
  const protectedAccess = join(root, 'protected-access'), client = join(root, 'client-export');
  for (const path of [data, configuration, protectedAccess, client]) mkdirSync(path, { mode: 0o700 });
  writeFileSync(join(data, 'secret'), 'c'.repeat(64), { mode: 0o600 });
  writeFileSync(join(configuration, 'release.json'), '{"revision":"synthetic-frozen-source"}');
  writeFileSync(join(protectedAccess, 'token'), 'SYNTHETIC_DEFERRED_TOKEN');
  writeFileSync(join(client, 'pending.json'), '{"synthetic":true,"active":{"id":"local-active"},"dirty":true}');
  const image = Buffer.from([0xff, 0xd8, 0xff, 0xe0]), hash = createHash('sha256').update(image).digest('hex');
  const users = [['A', 'Capture Alice'], ['B', 'Capture Bob']].map(([id, name]) =>
    ({ id, name, workout: 'captured-' + id, rev: 1 }));
  const password = '$scrypt$v=1$ln=15,r=8,p=1$aW5kZXBlbmRlbnQtc2FsdA==$Bjd+MjiP3fgJgtBQ7YtA+FZz32RnxkRW4AqlBrzwRIM=';
  writeFileSync(join(data, 'db.json'), JSON.stringify({ users: users.map(({ id, name }) =>
    ({ id, name, pw: { h: password, set: 1_800_000_000_000 } })), creds: [], subs: [], invites: [] }));
  for (const user of users) {
    const state = { _rev: user.rev, _wid: 'write-' + user.workout, unit: 'kg', routines: [],
      workouts: [{ id: user.workout, d: '2026-11-03', entries: [] }],
      customEx: user.id === 'A' ? [{ id: 'custom-image', n: 'Synthetic', custom: true,
        media: { hash, kind: 'image', mime: 'image/jpeg', size: image.length, width: 1, height: 1, at: 1 } }] : [] };
    writeFileSync(join(data, 'state-' + user.id + '.json'), JSON.stringify(state));
  }
  mkdirSync(join(data, 'uploads/A'), { recursive: true, mode: 0o700 });
  writeFileSync(join(data, 'uploads/A', hash + '.jpg'), image);
  const sourceCutoffAt = new Date().toISOString();
  const receipt = await captureStoppedNode({ sources: [{ name: 'data', path: data }, { name: 'configuration', path: configuration },
    { name: 'protected-access', path: protectedAccess }, { name: 'client-export', path: client }],
    destination: join(root, 'capture'), sourceCutoffAt, writersStopped: () => true });
  assert.equal(receipt.importAuthorized, false);
  const invalid = join(root, 'invalid-source'); cpSync(data, invalid, { recursive: true, errorOnExist: true, force: false });
  writeFileSync(join(invalid, 'db.json'), '{"users":[],"users":[]}');
  await captureStoppedNode({ sources: [{ name: 'data', path: invalid }, { name: 'configuration', path: configuration }],
    destination: join(root, 'invalid-capture'), sourceCutoffAt, writersStopped: () => true });
  writeFileSync(join(root, 'expected.json'), JSON.stringify({ users, hash, mediaHex: image.toString('hex'), sourceCutoffAt }), { mode: 0o600 });
});
