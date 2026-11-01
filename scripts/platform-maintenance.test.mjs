import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { randomBytes } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { syntheticHarness } from './synthetic-harness.mjs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

// Public host CLI: malformed configuration must not reach Docker or alter files.
test('maintenance rejects an incomplete writer inventory before controlling services', t => {
  const root = mkdtempSync(join(tmpdir(), 'opengym-maintenance-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const config = join(root, 'operator.json');
  const source = JSON.stringify({ instance_id: 'synthetic-a', writers: [] });
  writeFileSync(config, source);
  const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
    '--config', config, '--reason', 'scheduled'], {
    encoding: 'utf8', timeout: 5000, env: { ...process.env, PATH: '' },
  });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /MAINTENANCE_CONFIG_INVALID/);
  assert.equal(readFileSync(config, 'utf8'), source);
  writeFileSync(config, JSON.stringify({ instance_id: 'synthetic-a', project: 'synthetic-a',
    project_directory: root, compose_files: [config], env_file: config,
    state_root: join(root, 'PRIVATE-PATH-SENTINEL'), writers: ['api'] }));
  const missing = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
    '--config', config, '--reason', 'scheduled'], { encoding: 'utf8', timeout: 5000, env: { ...process.env, PATH: '' } });
  assert.equal(missing.status, 1);
  assert.match(missing.stderr, /MAINTENANCE_FAILED/);
  assert.doesNotMatch(missing.stderr, /PRIVATE-PATH-SENTINEL|ENOENT/);
});

test('maintenance overlay gives only ops the SQL capture credentials and state mount', async t => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-maintenance-config-'));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const state = join(temporary, 'state').replaceAll('\\', '/');
  const configFile = join(temporary, 'capture.json').replaceAll('\\', '/');
  const envFile = join(temporary, 'explicit.env');
  const instance = 'synthetic-maintenance';
  writeFileSync(configFile, '{}');
  writeFileSync(envFile, [
    `PLATFORM_SECRETS_DIR=${temporary.replaceAll('\\', '/')}`,
    `PLATFORM_INSTANCE_ID=${instance}`, `PLATFORM_MAINTENANCE_STATE_DIR=${state}`,
    `PLATFORM_BACKUP_CONFIG_FILE=${configFile}`,
    ...['WEB', 'RUNTIME', 'MIGRATE', 'OPS', 'DIAGNOSTICS'].map(role => `PLATFORM_${role}_DIGEST=${'a'.repeat(64)}`),
  ].join('\n'));
  const { docker } = syntheticHarness({ root });
  const model = JSON.parse(await docker(['compose', '--project-directory', root, '--env-file', envFile,
    '-p', instance, '--profile', 'tools', ...['docker-compose.yml', 'docker-compose.prod.yml',
      'docker-compose.maintenance.yml'].flatMap(file => ['-f', join(root, 'deploy', file)]), 'config', '--format', 'json']));
  assert.equal(model.services.db.labels['org.opengym.maintenance.instance'], instance);
  assert.equal(model.services.db.labels['org.opengym.maintenance.state'], state);
  assert.equal(model.services.ops.environment.PLATFORM_DB_PASSWORD_FILE, '/run/secrets/backup_password');
  assert.deepEqual(model.services.ops.secrets.map(secret => secret.source), ['backup_password']);
  assert.ok(model.services.ops.volumes.some(volume => volume.target === '/run/maintenance' && volume.type === 'bind'
    && volume.bind.create_host_path === false));
  assert.deepEqual(model.services.api.secrets.map(secret => secret.source), ['runtime_password', 'session_secret', 'coach_secret']);
  assert.ok(!model.services.api.volumes.some(volume => volume.target === '/run/maintenance'));
  assert.ok(!model.services.db.ports?.length);
});

