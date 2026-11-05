import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import yaml from 'js-yaml';

const workflow = yaml.load(readFileSync('.github/workflows/test.yml', 'utf8'));
const manifest = JSON.parse(readFileSync('backend/platform-suites.json', 'utf8'));
const jobs = workflow.jobs;
const asList = value => (Array.isArray(value) ? value : [value]);

test('CI retains only supported workflows', () => {
  const check = files => assert.deepEqual(
    files.filter(file => /\.ya?ml$/.test(file)).sort(), ['test.yml'],
    'Retire inherited workflows from the merged tree before adding a new workflow',
  );
  check(readdirSync('.github/workflows'));
  for (const file of ['cla.yml', 'cla-issue.yml', 'unexpected.yaml']) {
    assert.throws(() => check(['test.yml', file]), assert.AssertionError);
  }
});

test('CI assigns every declared platform case', () => {
  const covered = new Set();
  for (const job of Object.values(jobs)) {
    for (const step of job.steps ?? []) {
      for (const match of (step.run ?? '').matchAll(
        /^node scripts\/platform\.mjs verify (\w+)(?: --case (\w+))?$/gm,
      )) {
        const [, suite, selectedCase] = match;
        assert.ok(Object.hasOwn(manifest, suite), `Unknown suite: ${suite}`);
        const selected = manifest[suite].filter(
          entry => !selectedCase || entry.id === selectedCase,
        );
        assert.ok(selected.length, `Unknown case: ${suite}/${selectedCase}`);
        for (const entry of selected) covered.add(`${suite}/${entry.id}`);
      }
    }
  }

  for (const entry of manifest.checks ?? []) {
    const command = `uv run --locked pytest -q ${entry.command.join(' ')}`;
    assert.ok(
      (jobs['python-checks']?.steps ?? []).some(step => step.run === command),
      `Missing Python check: ${entry.id}`,
    );
    covered.add(`checks/${entry.id}`);
  }

  if (covered.has('images/reproducibility')) covered.add('images/isolation');

  const missing = Object.entries(manifest).flatMap(([suite, cases]) =>
    cases
      .map(entry => `${suite}/${entry.id}`)
      .filter(key => !covered.has(key)),
  );
  assert.deepEqual(missing, []);
});

test('CI gate requires every blocking job', () => {
  assert.match(String(jobs.ci.if), /always\(\)/);
  const aggregated = new Set(['platform-suites', 'ci']);
  const expected = Object.keys(jobs)
    .filter(name => !aggregated.has(name))
    .sort();
  assert.deepEqual(asList(jobs.ci.needs).sort(), expected);
  assert.deepEqual(asList(jobs.platform.needs), ['platform-suites']);
  assert.match(String(jobs.platform.if), /needs\.platform-suites\.result != 'skipped'/);

  for (const [name, job] of Object.entries(jobs)) {
    assert.equal(job['continue-on-error'], undefined, name);
    for (const step of job.steps ?? []) {
      assert.equal(step['continue-on-error'], undefined, name);
    }
  }
});

test('documentation classifier runs platform for empty, mixed and unknown paths', () => {
  const classify = jobs.changes.steps.find(step => step.id === 'classify').run;
  const source = classify.match(/node --input-type=module -e '([\s\S]*?)'/)?.[1];
  assert.ok(source);
  for (const [files, expected] of [
    [['README.md', 'docs/guide.md', 'docs/reference/api.md'], false],
    [['CONTRIBUTING.md', 'CHANGELOG.md'], false],
    [[], true],
    [['docs/guide.md', 'scripts/ci.test.mjs'], true],
    [['.github/workflows/test.yml'], true],
    [['docs/example.py'], true],
    [['unknown.md'], true],
    [['docs/name\nwith newline.md'], true],
  ]) {
    const result = spawnSync(process.execPath, ['--input-type=module', '-e', source], {
      input: files.join('\0'), encoding: 'utf8',
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), `platform=${expected}`, JSON.stringify(files));
  }
  assert.match(classify, /if \[ "\$EVENT" != pull_request \]; then\s+echo "platform=true"/);
});

test('CI gate rejects failures, cancellations and unexpected skips', () => {
  const source = jobs.ci.steps[0].run.match(/<<'JS'\n([\s\S]*?)\nJS/)?.[1];
  assert.ok(source);
  const baseline = Object.fromEntries(asList(jobs.ci.needs).map(name => [
    name, { result: 'success', ...(name === 'changes' ? { outputs: { platform: 'true' } } : {}) },
  ]));
  const run = needs => spawnSync(process.execPath, ['--input-type=module', '-e', source], {
    env: { ...process.env, NEEDS: JSON.stringify(needs) }, encoding: 'utf8',
  }).status;
  assert.equal(run(baseline), 0);
  const docs = structuredClone(baseline);
  docs.changes.outputs.platform = 'false';
  docs.platform.result = 'skipped';
  assert.equal(run(docs), 0);
  for (const name of Object.keys(baseline)) {
    for (const result of ['failure', 'cancelled', 'skipped']) {
      const needs = structuredClone(baseline);
      needs[name].result = result;
      assert.notEqual(run(needs), 0, `${name}: ${result}`);
    }
  }
  for (const output of ['', 'unknown']) {
    docs.changes.outputs.platform = output;
    assert.notEqual(run(docs), 0);
  }
});

test('platform matrix conditions reference declared groups', () => {
  const platform = jobs['platform-suites'];
  const groups = new Set(platform.strategy.matrix.include.map(entry => entry.group));
  for (const step of platform.steps) {
    for (const match of String(step.if ?? '').matchAll(/matrix\.group == '([^']+)'/g)) {
      assert.ok(groups.has(match[1]), `Unknown matrix group: ${match[1]}`);
    }
  }

  const identityAccount = platform.steps.find(
    step => step.run === 'node scripts/platform.mjs verify identity_account',
  );
  assert.equal(identityAccount?.if, "matrix.group == 'identity-account'");
});
