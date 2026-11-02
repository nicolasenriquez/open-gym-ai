import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { syntheticHarness } from './synthetic-harness.mjs';

test('targets and real dev/ops Compose isolate credentials, networks and dependencies', async () => {
  const token = randomBytes(8).toString('hex');
  const project = `opengym-platform-test-${token}`;
  const { execute, docker, cleanup } = syntheticHarness({
    root: fileURLToPath(new URL('../', import.meta.url)), namespace: 'opengym-platform-test',
    label: 'org.opengym.platform', name: 'Platform',
    services: ['platform-runtime', 'platform-test', 'platform-migrate', 'platform-ops', 'platform-dev', 'platform-diagnostics', 'platform-web'],
    images: ['platform-runtime', 'platform-test', 'platform-migrate', 'platform-ops', 'platform-dev', 'platform-diagnostics', 'platform-web'], database: 'platform-db',
  });
  const image = `${project}-platform-runtime:local`;
  try {
    await execute('docker', ['build', '--platform', 'linux/amd64', '--target', 'runtime',
      '--label', `com.docker.compose.project=${project}`, '--label', 'com.docker.compose.service=platform-runtime',
      '--label', 'org.opengym.platform=synthetic', '-t', image, '-f', 'backend/Dockerfile', 'backend'], true);
    await docker(['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
      '--security-opt', 'no-new-privileges', image, '-c', `
import importlib.util, os, pathlib, shutil
assert os.getuid() == 1000
for executable in ('node', 'npm', 'uv', 'pip', 'claude', 'codex', 'bwrap', 'pg_dump', 'age', 'age-keygen'):
    assert shutil.which(executable) is None, executable
for module in ('pytest', 'ruff', 'mypy', 'pip'):
    assert importlib.util.find_spec(module) is None, module
assert not pathlib.Path('/app/tests').exists()
assert importlib.util.find_spec('opengym_platform.importer') is None
assert importlib.util.find_spec('opengym_platform.backup') is None
assert importlib.util.find_spec('opengym_platform.bundle') is None
assert not pathlib.Path('/app/src/opengym_platform/runner.py').exists()
import fastapi, asyncpg, uvicorn, httpx
assert httpx.__version__ == '0.28.1'
from opengym_platform.coach.payload import ASSETS
assert ASSETS['library'] and ASSETS['prompts']['common']
print('PLATFORM_RUNTIME_ISOLATION_OK')
`], true);
    const testImage = `${project}-platform-test:local`;
    await docker(['build', '--platform', 'linux/amd64', '--target', 'test',
      '--label', `com.docker.compose.project=${project}`, '--label', 'com.docker.compose.service=platform-test',
      '--label', 'org.opengym.platform=synthetic', '-t', testImage, '-f', 'backend/Dockerfile', 'backend'], true);
    await docker(['run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp',
      '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', testImage, 'tests/platform/test_file_secrets.py'], true);
    for (const target of ['migrate', 'ops', 'dev']) {
      await docker(['build', '--platform', 'linux/amd64', '--target', target,
        '--label', `com.docker.compose.project=${project}`, '--label', `com.docker.compose.service=platform-${target}`,
        '--label', 'org.opengym.platform=synthetic', '-t', `${project}-platform-${target}:local`,
        '-f', 'backend/Dockerfile', 'backend'], true);
      const metadata = JSON.parse(await docker(['image', 'inspect', `${project}-platform-${target}:local`]))[0];
      assert.equal(metadata.Config.User, '1000:1000');
      await docker(['run', '--rm', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--entrypoint', '/app/.venv/bin/python',
        `${project}-platform-${target}:local`, '-c', `
import importlib.util, os, pathlib, shutil
assert os.getuid() == 1000
assert (importlib.util.find_spec('opengym_platform.importer') is not None) == ${target === 'ops' ? 'True' : 'False'}
assert (importlib.util.find_spec('opengym_platform.backup') is not None) == ${target === 'ops' ? 'True' : 'False'}
assert (importlib.util.find_spec('opengym_platform.bundle') is not None) == ${target === 'ops' ? 'True' : 'False'}
assert (importlib.util.find_spec('opengym_platform.restore') is not None) == ${target === 'ops' ? 'True' : 'False'}
assert (importlib.util.find_spec('opengym_platform.restore_access') is not None) == ${target === 'ops' ? 'True' : 'False'}
assert (shutil.which('age') is not None) == ${target === 'ops' ? 'True' : 'False'}
assert (shutil.which('age-keygen') is not None) == ${target === 'ops' ? 'True' : 'False'}
import subprocess, sys, json
result = subprocess.run([sys.executable, '-m', 'opengym_platform.operations', 'import',
    '--config', '/missing-import-config', '--source', '/missing-source', '--target', 'new-a'], capture_output=True)
assert result.returncode == 2 and result.stderr == b''
assert json.loads(result.stdout)['code'] == ${target === 'ops' ? "'IMPORT_BLOCKED'" : "'IMPORT_TOOL_UNAVAILABLE'"}
assert not pathlib.Path('/app/tests').exists()
for name in ('pytest', 'ruff', 'mypy', 'pip'):
    assert importlib.util.find_spec(name) is None
for name in ('node', 'npm', 'uv', 'pip', 'claude', 'codex', 'bwrap'):
    assert shutil.which(name) is None
`], true);
    }
    await docker(['run', '--rm', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
      '--security-opt', 'no-new-privileges', `${project}-platform-ops:local`], true);
    await docker(['build', '--platform', 'linux/amd64', '--label', 'org.opengym.platform=synthetic',
      '--label', 'com.docker.compose.project=' + project, '--label', 'com.docker.compose.service=platform-diagnostics',
      '-t', project + '-platform-diagnostics:local', '-f', 'backend/diagnostics/Dockerfile', 'backend/diagnostics'], true);
    await docker(['build', '--platform', 'linux/amd64', '--label', 'org.opengym.platform=synthetic',
      '--label', 'com.docker.compose.project=' + project, '--label', 'com.docker.compose.service=platform-web',
      '--build-arg', 'VITE_API_PREFIX=/api/v1', '-t', project + '-platform-web:local', '-f', 'web/Dockerfile', '.'], true);
    await deploymentProof({ project, image, docker });
  } finally {
    await cleanup(project);
  }
});

