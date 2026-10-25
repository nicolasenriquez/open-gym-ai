import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const probe = fileURLToPath(new URL('./assert-no-ai-executables.mjs', import.meta.url));

test('an installed but unloadable Agent SDK cannot pass as absent', t => {
  const directory = mkdtempSync(join(tmpdir(), 'opengym-ci-sdk-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const fixture = join(directory, 'probe.mjs');
  copyFileSync(probe, fixture);
  const dependency = join(directory, 'node_modules/@anthropic-ai/claude-agent-sdk');
  mkdirSync(dependency, { recursive: true });
  writeFileSync(join(dependency, 'package.json'), JSON.stringify({ name: '@anthropic-ai/claude-agent-sdk', exports: './missing.js' }));
  const result = spawnSync(process.execPath, [fixture], { encoding: 'utf8', env: { ...process.env, PATH: directory } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /CI_UNEXPECTED_AI_PACKAGE/);
});

test('an AI executable present in PATH fails even when the other is absent', t => {
  const directory = mkdtempSync(join(tmpdir(), 'opengym-ci-path-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  writeFileSync(join(directory, 'codex'), 'fixture; never executed');
  const result = spawnSync(process.execPath, [probe], {
    encoding: 'utf8', env: { ...process.env, PATH: directory },
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /CI_UNEXPECTED_AI_EXECUTABLE:codex/);
});

test('no AI executables passes and missing PATH fails explicitly', t => {
  const directory = mkdtempSync(join(tmpdir(), 'opengym-ci-empty-path-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  for (const [path, status] of [[directory, 0], ['', 1]]) {
    const result = spawnSync(process.execPath, [probe], {
      encoding: 'utf8', env: { ...process.env, PATH: path },
    });
    assert.ifError(result.error);
    assert.equal(result.status, status);
    if (status) assert.match(result.stderr, /CI_PATH_UNAVAILABLE/);
  }
});

test('bubblewrap alone also fails', t => {
  const directory = mkdtempSync(join(tmpdir(), 'opengym-ci-bwrap-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  writeFileSync(join(directory, 'bwrap'), 'fixture; never executed');
  const result = spawnSync(process.execPath, [probe], {
    encoding: 'utf8', env: { ...process.env, PATH: directory },
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /CI_UNEXPECTED_AI_EXECUTABLE:bwrap/);
});
