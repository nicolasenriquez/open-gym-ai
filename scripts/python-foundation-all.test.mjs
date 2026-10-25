import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

// Separate from the harness that `all` invokes: no recursive positive run.
test('all proves every independent group, checks and Docker negatives before success', () => {
  const started = performance.now();
  const result = spawnSync(process.execPath, ['scripts/python-foundation.mjs', 'run', 'all'], {
    cwd: fileURLToPath(new URL('../', import.meta.url)),
    encoding: 'utf8', timeout: 900_000, maxBuffer: 8 * 1024 * 1024,
  });
  const evidence = mkdtempSync(join(tmpdir(), 'opengym-foundation-all-evidence-'));
  writeFileSync(join(evidence, 'all.log'), (result.stdout ?? '') + (result.stderr ?? ''));
  writeFileSync(join(evidence, 'result.json'), JSON.stringify({ status: result.status, signal: result.signal,
    seconds: (performance.now() - started) / 1000, hostNode: process.versions.node }, null, 2));
  console.log(JSON.stringify({ code: 'FOUNDATION_ALL_EVIDENCE', evidence }));
  assert.ifError(result.error);
  assert.equal(result.status, 0, 'run all directly for bounded diagnostics');
  assert.match(result.stdout, /"code":"FOUNDATION_NODE_TARGET_OK"[^\n]*"group":"contracts"/);
  for (const group of ['ENVIRONMENT', 'POOL', 'MIGRATIONS', 'ISOLATION', 'RECOVERY', 'CHECKS', 'DOCKER_REGRESSIONS', 'ALL']) {
    assert.ok(result.stdout.includes(`FOUNDATION_${group}_OK`), `missing ${group} proof`);
  }
  const projects = [...result.stdout.matchAll(/Python Foundation project: (opengym-python-foundation-test-[a-f0-9]{16})/g)].map(match => match[1]);
  assert.equal(projects.length, 7);
  assert.equal(new Set(projects).size, 7, 'groups must not inherit previous fixtures or ACLs');
  assert.equal(result.stdout.match(/Python Foundation cleanup complete/g)?.length, 7);
  assert.doesNotMatch(result.stdout, /\b[1-9]\d* skipped\b|\bskipped [1-9]\d*/);
});
