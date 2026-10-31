import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import test from 'node:test';

const inventory = directory => readdirSync(directory, { withFileTypes: true }).flatMap(entry =>
  entry.isDirectory() ? inventory(join(directory, entry.name)).map(path => `${entry.name}/${path}`) : [entry.name]);

const scenarios = [
  {
    name: 'web', ignore: '.dockerignore', dockerfile: 'web/Dockerfile',
    required: ['frontend/package.json', 'frontend/pnpm-lock.yaml', 'frontend/index.html',
      'frontend/src/main.jsx', 'frontend/public/sw.js', 'frontend/scripts/sw-stamp.mjs',
      'shared/package.json', 'shared/coach-core/payload.js', 'web/nginx.conf.template', 'web/05-check-base-path.sh',
      'catalogue/media/still/1001.webp', 'catalogue/media/clip/1001.mp4'],
    excluded: ['.git/config', '.scratch/proof.json', '.playwright-cli/screen.png', 'docs/guide.md',
      'coach-auth/auth.json', 'data/users.json', '.env.production', 'dev.env', 'secrets.env.backup',
      'frontend/.env.local', 'frontend/node_modules/host.js', 'frontend/dist/old.js',
      'frontend/android/gradle.properties', 'frontend/ios/Podfile', 'backend/src/private.py'],
  },
  {
    name: 'api', ignore: 'api/Dockerfile.dockerignore', dockerfile: 'api/Dockerfile',
    required: ['api/package.json', 'api/pnpm-lock.yaml', 'api/server.js', 'api/durable.js',
      'shared/package.json', 'shared/coach-core/payload.js'],
    excluded: ['api/node_modules/host.js', 'api/test/private.test.js', '.env', '.env.local', 'dev.env',
      'api/coach/local.env', 'api/coach/.env.production', 'api/coach/node_modules/host.js', '.git/config',
      'frontend/src/main.jsx', 'data/users.json', 'shared/private.env'],
  },
  {
    name: 'python', ignore: 'backend/.dockerignore', dockerfile: 'Dockerfile',
    required: ['pyproject.toml', 'uv.lock', 'versions.json', 'dependency-licenses.json', 'pg-tool.sh',
      'src/opengym_platform/application.py', 'tests/platform/test_lifecycle.py',
      'contracts/identity-sessions.v1.json', 'contracts/identity-passwords.v1.json'],
    excluded: ['.venv/bin/python', '.env', 'dev.env', 'src/local.env',
      'src/opengym_platform/__pycache__/application.pyc', 'data/users.json'],
  },
  {
    name: 'contracts override', ignore: 'backend/Dockerfile.contracts.dockerignore', dockerfile: 'backend/Dockerfile.contracts',
    required: ['LICENSE', 'api/package.json', 'api/server.js', 'api/test/password.test.js',
      'frontend/src/lib/coach.js', 'backend/contracts-run.mjs', 'backend/contracts/identity-sessions.v1.json',
      'shared/package.json', 'shared/coach-core/payload.js', 'shared/coach-core/prompts/common.md',
      'scripts/shared-client.test.mjs', 'scripts/formats-and-bundles.test.mjs', 'scripts/build-coach-assets.mjs',
      'scripts/catalogue/stage-media.mjs', 'frontend/index.html', 'frontend/public/sw.js',
      'frontend/capacitor.config.json', 'frontend/android/app/src/main/AndroidManifest.xml',
      'frontend/ios/App/App/Info.plist', 'catalogue/i18n/es.json', 'catalogue/browse/README.md',
      'catalogue/media/still/1001.webp', 'catalogue/media/clip/1001.mp4',
      'catalogue/exercises/0001.json', 'backend/src/opengym_platform/coach/assets.json'],
    excluded: ['coach-auth/auth.json', '.env.local', 'api/coach/private.env', 'data/users.json',
      'frontend/node_modules/host.js', 'frontend/src/private.env',
      'frontend/android/local.properties', 'frontend/android/key.properties', 'frontend/android/release.jks',
      'frontend/android/app/build/private.apk', 'frontend/android/.gradle/cache',
      'frontend/android/app/src/main/assets/public/old.js', 'frontend/ios/App/App/public/old.js',
      'frontend/ios/App/Pods/private', 'frontend/ios/App/App.xcodeproj/xcuserdata/private',
      'frontend/ios/signing.p12', 'frontend/ios/profile.mobileprovision'],
  },
  {
    name: 'browser override', ignore: 'backend/Dockerfile.browser.dockerignore', dockerfile: 'backend/Dockerfile.browser',
    required: ['frontend/index.html', 'frontend/package.json', 'frontend/pnpm-lock.yaml',
      'frontend/src/main.jsx', 'frontend/e2e/platform/training.mjs', 'frontend/e2e/platform/package-lock.json', 'shared/package.json', 'shared/coach-core/payload.js'],
    excluded: ['data/users.json', 'coach-auth/auth.json', '.env', 'frontend/src/private.env',
      'frontend/e2e/platform/node_modules/host.js', 'frontend/e2e/platform/private.env', 'api/server.js', 'backend/src/private.env'],
  },
  {
    name: 'security override', ignore: 'backend/Dockerfile.security.dockerignore', dockerfile: 'backend/Dockerfile.security',
    required: ['backend/security/pyproject.toml', 'backend/security/uv.lock', 'backend/uv.lock',
      'backend/src/opengym_platform/application.py', '.github/workflows/test.yml'],
    excluded: ['data/users.json', 'coach-auth/auth.json', 'frontend/src/main.jsx', 'backend/src/private.env'],
  },
];