async function deploymentProof({ project, image, docker }) {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-images-'));
  const versions = JSON.parse(readFileSync(join(root, 'backend/versions.json'), 'utf8'));
  const dockerfile = readFileSync(join(root, 'backend/Dockerfile'), 'utf8');
  for (const pin of [versions.pythonImage, versions.uvImage, versions.postgresImage]) {
    assert.ok(dockerfile.includes(`FROM ${pin}`));
  }
  const images = {};
  for (const target of ['runtime', 'migrate', 'ops', 'diagnostics', 'web']) {
    images[target] = JSON.parse(await docker(['image', 'inspect', `${project}-platform-${target}:local`]))[0].Id.slice(7);
  }
  const envFile = join(temporary, 'verify.env');
  const volumeNames = [];
  try {
    for (const environment of ['dev', 'ops']) {
      const secretRoot = join(temporary, environment);
      mkdirSync(secretRoot, { mode: 0o700 });
      for (const file of ['bootstrap_password', 'migrator_password', 'runtime_password', 'session_secret', 'coach_secret']) {
        writeFileSync(join(secretRoot, file), `synthetic-${environment}-${file}-${randomBytes(20).toString('hex')}'$$`, { mode: 0o444 });
      }
      writeFileSync(envFile, [
        `PLATFORM_WEB_PORT=${environment === 'dev' ? 8081 : 8080}`,
        `PLATFORM_SECRETS_DIR=${secretRoot.replaceAll('\\', '/')}`,
        `PLATFORM_WEB_DIGEST=${images.web}`, `PLATFORM_RUNTIME_DIGEST=${images.runtime}`,
        `PLATFORM_MIGRATE_DIGEST=${images.migrate}`, `PLATFORM_OPS_DIGEST=${images.ops}`,
        `PLATFORM_DIAGNOSTICS_DIGEST=${images.diagnostics}`,
        'INVITE_ONLY=1', 'ALLOW_GUEST=0', 'PASSWORD_LOGIN=true', 'DEFAULT_LANG=es-CL', 'MEDIA_UPLOADS=0',
      ].join('\n'));
      const instance = `opengym-platform-test-${randomBytes(8).toString('hex')}`;
      const owner = syntheticHarness({
        root, namespace: 'opengym-platform-test', label: 'org.opengym.platform', name: 'Platform',
        services: ['api', 'web', 'db', 'migrate', 'bootstrap', 'ops', 'diagnostics'], images: [], database: 'db',
        networkNames: ['app', 'database', 'diagnostics'], volumeName: `${environment}-postgres-data`,
        extraVolumes: { 'diagnostic-logs': { name: `${environment}-diagnostic-logs`, service: 'diagnostics' }, 'diagnostic-socket': { name: `${environment}-diagnostic-socket`, service: 'diagnostics' }, 'media-data': { name: `${environment}-media-data`, service: 'api' } },
      });
      const args = ['compose', '--project-directory', root, '--env-file', envFile, '-p', instance, '--profile', '*',
        '-f', join(root, 'deploy/docker-compose.yml'), '-f', join(root, `deploy/docker-compose.${environment === 'ops' ? 'prod' : 'dev'}.yml`)];
      for (const trustProxy of [undefined, '', '0', '1']) {
        const env = { ...process.env };
        delete env.TRUST_PROXY;
        if (trustProxy !== undefined) env.TRUST_PROXY = trustProxy;
        const resolved = JSON.parse(execFileSync(
          'docker', [...args, 'config', '--format', 'json'],
          { cwd: root, env, encoding: 'utf8', timeout: 30000 },
        ));
        assert.equal(resolved.services.api.environment.TRUST_PROXY, trustProxy || '0');
        assert.ok(resolved.services.api.command.includes('--no-proxy-headers'));
      }
      const config = JSON.parse(await docker([...args, 'config', '--format', 'json']));
      assert.equal(config.services.db.image, versions.postgresImage);
      assert.equal(config.networks.database.internal, true);
      assert.equal(config.networks.diagnostics.internal, true);
      assert.equal(config.services.diagnostics.logging.driver, 'none');
      assert.equal(config.services.api.logging.driver, 'none');
      for (const source of ['db', 'web']) {
        assert.equal(config.services[source].logging.driver, 'syslog');
        assert.equal(config.services[source].logging.options.mode, 'non-blocking');
        assert.equal(config.services[source].logging.options['cache-disabled'], 'true');
      }
      assert.ok(!config.networks.app.internal);
      assert.deepEqual(Object.keys(config.services.web.networks), ['app']);
      assert.deepEqual(Object.keys(config.services.db.networks), ['database']);
      assert.deepEqual(Object.keys(config.services.api.networks).sort(), ['app', 'database']);
      assert.deepEqual(config.services.web.ports.map(port => [port.host_ip, port.published, port.target]), [['127.0.0.1', environment === 'dev' ? '8081' : '8080', 80]]);
      for (const [service, definition] of Object.entries(config.services)) {
        assert.ok(!definition.privileged && !definition.cap_add?.length);
        assert.ok(definition.read_only && definition.user !== '0');
        assert.deepEqual(definition.cap_drop, ['ALL']);
        if (!['db', 'web'].includes(service)) assert.equal(definition.logging.driver, 'none');
        if (service !== 'web') assert.ok(!definition.ports?.length);
        if (environment === 'ops') {
          assert.ok(!definition.build);
          if (service !== 'db') assert.match(definition.image, /^sha256:[a-f0-9]{64}$/);
          assert.ok(!definition.volumes?.some(volume => volume.type === 'bind'));
        }
      }
      assert.ok(config.services.api.command.includes('--no-proxy-headers'));
      assert.ok(config.services.api.volumes?.some(volume => volume.type === 'volume' && volume.source === 'media-data' && volume.target === '/data'));
      assert.deepEqual(config.services.api.secrets.map(secret => secret.source), ['runtime_password', 'session_secret', 'coach_secret']);
      assert.equal(config.services.api.environment.COACH_DISABLED, '0');
      assert.equal(config.services.migrate.secrets.length, 1);
      assert.equal(config.services.migrate.secrets[0].source, 'migrator_password');
      assert.ok(!config.services.ops.secrets?.length);
      if (environment === 'dev') {
        assert.equal(config.services.web.build.context, root.replace(/[\\/]$/, ''));
        assert.equal(config.services.web.build.dockerfile, 'web/Dockerfile');
        assert.equal(config.services.web.build.args.VITE_API_PREFIX, '/api/v1');
        assert.ok(config.services.api.command.includes('--reload'));
        assert.deepEqual(config.services.api.volumes.map(volume => volume.target).sort(), ['/app/src', '/data', '/run/diagnostic-logs', '/run/diagnostics']);
      } else assert.ok(!config.services.api.command.includes('--reload'));
      volumeNames.push(config.volumes['postgres-data'].name);
      assert.equal(config.volumes['media-data'].name, `${instance}_${environment}-media-data`);
      assert.doesNotMatch(JSON.stringify(config), /docker\.sock|coach-auth|seccomp|FOUNDATION_DB_|PLATFORM_DB_PASSWORD"/);
      // Run real nginx/API/PG on owned resources; no synthetic port competes with the user's instance.
      for (const [service, definition] of Object.entries(config.services)) {
        delete definition.build;
        definition.image = service === 'db' ? versions.postgresImage
          : service === 'bootstrap' || service === 'migrate' ? `${project}-platform-migrate:local`
          : service === 'diagnostics' ? `${project}-platform-diagnostics:local`
          : service === 'web' ? `${project}-platform-web:local`
          : service === 'ops' ? `${project}-platform-ops:local` : image;
        definition.labels = { ...definition.labels, 'org.opengym.platform': 'synthetic' };
        definition.pull_policy = 'never';
      }
      for (const name of ['app', 'database', 'diagnostics']) config.networks[name].labels = {
        'org.opengym.platform': 'synthetic', 'com.docker.compose.service': name,
      };
      config.volumes['postgres-data'].labels = { 'org.opengym.platform': 'synthetic', 'com.docker.compose.service': 'db' };
      config.volumes['media-data'].labels = { 'org.opengym.platform': 'synthetic', 'com.docker.compose.service': 'api' };
      config.volumes['diagnostic-logs'].driver_opts = { type: 'tmpfs', device: 'tmpfs', o: 'size=268435456,uid=1000,gid=1000,mode=0700' };
      for (const name of ['diagnostic-logs', 'diagnostic-socket']) config.volumes[name].labels = { 'org.opengym.platform': 'synthetic', 'com.docker.compose.service': 'diagnostics' };
      config.services.web.ports = [];
      // Only this disposable supervisor's clock advances; product has no fast-retention flag.
      config.services.diagnostics.entrypoint = ['python', '-c',
        "import pathlib,time,subprocess,runpy; clock=time.monotonic; time.monotonic=lambda:clock()+(7200 if pathlib.Path('/state/advance').exists() else 0); runpy.run_path('/usr/local/bin/diagnostics.py',run_name='__main__')"];
      config.services.ops.networks = { app: null };
      const configuration = join(temporary, `${environment}.json`);
      writeFileSync(configuration, JSON.stringify(config));
      const compose = [...args.slice(0, args.indexOf('-f')), '-f', configuration];
      try {
        await docker([...compose, 'up', '-d', '--wait', '--wait-timeout', '60', 'db'], true);
        await docker([...compose, 'run', '--rm', '--no-deps', 'bootstrap'], true);
        await docker([...compose, 'run', '--rm', '--no-deps', 'migrate'], true);
        await docker([...compose, 'up', '-d', '--no-deps', 'api'], true);
        await docker([...compose, 'exec', '-T', 'api', '/app/.venv/bin/python', '-c', `
import json, time, urllib.request, urllib.error, pathlib, os
assert os.getuid() == 1000
assert pathlib.Path('/data').stat().st_mode & 0o777 == 0o700
pathlib.Path('/data/synthetic-4-1').write_text('owned persistent media volume')
for attempt in range(100):
    try:
        with urllib.request.urlopen('http://127.0.0.1:3000/api/v1/health/ready', timeout=1) as response:
            assert json.load(response) == {'code': 'PLATFORM_READY_OK'}
        break
    except (OSError, urllib.error.URLError):
        time.sleep(0.1)
else:
    raise AssertionError('platform HTTP did not become ready')
with urllib.request.urlopen('http://127.0.0.1:3000/api/v1/health', timeout=1) as response:
    assert json.load(response) == {'ok': True, 'users': 0, 'writable': True}
with urllib.request.urlopen('http://127.0.0.1:3000/api/v1/config', timeout=1) as response:
    assert json.load(response) == {'invite_only': True, 'allow_guest': False, 'password_login': True, 'default_lang': 'es-CL'}
print('PLATFORM_COMPOSE_HTTP_OK')
`], true);
        await docker([...compose, 'up', '-d', '--no-deps', 'web']);
        await docker([...compose, 'exec', '-T', 'api', '/app/.venv/bin/python', '-c', `
import json,time,urllib.request
for _ in range(100):
 try:
  with urllib.request.urlopen('http://web:80/api/v1/health?SENSITIVE_9_4_URL',timeout=1) as r:assert json.load(r)['ok']
  break
 except OSError:time.sleep(.1)
else:raise AssertionError('real nginx proxy not ready')
print('PLATFORM_REAL_NGINX_PROXY_OK')
`], true);
        await docker([...compose, 'run', '--rm', '--no-deps', 'ops', '-c', `
import json,subprocess,sys
result=subprocess.run([sys.executable,'-m','opengym_platform.operations','diagnose','--config','/run/operator/config.json'],capture_output=True,text=True,timeout=5)
assert result.returncode==1 and result.stderr==''
state=json.loads(result.stdout)
assert state['database']=='writable' and state['schema']=='current'
assert state['backup']=={'state':'missing','verified':False}
assert state['logging']['sink']=='space_available'
assert state['pool']['size']<=state['pool']['maximum']
print('PLATFORM_PRIVATE_DIAGNOSE_OK')
`], true);
        await docker([...compose, 'exec', '-T', 'diagnostics', 'python', '-c', `
import pathlib,time
for _ in range(50):
 p=pathlib.Path('/logs/postgres.log')
 if p.exists() and p.stat().st_size:break
 time.sleep(.1)
else:raise AssertionError('native PostgreSQL stream missing')
assert '"service":"postgres"' in p.read_text()
assert 'synthetic-' not in p.read_text()
print('PLATFORM_POSTGRES_LOG_OK')
`], true);
        await docker([...compose, 'exec', '-T', 'db', 'psql', '--no-psqlrc', '--set=ON_ERROR_STOP=1',
          '-U', 'opengym_platform_bootstrap', '-d', config.services.db.environment.POSTGRES_DB,
          '-c', "INSERT INTO identity.users(id,display_name,is_admin,session_version) VALUES('diag-admin','Diagnostic fixture',true,0)"]);
        const provider = `${instance}-ops-run-${randomBytes(6).toString('hex')}`;
        await docker([...compose, 'run', '-d', '--no-deps', '--name', provider, 'ops', '-c', `
from http.server import BaseHTTPRequestHandler,HTTPServer
class Fixture(BaseHTTPRequestHandler):
 def do_POST(self):
  self.rfile.read(int(self.headers['Content-Length']))
  body=b'{"error":"SENSITIVE_9_4_PROVIDER"}'
  self.send_response(401);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
HTTPServer(('0.0.0.0',9090),Fixture).serve_forever()
`]);
        await docker([...compose, 'exec', '-T', 'db', 'psql', '--no-psqlrc', '--set=ON_ERROR_STOP=1',
          '-U', 'opengym_platform_bootstrap', '-d', config.services.db.environment.POSTGRES_DB,
          '-c', `UPDATE coach.settings SET enabled=true,provider='compatible'; UPDATE coach.provider_settings SET model='fixture',options='{"baseUrl":"http://${provider}:9090"}'::jsonb WHERE provider='compatible'; INSERT INTO training.documents(owner_id,document) VALUES('diag-admin','{"coach":{"consent":{"agreedAt":1}},"routines":[],"workouts":[]}'); DO $$BEGIN RAISE WARNING 'SENSITIVE_9_4_SQL'; END$$;`]);
        await docker([...compose, 'exec', '-T', 'api', '/app/.venv/bin/python', '-c', `
import json,time,urllib.request
from opengym_platform.identity.sessions import sign
from opengym_platform.core.platform_settings import load_session_secret
token=sign('diag-admin:'+str(int(time.time()*1000)+60000)+':0',load_session_secret())
headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Cookie':'fixture=SENSITIVE_9_4_COOKIE','X-Request-ID':'SENSITIVE_9_4_TRACE','User-Agent':'SENSITIVE_9_4_AGENT'}
req=urllib.request.Request('http://web:80/api/v1/coach/review?SENSITIVE_9_4_QUERY',data=b'{"note":"SENSITIVE_9_4_PROMPT"}',headers=headers)
with urllib.request.urlopen(req,timeout=3) as r:assert r.status==202
for _ in range(100):
 with urllib.request.urlopen(urllib.request.Request('http://web:80/api/v1/coach/status',headers=headers),timeout=3) as r:state=json.load(r)
 if state.get('last') and not state.get('job'):
  assert state['last']['errorClass']=='auth';break
 time.sleep(.05)
else:raise AssertionError('private provider fixture did not finish')
print('PLATFORM_SENSITIVE_HTTP_DB_PROVIDER_FIXTURE_OK')
`], true);
        await diagnosticCopies({ compose, docker, instance, provider, database: config.services.db.environment.POSTGRES_DB });
        await docker([...compose, 'exec', '-T', 'diagnostics', 'python', '-c', `
import errno,pathlib
try:
 with pathlib.Path('/logs/api.log.168').open('wb') as stream:
  for _ in range(65):stream.write(b'x'*(4*1024*1024))
except OSError as error:
 assert error.errno==errno.ENOSPC
else:raise AssertionError('fixture did not fill tmpfs')
print('PLATFORM_DIAGNOSTIC_DISK_FULL')
`], true);
        const invitationDuringFault = `
import json,time,urllib.request
from opengym_platform.identity.sessions import sign
from opengym_platform.core.platform_settings import load_session_secret
token=sign('diag-admin:'+str(int(time.time()*1000)+60000)+':0',load_session_secret())
request=urllib.request.Request('http://web:80/api/v1/admin/invites/new?SENSITIVE_9_4_FAULT',data=b'{"note":"SENSITIVE_9_4_NOTE"}',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=3) as response:assert response.status==200
print('PLATFORM_HTTP_COMMIT_DURING_SINK_FAULT')
`;
        await docker([...compose, 'exec', '-T', 'api', '/app/.venv/bin/python', '-c', invitationDuringFault], true);
        await docker([...compose, 'run', '--rm', '--no-deps', 'ops', '-c', `
from opengym_platform.operations import diagnose
code,state=diagnose('/run/operator/config.json')
assert code==1 and state['logging']['degraded'] and state['logging']['sink']=='full'
print('PLATFORM_FULL_SINK_VISIBLE')
`], true);
        const closing = Date.now();
        await docker([...compose, 'stop', '--timeout', '5', 'diagnostics']);
        assert.ok(Date.now() - closing < 5000, 'full collector shutdown exceeds five seconds');
        assert.notEqual(JSON.parse(await docker(['inspect', `${instance}-diagnostics-1`]))[0].State.ExitCode, 137);
        await docker([...compose, 'exec', '-T', 'api', '/app/.venv/bin/python', '-c', invitationDuringFault], true);
        await docker([...compose, 'run', '--rm', '--no-deps', 'ops', '-c', `
from opengym_platform.operations import diagnose
code,state=diagnose('/run/operator/config.json')
assert code==1 and state['logging']['degraded'] and state['logging']['failures']>0
print('PLATFORM_STOPPED_SINK_VISIBLE')
`], true);
        await docker([...compose, 'run', '--rm', '--no-deps', '--entrypoint', 'python', 'diagnostics', '-c',
          "import pathlib;pathlib.Path('/logs/api.log.168').unlink()"]);
        const committed = await docker([...compose, 'exec', '-T', 'db', 'psql', '--no-psqlrc', '-tAc',
          'SELECT count(*) FROM identity.invitations', '-U', 'opengym_platform_bootstrap', '-d', config.services.db.environment.POSTGRES_DB]);
        assert.equal(committed.trim(), '2', 'both fault-time HTTP writes must commit');
        await docker([...compose, 'up', '-d', '--wait', '--wait-timeout', '30', 'diagnostics']);
        await docker([...compose, 'exec', '-T', 'diagnostics', 'rotate']);
        await diagnosticCopies({ compose, docker, instance, provider, database: config.services.db.environment.POSTGRES_DB, allowTorn: true });
        const stopping = Date.now();
        await docker([...compose, 'stop', '--timeout', '5', 'api']);
        assert.ok(Date.now() - stopping < 5000, 'API shutdown exceeds five seconds');
        assert.notEqual(JSON.parse(await docker(['inspect', `${instance}-api-1`]))[0].State.ExitCode, 137);
        await docker([...compose, 'exec', '-T', 'diagnostics', 'python', '-c', `
import pathlib,time,os
for name in ('api','nginx','postgres','ops'):
 for suffix in ('','.1'):
  p=pathlib.Path('/logs/'+name+'.log'+suffix);p.write_text('stopped-api-expired');os.utime(p,(time.time()-8*86400,)*2)
pathlib.Path('/state/advance').touch()
for _ in range(100):
 try:
  if not any(b'stopped-api-expired' in p.read_bytes() for p in pathlib.Path('/logs').glob('*.log*')):break
 except FileNotFoundError:pass
 time.sleep(.05)
else:raise AssertionError('stopped API prevented hourly retention')
print('PLATFORM_STOPPED_API_HOURLY_RETENTION_OK')
`], true);
        await docker([...compose, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '30', 'api']);
        await docker([...compose, 'exec', '-T', 'api', '/app/.venv/bin/python', '-c',
          "import urllib.request;assert urllib.request.urlopen('http://web:80/api/v1/health',timeout=3).status==200"]);
        await docker([...compose, 'run', '--rm', '--no-deps', '--entrypoint', '/app/.venv/bin/python', 'api', '-c', `
import asyncio, pathlib, asyncpg
assert pathlib.Path('/data/synthetic-4-1').read_text() == 'owned persistent media volume'
from opengym_platform.core.platform_settings import load_database
async def check():
    target = load_database('runtime')
    assert not pathlib.Path('/run/secrets/migrator_password').exists()
    assert not pathlib.Path('/run/secrets/bootstrap_password').exists()
    connection = await asyncpg.connect(host=target.host, database=target.database, user=target.user, password=target.password, ssl=False, timeout=5)
    try:
        assert await connection.fetchval('SELECT current_user') == 'opengym_api_runtime'
        assert await connection.fetchval('SELECT version_num FROM public.alembic_version') == 'p004_audit'
        try:
            await connection.execute('SET ROLE opengym_schema_owner')
        except asyncpg.InsufficientPrivilegeError:
            pass
        else:
            raise AssertionError('runtime assumed owner')
    finally:
        await connection.close(timeout=5)
asyncio.run(check())
print('PLATFORM_DEPLOYMENT_FILES_OK')
`], true);
        const db = JSON.parse(await docker(['container', 'inspect', `${instance}-db-1`]))[0];
        const address = Object.values(db.NetworkSettings.Networks)[0].IPAddress;
        await docker(['run', '--rm', '--name', `${instance}-web-run-${randomBytes(6).toString('hex')}`,
          '--label', `com.docker.compose.project=${instance}`, '--label', 'com.docker.compose.service=web',
          '--label', 'org.opengym.platform=synthetic', '--network', `${instance}_app`, '--read-only', '--cap-drop', 'ALL',
          '--security-opt', 'no-new-privileges', '--log-driver', 'none', image, '-c', `
import socket,pathlib
assert not pathlib.Path('/run/secrets/database_password').exists()
try:socket.create_connection((${JSON.stringify(address)},5432),timeout=1).close()
except OSError:print('PLATFORM_WEB_DB_DENIED')
else:raise AssertionError('web network reached private database')
`], true);
      } finally {
        await owner.cleanup(instance);
      }
    }
    assert.notEqual(volumeNames[0], volumeNames[1]);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}

async function diagnosticCopies({ compose, docker, instance, provider, database, allowTorn = false }) {
  for (const container of [...['api', 'web', 'db', 'diagnostics'].map(service => `${instance}-${service}-1`), provider]) {
    const meta = JSON.parse(await docker(['inspect', container]))[0];
    const service = meta.Config.Labels['com.docker.compose.service'];
    assert.equal(meta.LogPath, '', `${service} must have no Docker log file`);
    const config = meta.HostConfig.LogConfig;
    assert.equal(config.Type, ['db', 'web'].includes(service) ? 'syslog' : 'none');
    if (config.Type === 'syslog') {
      assert.equal(config.Config.mode, 'non-blocking');
      assert.equal(config.Config['max-buffer-size'], '1m');
      assert.equal(config.Config['cache-disabled'], 'true');
    }
    assert.doesNotMatch(JSON.stringify(meta.State.Health || {}), /SENSITIVE_9_4/);
    let refused = false;
    try {
      const output = execFileSync('docker', ['logs', container], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 5000 });
      assert.equal(output, '');
    } catch (error) {
      assert.ok(error.status > 0);
      assert.match(String(error.stderr), /configured logging driver does not support reading/);
      assert.doesNotMatch(String(error.stdout) + String(error.stderr), /SENSITIVE_9_4/);
      refused = true;
    }
    assert.ok(refused, `${service} unexpectedly supports a durable Docker log cache`);
  }
  await docker([...compose, 'exec', '-T', 'diagnostics', 'python', '-c', `
import pathlib,json,time
for _ in range(100):
 if all(any(p.stat().st_size for p in pathlib.Path('/logs').glob(n+'.log*')) for n in ('api','nginx','postgres')):break
 time.sleep(.05)
else:raise AssertionError('privacy proof needs nonempty real source streams')
for p in pathlib.Path('/logs').iterdir():
 assert p.is_file() and not p.is_symlink()
 assert p.stat().st_mode & 0o777 == 0o600
 raw=p.read_text();assert 'SENSITIVE_9_4' not in raw
 torn=0
 for line in raw.splitlines():
  try:record=json.loads(line)
  except json.JSONDecodeError:
   # ENOSPC can tear an omfile write. All bytes still undergo the privacy assertion above.
   assert ${allowTorn ? 'True' : 'False'}
   torn+=1;assert torn<=1;continue
  if p.name.startswith('api.log'):
   assert set(record)=={'service','revision','severity','request_id','operation','result','duration_ms','time'}
  else:assert set(record)=={'service','event','severity'}
assert pathlib.Path('/logs').stat().st_mode & 0o777 == 0o700
assert sum(p.stat().st_size for p in pathlib.Path('/logs').iterdir()) < 256*1024*1024
for p in pathlib.Path('/state').iterdir():
 assert p.name in {'retention.lock','logrotate.state','rsyslog.pid','ready','advance'}
 assert 'SENSITIVE_9_4' not in p.read_text()
config=pathlib.Path('/etc/opengym/rsyslog.conf').read_text()
assert 'queue.type="FixedArray" queue.size="256"' in config
assert 'queue.filename' not in config
print('PLATFORM_ALL_PRIVATE_STREAMS_AND_DOCKER_COPIES_OK')
`], true);
  const pg = await docker([...compose, 'exec', '-T', 'db', 'psql', '--no-psqlrc', '-tAc',
    "SELECT current_setting('logging_collector')||','||current_setting('log_destination')||','||current_setting('log_statement')", '-U', 'opengym_platform_bootstrap', '-d', database]);
  assert.equal(pg.trim(), 'off,stderr,none');
  await docker([...compose, 'exec', '-T', 'db', 'sh', '-ec',
    'test ! -e "$PGDATA/current_logfiles"; test ! -d "$PGDATA/log"; test ! -d "$PGDATA/pg_log"']);
  await docker([...compose, 'exec', '-T', 'web', 'sh', '-ec',
    'test "$(readlink /var/log/nginx/access.log)" = /dev/stdout; test "$(readlink /var/log/nginx/error.log)" = /dev/stderr']);
}