test('host backup stops actual writers, leaves PostgreSQL available and captures all owners', async () => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-maintenance-'));
  const project = `opengym-platform-test-${randomBytes(8).toString('hex')}`;
  const image = `${project}-platform-test:local`;
  const composeFile = join(temporary, 'compose.json');
  const envFile = join(temporary, 'empty.env');
  const state = join(temporary, 'state');
  mkdirSync(state, { mode: 0o700 });
  const protect = path => {
    if (process.platform !== 'win32') return;
    const result = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      "$ErrorActionPreference='Stop'; $u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User; "
      + "$a=New-Object System.Security.AccessControl.DirectorySecurity; $a.SetOwner($u); "
      + "$a.SetAccessRuleProtection($true,$false); "
      + "$a.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new($u,'FullControl','ContainerInherit,ObjectInherit','None','Allow')); "
      + "Set-Acl -LiteralPath $env:OPENGYM_TEST_DIRECTORY -AclObject $a"],
    { env: { ...process.env, OPENGYM_TEST_DIRECTORY: path }, stdio: 'ignore', timeout: 5000 });
    assert.equal(result.status, 0, 'Cannot protect owned synthetic directory');
  };
  protect(temporary);
  protect(state);
  writeFileSync(envFile, '');
  const { docker, cleanup } = syntheticHarness({ root, namespace: 'opengym-platform-test',
    label: 'org.opengym.platform', name: 'Maintenance', services: ['db', 'api', 'ops', 'migrate'],
    images: ['platform-test'], database: 'db' });
  const compose = ['compose', '--project-directory', root, '--env-file', envFile, '-p', project, '-f', composeFile];
  const labels = { 'org.opengym.platform': 'synthetic' };
  const secret = name => {
    const path = join(temporary, name);
    writeFileSync(path, `synthetic-maintenance-${name}-only-0123456789`, { mode: 0o600 });
    return { type: 'bind', source: path, target: `/run/secrets/${name}`, read_only: true };
  };
  const secrets = ['bootstrap', 'migrator', 'runtime', 'session', 'backup'].map(secret);
  const environment = { PLATFORM_ENV: 'dev', PLATFORM_DB_MODE: 'local_compose', PLATFORM_DB_HOST: 'db',
    PLATFORM_DB_PORT: '5432', PLATFORM_DB_NAME: 'opengym_dev', PLATFORM_DB_TLS: 'disable',
    PLATFORM_DB_PASSWORD_FILE: '/run/secrets/bootstrap', PLATFORM_MIGRATOR_PASSWORD_FILE: '/run/secrets/migrator',
    PLATFORM_RUNTIME_PASSWORD_FILE: '/run/secrets/runtime', PLATFORM_SESSION_SECRET_FILE: '/run/secrets/session',
    MEDIA_UPLOADS: '0', PASSWORD_LOGIN: 'true' };
  // Private bind files must belong to the test caller, including CI's UID 1001.
  const user = `${process.getuid?.() ?? 1000}:${process.getgid?.() ?? 1000}`;
  const python = { image, entrypoint: ['python'], labels, user, read_only: true,
    cap_drop: ['ALL'], security_opt: ['no-new-privileges:true'], tmpfs: ['/tmp'], networks: ['private'], restart: 'no' };
  const opsConfig = join(temporary, 'capture.json');
  writeFileSync(opsConfig, JSON.stringify({ instance_id: 'synthetic-a', project,
    staging_root: '/run/maintenance', expected_schema: 'p004_audit' }));
  writeFileSync(composeFile, JSON.stringify({ services: {
    db: { image: JSON.parse(readFileSync('backend/versions.json')).postgresImage,
      labels: { ...labels, 'org.opengym.maintenance.instance': 'synthetic-a', 'org.opengym.maintenance.state': state.replaceAll('\\', '/') }, user,
      environment: { POSTGRES_USER: 'opengym_platform_bootstrap', POSTGRES_DB: 'opengym_dev',
        POSTGRES_PASSWORD_FILE: '/run/secrets/bootstrap' }, volumes: [secrets[0], 'postgres-data:/var/lib/postgresql'],
      networks: ['private'], healthcheck: { test: ['CMD', 'pg_isready', '-U', 'opengym_platform_bootstrap', '-d', 'opengym_dev'],
        interval: '1s', timeout: '3s', retries: 40 }, restart: 'no' },
    migrate: { ...python, profiles: ['tools'], environment, volumes: secrets,
      command: ['-m', 'opengym_platform.platform_migrate', '--deployment', 'bootstrap'] },
    api: { ...python, environment: { ...environment, PLATFORM_DB_PASSWORD_FILE: '/run/secrets/runtime' },
      volumes: secrets.filter(item => /runtime|session/.test(item.target)),
      command: ['-m', 'uvicorn', 'opengym_platform.application:create_app', '--factory', '--host', '0.0.0.0',
        '--port', '3000', '--no-access-log', '--no-proxy-headers'], stop_grace_period: '30s' },
    ops: { ...python, entrypoint: ['python', '/app/tests/platform/backup_probe.py'], profiles: ['tools'], environment: { ...environment, PLATFORM_DB_PASSWORD_FILE: '/run/secrets/backup' },
      volumes: [secrets[4], { type: 'bind', source: state, target: '/run/maintenance' },
        { type: 'bind', source: opsConfig, target: '/run/operator/config.json', read_only: true }] },
  }, networks: { private: { internal: true, labels: { ...labels, 'com.docker.compose.service': 'private' } } },
  volumes: { 'postgres-data': { labels: { ...labels, 'com.docker.compose.service': 'db' } } } }));
  const config = join(temporary, 'operator.json');
  writeFileSync(config, JSON.stringify({ instance_id: 'synthetic-a', project, project_directory: root,
    compose_files: [composeFile], env_file: envFile, state_root: state, writers: ['api'] }), { mode: 0o600 });
  const invoke = () => spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
    '--config', config, '--reason', 'scheduled'], { encoding: 'utf8', timeout: 180_000 });
  const sql = async statement => docker([...compose, 'exec', '-T', 'db', 'psql', '-U', 'opengym_platform_bootstrap',
    '-d', 'opengym_dev', '-v', 'ON_ERROR_STOP=1', '-Atc', statement]);
  const ready = () => docker([...compose, 'exec', '-T', 'api', 'python', '-c', `import urllib.request,time
for _ in range(100):
 try:
  assert urllib.request.urlopen('http://127.0.0.1:3000/api/v1/health/ready',timeout=1).status==200;break
 except Exception:time.sleep(.1)
else:raise AssertionError('API_NOT_READY')`]);
  try {
    await docker(['build', '--target', 'test', '--label', `com.docker.compose.project=${project}`,
      '--label', 'com.docker.compose.service=platform-test', '--label', 'org.opengym.platform=synthetic',
      '-t', image, '-f', 'backend/Dockerfile', 'backend'], true);
    await docker([...compose, 'up', '-d', '--wait', 'db']);
    await docker([...compose, 'run', '--rm', '--no-deps', 'migrate'], true);
    await docker([...compose, 'run', '--rm', '--no-deps', '-e', 'PLATFORM_DB_PASSWORD_FILE=/run/secrets/migrator',
      'migrate', '-m', 'opengym_platform.platform_migrate', '--deployment', 'up'], true);
    await sql(readFileSync('backend/backup-role.sql', 'utf8'));
    await sql(readFileSync('backend/backup-role.sql', 'utf8'));
    await sql("ALTER ROLE opengym_backup PASSWORD 'synthetic-maintenance-backup-only-0123456789'; "
      + "INSERT INTO identity.users(id,display_name) VALUES ('A','synthetic A'),('B','synthetic B'); "
      + "INSERT INTO training.documents(owner_id,document) VALUES ('A','{\"_rev\":7,\"_wid\":\"a\",\"_prior\":{\"notes\":null}}'),"
      + "('B','{\"_rev\":11,\"_wid\":\"b\",\"notes\":\"synthetic B\"}')");
    const tables = (await sql("SELECT format('%I.%I',schemaname,tablename) FROM pg_tables WHERE schemaname IN "
      + "('public','identity','training','coach','administration','notifications','audit') ORDER BY 1")).trim().split(/\r?\n/);
    const digestSQL = tables.map((table, index) => `SELECT ${index} AS n,count(*)::text || ':' || coalesce(md5(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text),'empty') AS digest FROM ${table} t`).join(' UNION ALL ') + ' ORDER BY n';
    const expectedDigests = (await sql(digestSQL)).trim();
    await docker([...compose, 'up', '-d', '--no-deps', 'api']);
    await ready();
    const first = spawn(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
      '--config', config, '--reason', 'scheduled'], { stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    first.stdout.on('data', chunk => { stdout += chunk; });
    first.stderr.on('data', chunk => { stderr += chunk; });
    const finished = new Promise(resolve => first.on('close', status => resolve({ status, stdout, stderr })));
    try {
      for (let i = 0; i < 200; i++) {
        if (existsSync(join(state, 'journal.json'))
          && JSON.parse(readFileSync(join(state, 'journal.json'))).phase === 'capturing') break;
        if (first.exitCode !== null) break;
        await sleep(50);
      }
      assert.ok(existsSync(join(state, 'journal.json')), stderr);
      assert.equal(JSON.parse(readFileSync(join(state, 'journal.json'))).phase, 'capturing', stderr);
      const stopped = JSON.parse(await docker(['inspect', `${project}-api-1`]))[0];
      assert.equal(stopped.State.Running, false);
      assert.equal(stopped.State.ExitCode, 0);
      assert.match(await sql('SELECT 1'), /1/);
      const competing = invoke();
      assert.equal(competing.status, 1);
      assert.match(competing.stderr, /MAINTENANCE_LOCKED/);
      const alternate = join(temporary, 'alternate');
      mkdirSync(alternate, { mode: 0o700 });
      protect(alternate);
      const alternateConfig = join(temporary, 'alternate.json');
      writeFileSync(alternateConfig, JSON.stringify({ ...JSON.parse(readFileSync(config)), state_root: alternate }));
      const bypass = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
        '--config', alternateConfig, '--reason', 'scheduled'], { encoding: 'utf8', timeout: 15_000 });
      assert.equal(bypass.status, 1);
      assert.match(bypass.stderr, /MAINTENANCE_STATE_OWNERSHIP/);
    } finally {
      writeFileSync(join(state, 'allow-capture'), '');
    }
    const result = await finished;
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, /BACKUP_CAPTURED_UNVERIFIED/, result.stderr);
    const journal = JSON.parse(readFileSync(join(state, 'journal.json')));
    assert.equal(journal.phase, 'captured_unverified');
    assert.deepEqual(journal.previously_running, ['api']);
    assert.ok(journal.pause_ms > 0 && journal.pause_ms < 120_000);
    console.log(`SQL_CAPTURE_PAUSE_MS=${journal.pause_ms}`);
    const dump = join(state, journal.operation, 'database.dump');
    assert.ok(readFileSync(dump).length > 1000);
    assert.match(await sql('SELECT 1'), /1/);
    await ready();
    assert.equal((await sql("SELECT NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication) "
      + "FROM pg_roles WHERE rolname='opengym_backup'")).trim(), 't');
    assert.equal((await sql("SELECT pg_has_role('opengym_backup','pg_read_all_stats','USAGE')")).trim(), 't');
    await sql('CREATE DATABASE opengym_capture');
    await docker(['cp', dump, `${project}-db-1:/tmp/capture.dump`]);
    await docker([...compose, 'exec', '-T', 'db', 'pg_restore', '--exit-on-error', '-U',
      'opengym_platform_bootstrap', '-d', 'opengym_capture', '/tmp/capture.dump']);
    assert.equal((await docker([...compose, 'exec', '-T', 'db', 'psql', '-U', 'opengym_platform_bootstrap',
      '-d', 'opengym_capture', '-Atc', 'SELECT string_agg(id,\',\' ORDER BY id) FROM identity.users'])).trim(), 'A,B');
    assert.equal((await docker([...compose, 'exec', '-T', 'db', 'psql', '-U', 'opengym_platform_bootstrap',
      '-d', 'opengym_capture', '-Atc', digestSQL])).trim(), expectedDigests);
    // A successful SQL capture is deliberately not a verified recovery point.
    assert.equal(journal.verified, false);
    console.log('ACTUAL_WRITER_SHUTDOWN_AND_SQL_CAPTURE_OK');
    await docker([...compose, 'stop', '--timeout', '30', 'api']);
    const stoppedResult = invoke();
    assert.equal(stoppedResult.status, 1, stoppedResult.stderr);
    assert.match(stoppedResult.stdout, /BACKUP_CAPTURED_UNVERIFIED/);
    const stoppedJournal = JSON.parse(readFileSync(join(state, 'journal.json')));
    assert.deepEqual(stoppedJournal.previously_running, []);
    assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
    console.log('INITIALLY_STOPPED_API_STAYS_STOPPED_OK');
    await docker([...compose, 'run', '--rm', '--no-deps', '--entrypoint', 'python', 'ops', '-c', `
import subprocess,sys,json
p=subprocess.run([sys.executable,'-m','opengym_platform.operations','capture-sql','--config','/run/operator/config.json'],capture_output=True)
assert p.returncode==1 and p.stderr==b''
assert json.loads(p.stdout)['code']=='BACKUP_CAPTURE_BLOCKED'
print('DIRECT_BACKUP_WITHOUT_ACTIVE_PROOF_REJECTED')`], true);
    const outsider = spawn('docker', [...compose, 'exec', '-T', 'db', 'psql', '-U', 'opengym_platform_bootstrap',
      '-d', 'opengym_dev', '-c', 'SELECT pg_sleep(30)'], { stdio: 'ignore' });
    try {
      for (let i = 0; i < 40; i++) {
        if ((await sql("SELECT count(*) FROM pg_stat_activity WHERE query='SELECT pg_sleep(30)' AND state='active'")).trim() === '1') break;
        await sleep(50);
      }
      const blocked = invoke();
      assert.equal(blocked.status, 1);
      assert.doesNotMatch(blocked.stdout, /BACKUP_CAPTURED_UNVERIFIED/);
      const failed = JSON.parse(readFileSync(join(state, 'journal.json')));
      assert.equal(failed.phase, 'capturing');
      assert.equal(failed.verified, false);
      assert.ok(existsSync(join(state, 'exclusive')));
      assert.equal(existsSync(join(state, failed.operation, 'database.dump')), false);
      assert.ok(readFileSync(dump).length > 1000, 'Prior capture was displaced');
      assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
      console.log('UNCOORDINATED_SQL_CLIENT_BLOCKS_CAPTURE_WITH_JOURNAL_RETAINED_OK');
    } finally { outsider.kill(); }
  } finally {
    await cleanup(project);
    rmSync(temporary, { recursive: true, force: true });
  }
});
