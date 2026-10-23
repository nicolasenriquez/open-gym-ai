import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

test('http.health.v1: comparator rejects a changed status with exit 1', t => {
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-contract-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const actual = join(temporary, 'actual.json');
  writeFileSync(actual, JSON.stringify({
    id: 'http.health.v1',
    response: { status: 503, body: { ok: true, users: 0, writable: true } },
  }));
  const result = spawnSync(process.execPath, [
    fileURLToPath(new URL('./contracts-run.mjs', import.meta.url)), 'compare',
    fileURLToPath(new URL('./contracts/http-health.v1.json', import.meta.url)), actual,
  ], { encoding: 'utf8', timeout: 5000 });
  assert.ifError(result.error);
  assert.equal(result.signal, null, 'comparator must finish normally');
  assert.equal(result.status, 1,
    `changed HTTP status must fail comparison; stdout=${result.stdout}; stderr=${result.stderr}`);
});

test('comparator rejects two invalid envelopes without echoing untrusted content', t => {
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-contract-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const input = join(temporary, 'input.json');
  writeFileSync(input, JSON.stringify({ id: 'PRIVATE_PAYLOAD_MARKER' }));
  const result = spawnSync(process.execPath, [
    fileURLToPath(new URL('./contracts-run.mjs', import.meta.url)), 'compare', input, input,
  ], { encoding: 'utf8', timeout: 5000 });
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE_PAYLOAD_MARKER/);
});

const semantic = {
  id: 'comparator.semantics.v1', sourceRevision: '1b2daff9199611604783faabf76cd741123cec95',
  response: { status: 200, body: { owner: 'A', count: 2, nullable: null, stamp: [100, 'device-a'] },
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store',
      'set-cookie': 'gymsid=synthetic; Secure; HttpOnly; SameSite=Lax' } },
};
for (const [name, change, exit] of [
  ['identical response', () => {}, 0],
  ['payload type', v => { v.response.body.count = '2'; }, 1],
  ['missing versus null', v => { delete v.response.body.nullable; }, 1],
  ['ownership', v => { v.response.body.owner = 'B'; }, 1],
  ['semantic header', v => { v.response.headers['cache-control'] = 'public'; }, 1],
  ['cookie security', v => { v.response.headers['set-cookie'] = 'gymsid=synthetic'; }, 1],
  ['Training stamp', v => { v.response.body.stamp = [99, 'device-a']; }, 1],
  ['wrong case', v => { v.id = 'another.case'; }, 1],
]) {
  test(`comparator: ${name}`, t => {
    const temporary = mkdtempSync(join(tmpdir(), 'opengym-contract-'));
    t.after(() => rmSync(temporary, { recursive: true, force: true }));
    const expected = join(temporary, 'expected.json');
    const actual = join(temporary, 'actual.json');
    writeFileSync(expected, JSON.stringify(semantic));
    const observed = structuredClone(semantic);
    change(observed);
    writeFileSync(actual, JSON.stringify(observed));
    const result = spawnSync(process.execPath, [
      fileURLToPath(new URL('./contracts-run.mjs', import.meta.url)), 'compare', expected, actual,
    ], { encoding: 'utf8', timeout: 5000 });
    assert.ifError(result.error);
    assert.equal(result.status, exit);
    assert.deepEqual(JSON.parse(result.stdout), {
      code: exit ? 'FOUNDATION_CONTRACT_MISMATCH' : 'FOUNDATION_CONTRACT_OK',
      id: semantic.id, sourceRevision: semantic.sourceRevision,
    });
    assert.doesNotMatch(result.stdout + result.stderr, /gymsid|device-a/);
  });
}
