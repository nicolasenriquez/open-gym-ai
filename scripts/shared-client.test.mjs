import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { stripVTControlCharacters } from 'node:util';
import test from 'node:test';

const root = new URL('../', import.meta.url);
const core = new URL('shared/coach-core/', root);
const files = directory => readdirSync(directory, { withFileTypes: true }).flatMap(entry =>
  entry.isDirectory() ? files(new URL(entry.name + '/', directory)) : [new URL(entry.name, directory)]);

function run(args, cwd = root) {
  const env = { ...process.env, NODE_ENV: 'test', FORCE_COLOR: '0' };
  delete env.NODE_TEST_CONTEXT;
  const result = spawnSync(process.execPath, args, {
    cwd: fileURLToPath(cwd), encoding: 'utf8', timeout: 180_000, maxBuffer: 8 * 1024 * 1024,
    env,
  });
  assert.ifError(result.error);
  const output = stripVTControlCharacters(result.stdout + result.stderr);
  assert.equal(result.status, 0, output);
  assert.doesNotMatch(output, /(?:# (?:skipped|todo|cancelled) [1-9]|[1-9]\d* skipped)/);
  return output;
}

test('one canonical ES module tree loads without Node, Vite or backend dependencies', async () => {
  assert.equal(existsSync(new URL('api/coach/core/', root)), false);
  assert.equal(existsSync(new URL('api/coach/prompts/', root)), false);
  assert.equal(JSON.parse(readFileSync(new URL('shared/package.json', root))).type, 'module');
  const modules = files(core).filter(file => file.pathname.endsWith('.js'));
  assert.ok(modules.length >= 20);
  for (const file of modules) {
    const source = readFileSync(file, 'utf8');
    for (const [, specifier] of source.matchAll(/(?:from\s*|import\s*\()['"]([^'"]+)['"]/g)) {
      assert.ok(specifier.startsWith('./') || specifier.startsWith('../'), specifier);
      assert.ok(new URL(specifier, file).href.startsWith(core.href), specifier);
    }
    await import(file);
  }
});

test('generated JS and Python assets match the canonical catalogue and prompts', () => {
  run(['scripts/build-coach-assets.mjs', '--check']);
  run(['scripts/build-coach-library.mjs', '--check']);
  run(['api/scripts/check-core-loadable.mjs']);
});

test('shared payload, prompts, HTTP pipeline and validators preserve existing cases', () => {
  const output = run(['--test', '--test-reporter=tap', ...[
    'adapters-http', 'payload', 'payload-bounds', 'payload-parity', 'parse', 'validate',
    'prompts', 'prompt-split', 'review-repair', 'refine-change-list',
  ].map(name => 'api/test/' + name + '.test.js')]);
  assert.match(output, /# tests [1-9]\d*/);
  console.log(output.match(/# tests \d+/)[0]);
});

test('the local phone coach and client parity use the same shared source', () => {
  const output = run(['node_modules/vitest/vitest.mjs', 'run', '--configLoader', 'runner', '--maxWorkers=1',
    'src/lib/coach-local.test.js', 'src/lib/coach-parity.test.js', 'src/lib/coach.test.js',
    'src/lib/coach-demo.test.js', 'src/lib/coach-secrets.test.js',
    'src/views/CoachSetup.test.jsx', 'src/views/CoachSetup.flow.test.jsx', 'src/views/CoachIntake.test.jsx',
  ], new URL('frontend/', root));
  assert.match(output, /Tests\s+[1-9]\d* passed/);
  console.log(output.match(/Tests\s+\d+ passed/)[0]);
});
