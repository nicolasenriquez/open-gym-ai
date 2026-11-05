import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { join, sep } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../', import.meta.url));
// Child test runners must report their own results instead of inheriting this runner.
delete process.env.NODE_TEST_CONTEXT;

function runLogged(command, args, cwd, log) {
  const result = spawnSync(command, args, { cwd, encoding: 'utf8', timeout: 1_200_000, maxBuffer: 8 * 1024 * 1024,
    env: { ...Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith('COMPOSE_'))),
      COMPOSE_DISABLE_ENV_FILE: 'true' } });
  writeFileSync(log, (result.stdout ?? '') + (result.stderr ?? ''));
  assert.ifError(result.error);
  assert.equal(result.status, 0, `Proof failed; inspect ${log}`);
  return result.stdout;
}

test('failed child proof retains stdout and stderr in its owned temporary log', () => {
  const directory = mkdtempSync(join(tmpdir(), 'opengym-proof-log-'));
  try {
    const log = join(directory, 'failed.log');
    assert.throws(() => runLogged(process.execPath,
      ['-e', 'console.log("proof-stdout"); console.error("proof-stderr"); process.exit(7)'], root, log), /Proof failed/);
    const output = readFileSync(log, 'utf8');
    assert.match(output, /proof-stdout/);
    assert.match(output, /proof-stderr/);
  } finally {
    assert.ok(realpathSync(directory).startsWith(realpathSync(tmpdir()) + sep));
    rmSync(directory, { recursive: true });
  }
});

test('clean checkout: delivered targets, cold cache matrix and HTTP database recovery', async () => {
  const evidence = mkdtempSync(join(tmpdir(), 'opengym-reproducibility-'));
  const checkout = join(evidence, 'checkout');
  console.log(`PLATFORM_REPRODUCIBILITY_EVIDENCE ${evidence}`);
  async function run(command, args, cwd, name) {
    return runLogged(command, args, cwd, join(evidence, name + '.log'));
  }
  const revision = (await run('git', ['rev-parse', 'HEAD'], root, 'revision')).trim();
  await run('git', ['worktree', 'add', '--detach', checkout, revision], root, 'checkout');
  try {
    assert.equal((await run('git', ['status', '--porcelain'], checkout, 'clean')).trim(), '');
    writeFileSync(join(evidence, 'context.json'), JSON.stringify({ revision, platform: 'linux/amd64',
      versions: JSON.parse(readFileSync(join(checkout, 'backend/versions.json'))),
      scope: 'clean HEAD runtime and existing probes; uncommitted documentation/runner changes excluded' }, null, 2));
    for (const [name, args] of [
      ['targets', ['--test', '--test-reporter=tap', 'scripts/platform-images.test.mjs']],
      ['cache', ['--test', '--test-reporter=tap', 'scripts/platform-build.test.mjs']],
      ['lifecycle', ['scripts/platform.mjs', 'verify', 'lifecycle']],
    ]) {
      const output = await run(process.execPath, args, checkout, name);
      if (name === 'lifecycle') assert.match(output, /PLATFORM_CASE_OK/);
      else {
        assert.match(output, /\btests [1-9]\d*/);
        assert.doesNotMatch(output, /\b(?:skipped|todo|cancelled) [1-9]\d*/);
      }
      console.log(`PLATFORM_REPRODUCIBILITY_OK ${name}`);
    }
    assert.equal((await run('git', ['status', '--porcelain'], checkout, 'clean-after')).trim(), '');
  } finally {
    assert.ok(realpathSync(checkout).startsWith(realpathSync(evidence)));
    await run('git', ['worktree', 'remove', checkout], root, 'cleanup');
  }
});
