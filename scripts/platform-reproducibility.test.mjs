import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { syntheticHarness } from './synthetic-harness.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
// Child test runners must report their own results instead of inheriting this runner.
delete process.env.NODE_TEST_CONTEXT;

test('clean checkout: delivered targets, cold cache matrix and HTTP database recovery', async () => {
  const parent = join(root, '.scratch', 'platform-reproducibility');
  mkdirSync(parent, { recursive: true });
  const evidence = mkdtempSync(join(parent, 'run-'));
  const checkout = join(evidence, 'checkout');
  console.log(`PLATFORM_REPRODUCIBILITY_EVIDENCE ${evidence}`);
  async function run(command, args, cwd, name) {
    const { execute } = syntheticHarness({ root: cwd, name: 'Reproducibility' });
    const output = await execute(command, args, false, 1_200_000);
    writeFileSync(join(evidence, name + '.log'), output);
    return output;
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
