import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

test('catalogue check accepts CRLF output while rejecting changed content', t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-catalogue-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const dir of ['scripts/catalogue', 'catalogue/exercises', 'catalogue/i18n']) mkdirSync(join(root, dir), { recursive: true });
  for (const file of ['build.mjs', 'validate.mjs']) copyFileSync(new URL(`./${file}`, import.meta.url), join(root, 'scripts/catalogue', file));
  // This catalogue-only fixture has no API consumer to regenerate.
  writeFileSync(join(root, 'scripts/build-coach-assets.mjs'), '');
  writeFileSync(join(root, 'catalogue/exercises/0001.json'), JSON.stringify({
    id: '0001', name: 'test exercise', bodyPart: 'back', equipment: 'body weight',
    target: 'lats', description: '', secondaryMuscles: [], instructions: [], textSource: 'exercisedb',
  }));
  const run = (...args) => spawnSync(process.execPath, [join(root, 'scripts/catalogue/build.mjs'), ...args], { encoding: 'utf8', timeout: 10000 });
  const generated = run();
  assert.equal(generated.status, 0, generated.stderr);
  const file = join(root, 'catalogue/browse/README.md');
  const body = readFileSync(file, 'utf8');
  writeFileSync(file, body.replaceAll('\n', '\r\n'));
  assert.equal(run('--check').status, 0);
  writeFileSync(file, body + '\nchanged content\n');
  assert.equal(run('--check').status, 1);
});
