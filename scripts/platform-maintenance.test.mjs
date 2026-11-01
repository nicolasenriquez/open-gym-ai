import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, utimesSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { createHash, randomBytes } from 'node:crypto';
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
  for (const options of [[], ['--operation', '../other'], ['--operation', 'f'.repeat(32), '--force']]) {
    const misuse = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
      '--config', config, ...options], { encoding: 'utf8', timeout: 5000, env: { ...process.env, PATH: '' } });
    assert.equal(misuse.status, 2);
    assert.match(misuse.stderr, /MAINTENANCE_ARGUMENTS_INVALID/);
  }
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
  assert.equal(model.services.api.environment.PLATFORM_MAINTENANCE_GATE_DIR, '/run/maintenance-gate');
  assert.equal(model.services.api.environment.PLATFORM_INSTANCE_ID, instance);
  assert.ok(model.services.api.volumes.some(volume => volume.target === '/run/maintenance-gate'
    && volume.source === `${state}/gate` && volume.read_only && volume.bind.create_host_path === false));
  assert.ok(!model.services.db.ports?.length);
});

async function backupProof(fault) {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const temporary = mkdtempSync(join(tmpdir(), 'opengym-maintenance-'));
  const project = `opengym-platform-test-${randomBytes(8).toString('hex')}`;
  const image = `${project}-platform-test:local`;
  const foreign = `${project}-external`;
  const composeFile = join(temporary, 'compose.json');
  const envFile = join(temporary, 'empty.env');
  const state = join(temporary, 'state');
  const data = join(temporary, 'data');
  mkdirSync(state, { mode: 0o700 });
  const gate = join(state, 'gate');
  mkdirSync(gate, { mode: 0o700 });
  writeFileSync(join(gate, 'admission.json'), JSON.stringify({ instance_id: 'synthetic-a', operation: '0'.repeat(32), allowed: true }), { mode: 0o600 });
  mkdirSync(data, { mode: 0o700 });
  mkdirSync(join(data, 'uploads'), { mode: 0o700 });
  for (const owner of ['A', 'B']) mkdirSync(join(data, 'uploads', owner), { mode: 0o700 });
  const aHash = createHash('sha256').update('synthetic-owner-A-bytes').digest('hex');
  const bHash = createHash('sha256').update('synthetic-owner-B-bytes').digest('hex');
  const expectedFiles = {
    [`uploads/A/${aHash}.jpg`]: 'synthetic-owner-A-bytes',
    [`uploads/B/${bHash}.jpg`]: 'synthetic-owner-B-bytes',
    'uploads/A/.gc.json': JSON.stringify({ [aHash]: 123 }),
    'uploads/B/.gc.json': JSON.stringify({ [bHash]: 456 }),
    'coach-auth-A.json': '{"data":"synthetic-encrypted-record"}',
    'vapid.json': '{"publicKey":"synthetic-public","privateKey":"synthetic-private"}',
  };
  for (const [name, bytes] of Object.entries(expectedFiles)) writeFileSync(join(data, name), bytes, { mode: 0o600 });
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
    api: { ...python, environment: { ...environment, PLATFORM_DB_PASSWORD_FILE: '/run/secrets/runtime',
      PLATFORM_INSTANCE_ID: 'synthetic-a', PLATFORM_MAINTENANCE_GATE_DIR: '/run/maintenance-gate' },
      volumes: [...secrets.filter(item => /runtime|session/.test(item.target)), { type: 'bind', source: data, target: '/data' },
        { type: 'bind', source: gate, target: '/run/maintenance-gate', read_only: true }],
      command: [...(fault === 'recover' ? ['/app/tests/platform/api_start_probe.py'] : ['-m', 'uvicorn']), 'opengym_platform.application:create_app', '--factory', '--host', '0.0.0.0',
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
      + `INSERT INTO training.documents(owner_id,document) VALUES ('A','{"_rev":7,"_wid":"a","_prior":{"notes":null},"workouts":[{"media":[{"hash":"${aHash}"}]}]}'),`
      + `('B','{"_rev":11,"_wid":"b","notes":"synthetic B","workouts":[{"media":[{"hash":"${bHash}"}]}]}')`);
    const tables = (await sql("SELECT format('%I.%I',schemaname,tablename) FROM pg_tables WHERE schemaname IN "
      + "('public','identity','training','coach','administration','notifications','audit') ORDER BY 1")).trim().split(/\r?\n/);
    const digestSQL = tables.map((table, index) => `SELECT ${index} AS n,count(*)::text || ':' || coalesce(md5(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text),'empty') AS digest FROM ${table} t`).join(' UNION ALL ') + ' ORDER BY n';
    const expectedDigests = (await sql(digestSQL)).trim();
    await docker([...compose, 'up', '-d', '--no-deps', 'api']);
    await ready();
    if (fault === 'recover') {
      const initialAdmission = readFileSync(join(gate, 'admission.json'));
      await docker([...compose, 'stop', '--timeout', '30', 'api']);
      for (const invalid of [null, '{bad-json', JSON.stringify({ instance_id: 'foreign', operation: '0'.repeat(32), allowed: true })]) {
        if (invalid === null) rmSync(join(gate, 'admission.json'));
        else writeFileSync(join(gate, 'admission.json'), invalid);
        await docker([...compose, 'start', 'api']);
        for (let i = 0; i < 100; i++) {
          if (!JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running) break;
          await sleep(50);
        }
        const failed = JSON.parse(await docker(['inspect', `${project}-api-1`]))[0];
        assert.equal(failed.State.Running, false);
        assert.notEqual(failed.State.ExitCode, 0);
        assert.equal((await sql("SELECT count(*) FROM pg_stat_activity WHERE usename='opengym_runtime'")).trim(), '0');
      }
      writeFileSync(join(gate, 'admission.json'), initialAdmission);
      await docker([...compose, 'start', 'api']);
      await ready();
      console.log('MISSING_CORRUPT_FOREIGN_GATE_FAILS_CLOSED_BEFORE_DB_WRITERS_OK');
    }
    if (fault === 'runtime-secret') {
      const replacement = join(temporary, 'replacement-session');
      writeFileSync(replacement, 'synthetic-replacement-session-only-0123456789', { mode: 0o600 });
      const selection = JSON.parse(readFileSync(composeFile, 'utf8'));
      selection.services.api.volumes.find(item => item.target === '/run/secrets/session').source = replacement;
      writeFileSync(composeFile, JSON.stringify(selection));
    }
    if (fault === 'unsafe-link') {
      await docker([...compose, 'exec', '-T', 'api', 'python', '-c',
        "import os; os.symlink('/run/secrets/session', '/data/uploads/A/unsafe-link')"]);
    }
    // A separate project with no DB-network access can still write shared media.
    try {
      await docker(['run', '-d', '--name', `${foreign}-ops-1`, '--network', 'none',
        '--label', `com.docker.compose.project=${foreign}`, '--label', 'com.docker.compose.service=ops',
        '--label', 'org.opengym.platform=synthetic', '--read-only', '--cap-drop=ALL', '--user', user,
        '--volume', `${data}:/shared`, '--entrypoint', 'python', image, '-c', 'import time;time.sleep(90)']);
      const blocked = invoke();
      assert.equal(blocked.status, 1);
      assert.match(blocked.stderr, /MAINTENANCE_EXTERNAL_FILE_WRITER/);
      assert.doesNotMatch(blocked.stdout, /BACKUP_CAPTURED_UNVERIFIED/);
      assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, true);
      assert.equal(existsSync(join(state, 'exclusive')), false);
      console.log('EXTERNAL_SHARED_MEDIA_WRITER_BLOCKS_BEFORE_SHUTDOWN_OK');
    } finally { await cleanup(foreign); }
    if (fault === 'media-change') writeFileSync(join(state, 'pause-after-dump'), '');
    const first = spawn(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
      '--config', config, '--reason', 'scheduled'], { stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    first.stdout.on('data', chunk => { stdout += chunk; });
    first.stderr.on('data', chunk => { stderr += chunk; });
    const finished = new Promise(resolve => first.on('close', status => resolve({ status, stdout, stderr })));
    if (fault === 'recover') {
      let resuming;
      try {
        for (let i = 0; i < 300; i++) {
          if (existsSync(join(state, 'journal.json'))
            && JSON.parse(readFileSync(join(state, 'journal.json'))).phase === 'capturing') break;
          if (first.exitCode !== null) break;
          await sleep(50);
        }
        const interrupted = JSON.parse(readFileSync(join(state, 'journal.json')));
        assert.equal(interrupted.phase, 'capturing');
        for (let i = 0; i < 100; i++) {
          if ((await docker(['ps', '-q', '--filter', `name=^/${interrupted.capture_container}$`])).trim()) break;
          await sleep(50);
        }
        assert.equal(JSON.parse(await docker(['inspect', interrupted.capture_container]))[0].State.Running, true);
        utimesSync(join(state, 'journal.json'), new Date(0), new Date(0));
        const active = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
          '--config', config, '--operation', interrupted.operation], { encoding: 'utf8', timeout: 15_000 });
        assert.equal(active.status, 1);
        assert.match(active.stderr, /MAINTENANCE_CONTROLLER_ACTIVE/);
        assert.equal(JSON.parse(await docker(['inspect', interrupted.capture_container]))[0].State.Running, true);
        console.log('LIVE_CONTROLLER_CANNOT_BE_TAKEN_OVER_OK');
        first.kill('SIGKILL');
        await new Promise(resolve => first.exitCode !== null || first.signalCode !== null ? resolve() : first.once('exit', resolve));
        await docker([...compose, 'start', 'api']);
        for (let i = 0; i < 100; i++) {
          if (!JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running) break;
          await sleep(50);
        }
        const gated = JSON.parse(await docker(['inspect', `${project}-api-1`]))[0];
        assert.equal(gated.State.Running, false, 'A new API process must not start writers while capture is unresolved');
        assert.notEqual(gated.State.ExitCode, 0);
        console.log('PERSISTED_GATE_BLOCKS_NEW_API_PROCESS_BEFORE_WRITERS_OK');
        const recover = () => spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
          '--config', config, '--operation', interrupted.operation], { encoding: 'utf8', timeout: 90_000 });
        await docker(['run', '-d', '--name', `${foreign}-ops-1`, '--network', 'none',
          '--label', `com.docker.compose.project=${foreign}`, '--label', 'com.docker.compose.service=ops',
          '--label', 'org.opengym.platform=synthetic', '--read-only', '--cap-drop=ALL', '--user', user,
          '--entrypoint', 'python', image, '-c', 'import time;time.sleep(300)']);
        const originalJournal = readFileSync(join(state, 'journal.json'), 'utf8');
        const wrong = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
          '--config', config, '--operation', 'f'.repeat(32)], { encoding: 'utf8', timeout: 15_000 });
        assert.equal(wrong.status, 1);
        assert.equal(readFileSync(join(state, 'journal.json'), 'utf8'), originalJournal);
        // Filesystem fault at persisted command intent, before PID recording.
        writeFileSync(join(state, 'journal.json'), JSON.stringify({ ...JSON.parse(originalJournal), client: 'pending' }));
        const uncertain = recover();
        assert.equal(uncertain.status, 1);
        assert.match(uncertain.stderr, /MAINTENANCE_PROCESS_UNPROVEN/);
        assert.ok(existsSync(join(state, 'exclusive')));
        assert.equal(JSON.parse(readFileSync(join(gate, 'admission.json'))).allowed, false);
        writeFileSync(join(state, 'journal.json'), originalJournal);
        console.log('UNRECORDED_PROCESS_INTENT_STAYS_BLOCKED_FOR_FORENSIC_REVIEW_OK');
        await sql("UPDATE public.alembic_version SET version_num='future_schema'");
        const incompatible = recover();
        assert.equal(incompatible.status, 1);
        assert.ok(existsSync(join(state, 'exclusive')));
        assert.equal(JSON.parse(readFileSync(join(gate, 'admission.json'))).allowed, false);
        assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
        await sql("UPDATE public.alembic_version SET version_num='p004_audit'");
        console.log('UNKNOWN_SCHEMA_BLOCKS_RECOVERY_WITHOUT_WRITES_OR_OPENING_OK');
        writeFileSync(join(gate, 'fail-start'), '');
        const failedStart = recover();
        assert.equal(failedStart.status, 1, 'Recovery must not report success when the admitted API exits during startup');
        assert.ok(existsSync(join(state, 'exclusive')));
        assert.equal(JSON.parse(readFileSync(join(gate, 'admission.json'))).allowed, false);
        rmSync(join(gate, 'fail-start'));
        console.log('FAILED_RESTART_REBLOCKS_GATE_AND_RETAINS_RECOVERABLE_JOURNAL_OK');
        writeFileSync(join(state, 'pause-check'), '');
        resuming = spawn(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
          '--config', config, '--operation', interrupted.operation], { stdio: 'ignore' });
        for (let i = 0; i < 300; i++) {
          if (existsSync(join(state, 'check-paused'))) break;
          if (resuming.exitCode !== null) break;
          await sleep(50);
        }
        assert.ok(existsSync(join(state, 'check-paused')), 'Recovery must reach the real compatibility command');
        const competing = recover();
        assert.equal(competing.status, 1);
        assert.match(competing.stderr, /MAINTENANCE_CONTROLLER_ACTIVE|MAINTENANCE_LOCKED/);
        resuming.kill('SIGKILL');
        await new Promise(resolve => resuming.exitCode !== null || resuming.signalCode !== null ? resolve() : resuming.once('exit', resolve));
        rmSync(join(state, 'pause-check'));
        const recovered = recover();
        assert.equal(recovered.status, 0, `Explicit recovery must succeed after wrapper death: ${recovered.stderr}`);
        assert.match(recovered.stdout, /MAINTENANCE_RECOVERED/);
        assert.equal(JSON.parse(await docker(['inspect', interrupted.capture_container]))[0].State.Running, false);
        await ready();
        assert.equal(existsSync(join(state, 'exclusive')), false);
        assert.equal(JSON.parse(readFileSync(join(state, 'journal.json'))).verified, false);
        assert.equal(JSON.parse(await docker(['inspect', `${foreign}-ops-1`]))[0].State.Running, true, 'Unrelated sentinel must survive recovery');
        console.log('INTERRUPTED_CAPTURE_AND_RECOVERY_RECOVER_ONLY_OWNED_RUNNING_SERVICES_OK');
        assert.equal(JSON.parse(readFileSync(join(state, 'journal.json'))).operation, interrupted.operation, 'Recovery must not recursively launch a startup backup');
        assert.equal((await sql("SELECT string_agg(id,',' ORDER BY id) FROM identity.users")).trim(), 'A,B');
        await docker([...compose, 'stop', '--timeout', '30', 'api']);
        resuming = spawn(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
          '--config', config, '--reason', 'startup'], { stdio: 'ignore' });
        let stopped;
        for (let i = 0; i < 300; i++) {
          stopped = JSON.parse(readFileSync(join(state, 'journal.json')));
          if (stopped.phase === 'capturing' && stopped.operation !== interrupted.operation
            && (await docker(['ps', '-q', '--filter', `name=^/${stopped.capture_container}$`])).trim()) break;
          await sleep(50);
        }
        assert.equal(stopped.phase, 'capturing');
        assert.deepEqual(stopped.previously_running, []);
        resuming.kill('SIGKILL');
        await new Promise(resolve => resuming.exitCode !== null || resuming.signalCode !== null ? resolve() : resuming.once('exit', resolve));
        const stoppedRecovery = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
          '--config', config, '--operation', stopped.operation], { encoding: 'utf8', timeout: 90_000 });
        assert.equal(stoppedRecovery.status, 0, stoppedRecovery.stderr);
        assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
        assert.equal(JSON.parse(readFileSync(join(state, 'journal.json'))).operation, stopped.operation);
        console.log('STARTUP_RECOVERY_PRESERVES_STOPPED_API_WITHOUT_RECURSIVE_BACKUP_OK');
        writeFileSync(join(state, 'allow-capture'), '');
        const preMigration = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'backup',
          '--config', config, '--reason', 'pre-migration'], { encoding: 'utf8', timeout: 180_000 });
        assert.equal(preMigration.status, 1);
        assert.match(preMigration.stderr, /MAINTENANCE_MIGRATION_NOT_IMPLEMENTED/);
        const migration = JSON.parse(readFileSync(join(state, 'journal.json')));
        const held = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'maintenance-recover',
          '--config', config, '--operation', migration.operation], { encoding: 'utf8', timeout: 90_000 });
        assert.equal(held.status, 1);
        assert.match(held.stderr, /MAINTENANCE_MIGRATION_HELD/);
        assert.ok(existsSync(join(state, 'exclusive')));
        assert.equal(JSON.parse(readFileSync(join(gate, 'admission.json'))).allowed, false);
        assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
        assert.equal(JSON.parse(readFileSync(join(state, 'journal.json'))).phase, 'migration_held');
        assert.equal((await sql('SELECT version_num FROM public.alembic_version')).trim(), 'p004_audit');
        console.log('PRE_MIGRATION_RECOVERY_NEVER_RESTARTS_OR_RUNS_DDL_OK');
      } finally {
        resuming?.kill('SIGKILL');
        rmSync(join(state, 'pause-check'), { force: true });
        first.kill('SIGKILL');
        writeFileSync(join(state, 'allow-capture'), '');
        await finished;
      }
      return;
    }
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
      if (fault === 'host-change') writeFileSync(envFile, '# changed during pause\n');
      if (fault === 'late-writer') {
        await docker(['run', '-d', '--name', `${foreign}-ops-1`, '--network', 'none',
          '--label', `com.docker.compose.project=${foreign}`, '--label', 'com.docker.compose.service=ops',
          '--label', 'org.opengym.platform=synthetic', '--read-only', '--cap-drop=ALL', '--user', user,
          '--volume', `${data}:/shared`, '--entrypoint', 'python', image, '-c', 'import time;time.sleep(90)']);
      }
      writeFileSync(join(state, 'allow-capture'), '');
      if (fault === 'media-change') {
        try {
          for (let i = 0; i < 300; i++) {
            if (existsSync(join(state, 'dump-complete'))) break;
            if (first.exitCode !== null) break;
            await sleep(50);
          }
          assert.ok(existsSync(join(state, 'dump-complete')), 'Actual dump must finish before media mutation');
          writeFileSync(join(data, 'uploads', 'A', `${aHash}.jpg`), 'changed after SQL snapshot');
        } finally { writeFileSync(join(state, 'allow-dump'), ''); }
      }
    }
    const result = await finished;
    assert.equal(result.status, 1, result.stderr);
    if (fault) {
      assert.doesNotMatch(result.stdout, /BACKUP_CAPTURED_UNVERIFIED/);
      assert.ok(existsSync(join(state, 'exclusive')));
      const failed = JSON.parse(readFileSync(join(state, 'journal.json')));
      assert.equal(failed.phase, 'capturing');
      assert.equal(existsSync(join(state, failed.operation, 'capture.json')), fault === 'late-writer');
      assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
      if (fault === 'late-writer') assert.match(result.stderr, /MAINTENANCE_EXTERNAL_FILE_WRITER/);
      console.log(fault === 'late-writer' ? 'LATE_FILE_WRITER_BLOCKS_RESTART_WITH_JOURNAL_RETAINED_OK'
        : fault === 'unsafe-link' ? 'UNSAFE_SOURCE_LINK_BLOCKS_CAPTURE_WITH_JOURNAL_RETAINED_OK'
          : fault === 'media-change' ? 'MEDIA_CHANGED_AFTER_SQL_BLOCKS_CAPTURE_WITH_JOURNAL_RETAINED_OK'
            : fault === 'runtime-secret' ? 'RUNTIME_SECRET_SELECTION_MISMATCH_BLOCKS_CAPTURE_OK'
              : 'HOST_CONFIG_CHANGE_BLOCKS_CAPTURE_WITH_JOURNAL_RETAINED_OK');
      return;
    }
    assert.match(result.stdout, /BACKUP_CAPTURED_UNVERIFIED/, result.stderr);
    const journal = JSON.parse(readFileSync(join(state, 'journal.json')));
    assert.equal(journal.phase, 'captured_unverified');
    assert.deepEqual(journal.previously_running, ['api']);
    assert.ok(journal.pause_ms > 0 && journal.pause_ms < 120_000);
    console.log(`SQL_CAPTURE_PAUSE_MS=${journal.pause_ms}`);
    const dump = join(state, journal.operation, 'database.dump');
    assert.ok(readFileSync(dump).length > 1000);
    const captured = join(state, journal.operation);
    for (const [name, bytes] of Object.entries(expectedFiles)) {
      assert.equal(readFileSync(join(captured, 'data', name), 'utf8'), bytes, 'Recovery set must include exact data/GC/secret bytes');
    }
    const manifest = JSON.parse(readFileSync(join(captured, 'capture.json')));
    assert.equal(manifest.snapshot_at, journal.snapshot_at);
    assert.equal(manifest.verified, false);
    assert.ok(manifest.files.some(file => file.path === 'database.dump' && /^[a-f0-9]{64}$/.test(file.sha256)));
    for (const file of manifest.files.filter(file => !file.directory)) {
      const bytes = readFileSync(join(captured, file.path));
      assert.equal(bytes.length, file.size);
      assert.equal(createHash('sha256').update(bytes).digest('hex'), file.sha256);
    }
    assert.equal(readFileSync(join(captured, 'runtime-secrets/session'), 'utf8'), 'synthetic-maintenance-session-only-0123456789');
    assert.equal(readFileSync(join(captured, 'configuration/0'), 'utf8'), readFileSync(config, 'utf8'));
    const selectionSource = manifest.sources.find(source => source.origin.endsWith('.selection.json'));
    const selection = JSON.parse(readFileSync(join(captured, selectionSource.target), 'utf8'));
    assert.equal(selection.compose.services.api.environment.PLATFORM_DB_NAME, 'opengym_dev');
    assert.match(selection.api.image, /^sha256:[a-f0-9]{64}$/);
    assert.doesNotMatch(result.stdout + result.stderr, /synthetic-maintenance-session|synthetic-private|synthetic-encrypted-record/);
    console.log('INDEPENDENT_SQL_FILES_COHERENCE_OK');
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
    assert.equal((await docker([...compose, 'exec', '-T', 'db', 'psql', '-U', 'opengym_platform_bootstrap',
      '-d', 'opengym_capture', '-Atc', "SELECT owner_id,document#>>'{workouts,0,media,0,hash}' FROM training.documents ORDER BY owner_id"]))
      .trim().replaceAll('\r', ''), `A|${aHash}\nB|${bHash}`);
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
    await cleanup(foreign);
    await cleanup(project);
    rmSync(temporary, { recursive: true, force: true });
  }
}

test('host backup stops actual writers, leaves PostgreSQL available and captures all owners', () => backupProof());
test('host file mutation during the pause blocks the recovery set and retains the journal', () => backupProof('host-change'));
test('an external writer appearing during capture blocks restart and retains the journal', () => backupProof('late-writer'));
test('a source symlink blocks capture without following it into runtime secrets', () => backupProof('unsafe-link'));
test('media changed after the SQL snapshot cannot become a coherent recovery set', () => backupProof('media-change'));
test('selected secrets differing from the actual runtime cannot form a coherent recovery set', () => backupProof('runtime-secret'));
test('interrupted capture recovers owned services only after capture termination and compatibility', () => backupProof('recover'));
