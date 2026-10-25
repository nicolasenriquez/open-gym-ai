import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createHmac } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { isDeepStrictEqual } from 'node:util';

const versions = JSON.parse(readFileSync(new URL('./versions.json', import.meta.url), 'utf8'));

function compare(expected, actual) {
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const response = value => object(value) && Number.isInteger(value.status)
    && value.status >= 100 && value.status <= 599 && Object.hasOwn(value, 'body');
  if (!object(expected) || !object(actual) || typeof expected.id !== 'string'
      || typeof expected.sourceRevision !== 'string' || !/^[a-z][a-z0-9.-]{0,95}$/.test(expected.id)
      || !/^[a-f0-9]{40}$/.test(expected.sourceRevision)
      || !response(expected.response) || !response(actual.response)) {
    throw new Error('FOUNDATION_CONTRACT_INPUT_INVALID');
  }
  const matches = expected.id === actual.id && isDeepStrictEqual(expected.response, actual.response);
  console.log(JSON.stringify({ code: matches ? 'FOUNDATION_CONTRACT_OK' : 'FOUNDATION_CONTRACT_MISMATCH',
    id: expected.id, sourceRevision: expected.sourceRevision }));
  return matches;
}

function readContract(path) {
  const stat = statSync(path);
  if (!stat.isFile() || stat.size > 65536) throw new Error('FOUNDATION_CONTRACT_INPUT_INVALID');
  return JSON.parse(readFileSync(path, 'utf8'));
}

async function contractSuites() {
  const manifest = readContract(new URL('./contracts/suites.v2.json', import.meta.url));
  for (const suite of manifest.suites) {
    assert.ok(['api', 'frontend'].includes(suite.cwd));
    await new Promise((resolve, reject) => {
      const child = spawn(process.execPath, suite.args, {
        cwd: new URL(`./${suite.cwd}/`, import.meta.url), timeout: 180_000,
        env: { PATH: process.env.PATH, HOME: '/tmp', TMPDIR: '/tmp', NODE_ENV: 'test',
          COACH_CREDENTIAL_DIR: '/tmp/coach-auth', FORCE_COLOR: '0' },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      let output = '';
      const collect = chunk => {
        output += chunk;
        if (output.length > 4 * 1024 * 1024) child.kill('SIGKILL');
      };
      child.stdout.on('data', collect);
      child.stderr.on('data', collect);
      child.once('error', () => reject(new Error('FOUNDATION_SUITE_START_FAILED')));
      child.once('close', code => {
        const passed = code === 0 && !/(?:# skipped [1-9]|[1-9]\d* skipped)/.test(output);
        console.log(JSON.stringify({ code: passed ? 'FOUNDATION_SUITE_OK' : 'FOUNDATION_SUITE_FAILED',
          id: suite.id, sourceRevision: manifest.sourceRevision, command: [process.execPath, ...suite.args] }));
        if (passed) resolve();
        else reject(new Error('FOUNDATION_SUITE_FAILED'));
      });
    });
  }
}

async function apiSmoke(baseline) {
  const data = mkdtempSync(join(tmpdir(), 'python-foundation-api-'));
  if (baseline) {
    writeFileSync(join(data, 'secret'), baseline.setup.secret, { mode: 0o600 });
    writeFileSync(join(data, 'db.json'), JSON.stringify({ users: baseline.setup.users, creds: [], subs: [], invites: [] }));
    for (const [uid, state] of Object.entries(baseline.setup.states)) {
      assert.match(uid, /^[a-z0-9_]+$/);
      writeFileSync(join(data, `state-${uid}.json`), JSON.stringify(state));
    }
  }
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
    if (baseline) {
      for (const entry of baseline.cases) {
        const { owner, path, ...request } = entry.request;
        assert.match(path, /^\/api\/[a-z/-]+$/);
        const headers = { ...request.headers };
        if (owner) {
          assert.ok(baseline.setup.users.some(user => user.id === owner));
          const payload = `${owner}:4102444800000:0`;
          headers.cookie = `gymsid=${payload}.${createHmac('sha256', baseline.setup.secret).update(payload).digest('base64url')}`;
        }
        const response = await fetch(`http://127.0.0.1:${port}${path}`, {
          ...request, headers, redirect: 'error', signal: AbortSignal.timeout(5000),
        });
        const observed = { status: response.status, body: await response.json() };
        if (entry.response.headers) observed.headers = Object.fromEntries(
          Object.keys(entry.response.headers).map(key => [key, response.headers.get(key)]));
        assert.ok(compare({ ...entry, sourceRevision: baseline.sourceRevision }, { id: entry.id, response: observed }), 'CONTRACT_MISMATCH');
      }
    } else {
      const response = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: AbortSignal.timeout(5000) });
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), { ok: true, users: 0, writable: true });
    }
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

if (process.argv[2] === 'compare' && process.argv.length === 5) {
  try {
    if (!compare(readContract(process.argv[3]), readContract(process.argv[4]))) process.exitCode = 1;
  } catch {
    console.error('FOUNDATION_CONTRACT_INPUT_INVALID');
    process.exitCode = 1;
  }
} else if (process.argv.slice(2).length !== 1 || !['environment', 'baseline', 'contracts'].includes(process.argv[2])) {
  console.error('FOUNDATION_CONTRACTS_NOT_IMPLEMENTED');
  process.exitCode = 1;
} else {
  try {
    assert.equal(process.versions.node, versions.node);
    await apiSmoke(process.argv[2] === 'environment' ? undefined : readContract(new URL('./contracts/http-baseline.v1.json', import.meta.url)));
    if (process.argv[2] === 'contracts') await contractSuites();
    console.log(JSON.stringify({ code: 'FOUNDATION_NODE_TARGET_OK', node: process.versions.node, group: process.argv[2] }));
  } catch {
    console.error('FOUNDATION_NODE_TARGET_FAILED');
    process.exitCode = 1;
  }
}