for (const scenario of scenarios) test(`${scenario.name}: Docker filters private/host files and preserves required inputs`, t => {
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-build-context-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const context = join(temporary, 'context');
  const output = join(temporary, 'output');
  const write = (path, text) => {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, text);
  };
  for (const path of [...scenario.required, ...scenario.excluded]) write(join(context, path), 'synthetic fixture');
  write(join(context, '.dockerignore'), readFileSync('.dockerignore', 'utf8'));
  const ignorePath = scenario.ignore.includes('Dockerfile.') ? `${scenario.dockerfile}.dockerignore` : '.dockerignore';
  write(join(context, ignorePath), readFileSync(scenario.ignore, 'utf8'));
  const dockerfile = join(context, scenario.dockerfile);
  write(dockerfile, 'FROM scratch\nCOPY . /context/\n');
  const result = spawnSync('docker', ['build', '--network=none', '--progress=plain',
    '--file', dockerfile, '--output', `type=local,dest=${output}`, context], {
    encoding: 'utf8', timeout: 60_000, maxBuffer: 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const files = inventory(join(output, 'context'));
  for (const path of scenario.required) assert.ok(files.includes(path), `Required input excluded: ${path}`);
  for (const path of scenario.excluded) assert.ok(!files.includes(path), `Private/host input leaked: ${path}`);
});

test('Git ignores local credentials/envs while preserving the public template and synthetic env', t => {
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-git-ignore-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  copyFileSync('.gitignore', join(temporary, '.gitignore'));
  const git = args => spawnSync('git', args, { cwd: temporary, encoding: 'utf8', timeout: 10_000 });
  assert.equal(git(['init', '--quiet']).status, 0);
  for (const path of ['coach-auth/auth.json', '.env.local', 'dev.env', '.venv/file', '__pycache__/file.pyc']) {
    assert.equal(git(['check-ignore', '--no-index', path]).status, 0, `Private/local path is not ignored: ${path}`);
  }
  for (const path of ['.env.example', '.env.production.example', 'dev.env.example', 'backend/empty.env', 'frontend/src/main.jsx']) {
    assert.equal(git(['check-ignore', '--no-index', path]).status, 1, `Source/template is unexpectedly ignored: ${path}`);
  }
});
