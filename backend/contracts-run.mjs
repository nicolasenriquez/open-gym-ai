import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const versions = JSON.parse(readFileSync(new URL('./versions.json', import.meta.url), 'utf8'));

async function apiSmoke() {
  const data = mkdtempSync(join(tmpdir(), 'python-foundation-api-'));
  const child = spawn(process.execPath, ['server.js'], {
    cwd: new URL('./api/', import.meta.url), stdio: ['ignore', 'pipe', 'pipe'],
    // Do not forward instance, PostgreSQL or provider settings to the ordinary API.
    env: { PORT: '0', DATA_DIR: data, RP_ID: 'localhost', ORIGIN: 'http://localhost',
      NODE_ENV: 'test', COACH_DISABLED: '1', AUDIT_LOG: '0' },
  });
  const closed = new Promise(resolve => child.once('close', resolve));
  try {
    const port = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('API_START_TIMEOUT')), 10_000);
      const failed = () => { clearTimeout(timer); reject(new Error('API_START_FAILED')); };
      child.once('error', failed);
      child.once('exit', failed);
      let output = '';
      child.stderr.resume();
      child.stdout.on('data', chunk => {
        output += chunk;
        if (output.length > 4096) { failed(); return; }
        const match = /gym-api on :(\d+)/.exec(output);
        if (match) { clearTimeout(timer); resolve(Number(match[1])); }
      });
    });
    const response = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: AbortSignal.timeout(5000) });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { ok: true, users: 0, writable: true });
    assert.ok(statSync(join(data, 'secret')).isFile());
  } finally {
    child.kill('SIGTERM');
    let forced = false;
    const timer = setTimeout(() => { forced = true; child.kill('SIGKILL'); }, 5000);
    await closed;
    clearTimeout(timer);
    rmSync(data, { recursive: true, force: true });
    assert.equal(forced, false, 'API_STOP_TIMEOUT');
  }
  console.log(JSON.stringify({ code: 'FOUNDATION_NODE_API_OK', status: 200 }));
}

if (process.argv.slice(2).length !== 1 || process.argv[2] !== 'environment') {
  console.error('FOUNDATION_CONTRACTS_NOT_IMPLEMENTED');
  process.exitCode = 1;
} else {
  try {
    assert.equal(process.versions.node, versions.node);
    await apiSmoke();
    console.log(JSON.stringify({ code: 'FOUNDATION_NODE_TARGET_OK', node: process.versions.node, contracts: 'pending' }));
  } catch {
    console.error('FOUNDATION_NODE_TARGET_FAILED');
    process.exitCode = 1;
  }
}
