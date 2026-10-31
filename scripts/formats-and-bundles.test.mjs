import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { stripVTControlCharacters } from 'node:util';
import test from 'node:test';
import { checkCopy, checkMobileBundle } from '../frontend/scripts/check-mobile-bundle.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const frontend = join(root, 'frontend');
const files = directory => readdirSync(directory, { withFileTypes: true }).flatMap(entry =>
  entry.isDirectory() ? files(join(directory, entry.name)) : [join(directory, entry.name)]);

function run(args, cwd = root, extraEnv = {}) {
  const env = { ...process.env, NODE_ENV: 'test', FORCE_COLOR: '0', ...extraEnv };
  delete env.NODE_TEST_CONTEXT;
  const result = spawnSync(process.execPath, args, {
    cwd, env, encoding: 'utf8', timeout: 240_000, maxBuffer: 8 * 1024 * 1024,
  });
  assert.ifError(result.error);
  const output = stripVTControlCharacters(result.stdout + result.stderr);
  assert.equal(result.status, 0, output);
  assert.doesNotMatch(output, /(?:# (?:skipped|todo|cancelled) [1-9]|[1-9]\d* skipped)/);
  console.log(output);
  return output;
}

test('CSV/JSON/media backup/FIT and catalogue retain existing independent and hostile cases', () => {
  const selected = [
    ...['import-csv', 'import-csv.hostile', 'import-csv.strong', 'import-csv.twice',
      'import-hevy', 'import-hevy.hostile', 'import-reimport', 'import-match',
      'import-name-bodypart', 'import-effort', 'import-bodyweight', 'backup-media',
      'zip', 'fit-export', 'catalogue-continuity', 'catalogue-browse'].map(name => `src/lib/${name}.test.js`),
    ...['import-check', 'import-restore', 'media-backup'].map(name => `src/store/useStore.${name}.test.jsx`),
    'scripts/check-mobile-bundle.test.mjs',
  ];
  for (const path of selected) assert.ok(existsSync(join(frontend, path)), `Required format test missing: ${path}`);
  const output = run(['node_modules/vitest/vitest.mjs', 'run', '--configLoader', 'runner', '--maxWorkers=1', ...selected], frontend);
  assert.match(output, /Tests\s+[1-9]\d* passed/);
  run(['--test', 'scripts/catalogue/build.test.mjs']);
  run(['scripts/catalogue/build.mjs', '--check']);
  run(['scripts/catalogue/check-media.mjs']);
});

test('web and mobile bundles resolve shared JS without the Node API and copy intact to both shells', t => {
  const workspace = mkdtempSync(join(tmpdir(), 'opengym-formats-'));
  t.after(() => rmSync(workspace, { recursive: true, force: true }));
  const client = join(workspace, 'frontend');
  for (const entry of ['src', 'scripts', 'public', 'index.html', 'package.json', 'vite.config.js', 'capacitor.config.json', 'android', 'ios']) {
    cpSync(join(frontend, entry), join(client, entry), { recursive: true });
  }
  cpSync(join(root, 'shared'), join(workspace, 'shared'), { recursive: true });
  symlinkSync(join(frontend, 'node_modules'), join(client, 'node_modules'), 'junction');
  const vite = join(frontend, 'node_modules/vite/bin/vite.js');
  const env = { VITE_API_PREFIX: '/api/v1', VITE_MOBILE: '', VITE_UMAMI_SRC: '', VITE_UMAMI_ID: '', APP_MEDIA_DIR: '', VITE_CLIP_EXT: '' };

  for (const [flavor, prefix] of [['web-node', '/api'], ['web-python', '/api/v1'], ['mobile', '/api/v1']]) {
    const out = join(client, flavor === 'mobile' ? 'dist' : flavor);
    run([vite, 'build', '--configLoader', 'runner', '--outDir', out, '--sourcemap', 'hidden', '--manifest'], client,
      { ...env, VITE_API_PREFIX: prefix, VITE_MOBILE: flavor === 'mobile' ? '1' : '' });
    const html = readFileSync(join(out, 'index.html'), 'utf8');
    assert.equal(html.includes('opengym-flavor'), flavor === 'mobile');
    assert.equal(readFileSync(join(out, 'sw.js'), 'utf8').includes('__BUILD__'), false);
    assert.deepEqual(checkCopy(out).filter(problem => !problem.includes('not the mobile build')), []);
    const maps = files(join(out, 'assets')).filter(path => path.endsWith('.map')).map(path => JSON.parse(readFileSync(path, 'utf8')));
    const sources = maps.flatMap(map => map.sources);
    assert.ok(sources.some(source => source.includes('shared/coach-core/')), `${flavor}: shared source absent`);
    assert.ok(!sources.some(source => /(?:^|\/)api\//.test(source)), `${flavor}: Node API source bundled`);
    const apiMap = maps.find(map => map.sources.some(source => source.endsWith('/lib/api.js')));
    assert.ok(apiMap, `${flavor}: API client absent`);
    const code = readFileSync(join(out, 'assets', apiMap.file), 'utf8');
    assert.ok(['"', "'", '`'].some(quote => code.includes('replace(/^\\/api(?=\\/|$)/,' + quote + prefix + quote)), `${flavor}: wrong compiled API prefix`);
    const manifest = JSON.parse(readFileSync(join(out, '.vite/manifest.json'), 'utf8'));
    assert.ok(Object.keys(manifest).length > 0);
    for (const entry of Object.values(manifest)) {
      assert.ok(existsSync(join(out, entry.file)));
      for (const css of entry.css || []) assert.ok(existsSync(join(out, css)));
    }
  }

  run(['scripts/catalogue/stage-media.mjs', join(client, 'dist')], root, env);
  // Copy is the portable Capacitor boundary; native plugin/Gradle/CocoaPods compilation is not claimed.
  run([join(frontend, 'node_modules/@capacitor/cli/bin/capacitor'), 'copy', 'android'], client, env);
  run([join(frontend, 'node_modules/@capacitor/cli/bin/capacitor'), 'copy', 'ios'], client, env);
  assert.deepEqual(checkMobileBundle(client), []);
  const copies = ['android/app/src/main/assets/public', 'ios/App/App/public'];
  for (const file of files(join(client, 'dist'))) {
    const relative = file.slice(join(client, 'dist').length + 1);
    for (const copy of copies) {
      assert.deepEqual(readFileSync(join(client, copy, relative)), readFileSync(file), `${copy}: ${relative}`);
    }
  }
  for (const dir of ['still', 'clip']) {
    const source = join(root, 'catalogue/media', dir);
    assert.ok(files(source).length > 0);
    for (const file of files(source)) {
      assert.deepEqual(readFileSync(join(client, 'dist/exercise-media', dir, file.slice(source.length + 1))), readFileSync(file));
    }
  }
});
