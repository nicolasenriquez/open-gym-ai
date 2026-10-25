import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { readdirSync } from 'node:fs';

const name = `opengym-ci-${randomBytes(6).toString('hex')}`;
const containers = [];
let networkCreated = false;
let failed = false;
function docker(...args) {
  const result = spawnSync('docker', args, { encoding: 'utf8', timeout: 45000, maxBuffer: 1024 * 1024 });
  if (result.error || result.status !== 0) throw new Error(result.error?.message || result.stderr.trim() || `docker ${args[0]} failed`);
  return result.stdout.trim();
}
try {
  docker('info', '--format', '{{.OSType}}');
  docker('network', 'create', '--internal', name);
  networkCreated = true;
  for (const [role, image, env] of [
    ['api', 'opengym-api:default', ['DATA_DIR=/data', 'COACH_DISABLED=1']],
    ['web', 'opengym-web:ci', ['BACKEND=api']],
  ]) {
    const container = `${name}-${role}`;
    docker('create', '--name', container, '--network', name, '--network-alias', role,
      '--label', `org.opengym.ci=${name}`, ...(role === 'api' ? ['--tmpfs', '/data:rw,nosuid,noexec,size=16m'] : []),
      ...env.flatMap(value => ['--env', value]), image);
    containers.push(container);
    docker('start', container);
  }
  const still = readdirSync(new URL('../../catalogue/media/still/', import.meta.url)).find(file => /\.(webp|png|jpg)$/.test(file));
  if (!still) throw new Error('No catalogue still available');
  const probe = `
    import assert from 'node:assert/strict';
    const deadline = Date.now() + 30000;
    let last;
    while (Date.now() < deadline) {
      try {
        const get = path => fetch('http://web' + path, {signal: AbortSignal.timeout(3000)});
        const html = await get('/');
        assert.equal(html.status, 200);
        assert.match(html.headers.get('content-type'), /text\\/html/);
        const script = (await html.text()).match(/src="([^" ]+\\.js)"/);
        assert.ok(script, 'built JavaScript missing');
        const js = await get(script[1]);
        assert.equal(js.status, 200);
        assert.match(js.headers.get('content-type'), /javascript/);
        const config = await get('/api/config');
        assert.equal(config.status, 200);
        assert.equal(typeof (await config.json()).invite_only, 'boolean');
        const media = await get(${JSON.stringify(`/exercise-media/still/${still}`)});
        assert.equal(media.status, 200);
        assert.match(media.headers.get('content-type'), /^image\\//);
        process.exit(0);
      } catch (error) { last = error.message; await new Promise(resolve => setTimeout(resolve, 500)); }
    }
    throw new Error(last);
  `;
  docker('exec', `${name}-api`, 'node', '--input-type=module', '-e', probe);
} catch (error) {
  failed = true;
  console.error(`CI_SMOKE_FAILED: ${error.message}`);
  for (const container of containers) {
    const logs = spawnSync('docker', ['logs', '--tail', '60', container], { encoding: 'utf8', timeout: 10000, maxBuffer: 32768 });
    console.error(`${container}:\n${logs.stdout ?? ''}${logs.stderr ?? ''}`);
  }
} finally {
  for (const container of containers.reverse()) {
    try { docker('rm', '--force', '--volumes', container); }
    catch (error) { failed = true; console.error(`CI_SMOKE_FAILED cleanup: ${error.message}`); }
  }
  if (networkCreated) {
    try { docker('network', 'rm', name); }
    catch (error) { failed = true; console.error(`CI_SMOKE_FAILED cleanup: ${error.message}`); }
  }
}
if (failed) process.exitCode = 1;
else console.log('CI_SMOKE_OK: packaged web, JavaScript, catalogue media and API proxy');
