import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { syntheticHarness } from './synthetic-harness.mjs';

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'opengym-schedule-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  if (process.platform === 'win32') {
    const acl = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      "$ErrorActionPreference='Stop'; $a=Get-Acl -LiteralPath $env:OPENGYM_TEST_DIRECTORY; $a.SetAccessRuleProtection($true,$false); $u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User; $a.SetOwner($u); $r=New-Object System.Security.AccessControl.FileSystemAccessRule($u,'FullControl','ContainerInherit,ObjectInherit','None','Allow'); $a.AddAccessRule($r); Set-Acl -LiteralPath $env:OPENGYM_TEST_DIRECTORY -AclObject $a"],
    { env: { ...process.env, OPENGYM_TEST_DIRECTORY: root }, encoding: 'utf8' });
    assert.equal(acl.status, 0, acl.stderr);
  }
  for (const dir of ['state', 'state/gate', 'destination']) mkdirSync(join(root, dir), { mode: 0o700 });
  const config = join(root, 'operator.json');
  writeFileSync(join(root, 'identity'), 'private-fixture', { mode: 0o600 });
  writeFileSync(config, JSON.stringify({ instance_id: 'synthetic-a', project: 'synthetic-a', project_directory: root,
    state_root: join(root, 'state'), env_file: config, compose_files: [config], writers: ['api'],
    bundle: { destination: join(root, 'destination'), identity_file: join(root, 'identity'), recipient: 'age1' + 'q'.repeat(58) } }), { mode: 0o600 });
  writeFileSync(join(root, 'state/gate/admission.json'), JSON.stringify({ instance_id: 'synthetic-a', operation: 'b'.repeat(32), allowed: true }));
  const receipt = { version: 1, verified: true, instance_id: 'synthetic-a', operation: 'a'.repeat(32),
    snapshot_at: new Date(Date.now() - 3600_000).toISOString(), verified_at: new Date(Date.now() - 1800_000).toISOString(),
    ciphertext: { path: 'a'.repeat(32) + '.age', size: 100, sha256: 'c'.repeat(64) } };
  const receiptPath = join(root, 'state/gate/backup.json');
  writeFileSync(receiptPath, JSON.stringify(receipt));
  const invoke = (reason = 'startup') => spawnSync(process.execPath,
    ['scripts/platform.mjs', 'operate', 'backup', '--config', config, '--reason', reason],
    { encoding: 'utf8', timeout: 15_000, env: { ...process.env,
      DOCKER_HOST: process.platform === 'win32' ? 'npipe:////./pipe/opengym-platform-missing' : 'unix:///opengym-platform-missing.sock',
      DOCKER_CONTEXT: '', DOCKER_TLS_VERIFY: '', DOCKER_CERT_PATH: '' } });
  return { root, config, receipt, receiptPath, invoke };
}

test('startup with a current verified snapshot skips capture without Docker or changing evidence', t => {
  const { root, receiptPath, invoke } = fixture(t);
  const before = readFileSync(receiptPath);
  const result = invoke();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).code, 'BACKUP_NOT_DUE');
  if (process.platform === 'win32') {
    const xml = readFileSync('deploy/scheduling/windows-startup.xml', 'utf8')
      .replace('C:\\ABS\\node.exe', process.execPath)
      .replaceAll('C:\\ABS\\REPO', process.cwd())
      .replace('C:\\PRIVATE\\backup.json', join(root, 'operator.json'));
    const task = join(root, 'startup.xml');
    writeFileSync(task, xml);
    const started = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      "$ErrorActionPreference='Stop'; [xml]$x=Get-Content -Raw -LiteralPath $env:OPENGYM_TEMPLATE; $p=Start-Process -FilePath $x.Task.Actions.Exec.Command -ArgumentList $x.Task.Actions.Exec.Arguments -WorkingDirectory $x.Task.Actions.Exec.WorkingDirectory -NoNewWindow -Wait -PassThru; exit $p.ExitCode"],
    { env: { ...process.env, OPENGYM_TEMPLATE: task }, encoding: 'utf8', timeout: 15_000 });
    assert.equal(started.status, 0, started.stderr);
    assert.match(started.stdout, /BACKUP_NOT_DUE/);
  }
  assert.deepEqual(readFileSync(receiptPath), before);
  assert.throws(() => readFileSync(join(root, 'state/journal.json')), { code: 'ENOENT' });
});

test('startup accepts the actual Python UTC receipt format with microseconds and offset', t => {
  const { receipt, receiptPath, invoke } = fixture(t);
  writeFileSync(receiptPath, JSON.stringify({ ...receipt,
    snapshot_at: receipt.snapshot_at.replace('Z', '123+00:00'), verified_at: receipt.verified_at.replace('Z', '123+00:00') }));
  const result = invoke();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).code, 'BACKUP_NOT_DUE');
});

test('startup never skips overdue, invalid or foreign evidence, or scheduled/pre-migration capture', t => {
  const { root, receipt, receiptPath, invoke } = fixture(t);
  for (const patch of [
    { snapshot_at: new Date(Date.now() - 10800_000).toISOString() },
    { snapshot_at: new Date(Date.now() - 21601_000).toISOString() },
    { verified: false }, { version: 2 }, { instance_id: 'foreign' },
    { verified_at: new Date(Date.now() + 3600_000).toISOString() },
    { snapshot_at: 'invalid' }, { snapshot_at: '2026-02-30T10:00:00Z' },
    { ciphertext: { ...receipt.ciphertext, size: 0 } },
  ]) {
    writeFileSync(receiptPath, JSON.stringify({ ...receipt, ...patch }));
    const result = invoke();
    assert.equal(result.status, 1);
    assert.doesNotMatch(result.stdout, /BACKUP_NOT_DUE/);
  }
  writeFileSync(receiptPath, JSON.stringify(receipt));
  for (const reason of ['scheduled', 'pre-migration']) {
    const result = invoke(reason);
    assert.equal(result.status, 1);
    assert.doesNotMatch(result.stdout, /BACKUP_NOT_DUE/);
  }
  if (process.platform === 'win32') {
    const manual = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-File',
      'deploy/scheduling/windows-pre-migration.ps1', '-Node', process.execPath,
      '-Repository', process.cwd(), '-Config', join(root, 'operator.json')],
    { encoding: 'utf8', timeout: 15_000, env: { ...process.env,
      DOCKER_HOST: 'npipe:////./pipe/opengym-platform-missing', DOCKER_CONTEXT: '' } });
    assert.equal(manual.status, 1);
    assert.match(manual.stderr, /MAINTENANCE_DOCKER_FAILED/);
    assert.doesNotMatch(manual.stdout, /BACKUP_NOT_DUE/);
  }
  writeFileSync(join(root, 'state/gate/admission.json'), JSON.stringify({ instance_id: 'synthetic-a', operation: 'b'.repeat(32), allowed: false }));
  assert.equal(invoke().status, 1);
  writeFileSync(join(root, 'state/gate/admission.json'), JSON.stringify({ instance_id: 'synthetic-a', operation: 'b'.repeat(32), allowed: true }));
  rmSync(receiptPath);
  assert.equal(invoke().status, 1);
  writeFileSync(receiptPath, '{');
  assert.equal(invoke().status, 1);
  writeFileSync(receiptPath, JSON.stringify(receipt));
  writeFileSync(join(root, 'state/journal.json'), JSON.stringify({ instance_id: 'synthetic-a', project: 'synthetic-a', phase: 'stopping' }));
  assert.match(invoke().stderr, /MAINTENANCE_UNRESOLVED_JOURNAL/);
  rmSync(join(root, 'state/journal.json'));
  mkdirSync(join(root, 'state/exclusive'));
  const started = Date.now(), locked = invoke();
  assert.equal(locked.status, 1);
  assert.match(locked.stderr, /MAINTENANCE_LOCKED/);
  assert.ok(Date.now() - started < 5000);
});

test('diagnostic retention has a public bounded command and fails closed without a collector', t => {
  const { config } = fixture(t);
  const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'diagnostics-retain', '--config', config],
    { encoding: 'utf8', timeout: 10_000, env: { ...process.env,
      DOCKER_HOST: process.platform === 'win32' ? 'npipe:////./pipe/opengym-platform-missing' : 'unix:///opengym-platform-missing.sock', DOCKER_CONTEXT: '' } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /MAINTENANCE_DOCKER_FAILED/);
});

test('hourly retention uses only the owned live collector, preserves foreign files and fails when stopped', async t => {
  const { root, config } = fixture(t);
  const project = `opengym-platform-test-${randomBytes(8).toString('hex')}`;
  const { docker, cleanup } = syntheticHarness({ root: fileURLToPath(new URL('../', import.meta.url)),
    namespace: 'opengym-platform-test', label: 'org.opengym.platform', name: 'Platform',
    services: ['diagnostics'], images: ['diagnostics'],
    extraVolumes: { 'diagnostic-logs': { name: 'diagnostic-logs', service: 'diagnostics' } } });
  const image = `${project}-diagnostics:local`, volume = `${project}_diagnostic-logs`, container = `${project}-diagnostics-1`;
  const labels = ['--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.platform=synthetic', '--label', 'com.docker.compose.service=diagnostics'];
  try {
    await docker(['build', ...labels, '-t', image, '-f', 'backend/diagnostics/Dockerfile', 'backend/diagnostics'], true);
    const pin = JSON.parse(await docker(['image', 'inspect', image]))[0].Id;
    await docker(['volume', 'create', ...labels, '--label', 'com.docker.compose.volume=diagnostic-logs', volume]);
    await docker(['run', '-d', '--name', container, ...labels, '--label', 'com.docker.compose.oneoff=False',
      '--label', 'com.docker.compose.container-number=1', '--label', 'com.docker.compose.config-hash=synthetic', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
      '--security-opt', 'no-new-privileges', '--log-driver', 'none', '--tmpfs', '/state:rw,noexec,uid=1000,gid=1000,mode=0700,size=1048576',
      '--mount', `type=volume,source=${volume},target=/logs`, '--tmpfs', '/run/diagnostics:rw,noexec,uid=1000,gid=1000,mode=0711', pin]);
    const compose = join(root, 'compose.json');
    writeFileSync(compose, JSON.stringify({ services: { diagnostics: { image: pin, volumes: ['diagnostic-logs:/logs'] } },
      volumes: { 'diagnostic-logs': { name: volume, external: true } } }));
    const selected = JSON.parse(readFileSync(config));
    writeFileSync(config, JSON.stringify({ ...selected, project, compose_files: [compose], env_file: join(root, 'empty.env') }));
    writeFileSync(join(root, 'empty.env'), '');
    // Log retention must not depend on a removable backup disk or decryption key.
    rmSync(join(root, 'identity'));
    rmSync(join(root, 'destination'), { recursive: true });
    await docker(['exec', container, 'python', '-c', `import pathlib,time,os
for _ in range(100):
 if pathlib.Path('/state/ready').exists():break
 time.sleep(.05)
else:raise AssertionError('collector unavailable')
for name in ('api.log','api.log.1','api.log.foreign-sentinel'):
 p=pathlib.Path('/logs')/name;p.write_text('expired-marker');os.utime(p,(time.time()-8*86400,)*2)`]);
    const invoke = () => spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'diagnostics-retain', '--config', config],
      { encoding: 'utf8', timeout: 90_000 });
    const result = invoke();
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).code, 'DIAGNOSTICS_RETAINED');
    await docker(['exec', container, 'python', '-c', "from pathlib import Path;assert not any(b'expired-marker' in p.read_bytes() for p in Path('/logs').glob('api.log*') if p.name!='api.log.foreign-sentinel');assert Path('/logs/api.log.foreign-sentinel').read_text()=='expired-marker'"]);
    // Wrong volume selection must not execute retention against the actual collector.
    const model = JSON.parse(readFileSync(compose));
    model.volumes['diagnostic-logs'].name = `${project}_foreign`;
    writeFileSync(compose, JSON.stringify(model));
    const foreign = invoke();
    assert.equal(foreign.status, 1);
    assert.match(foreign.stderr, /MAINTENANCE_DIAGNOSTICS_UNAVAILABLE/);
    model.volumes['diagnostic-logs'].name = volume;
    writeFileSync(compose, JSON.stringify(model));
    await docker(['stop', '--time', '5', container]);
    const stopped = invoke();
    assert.equal(stopped.status, 1);
    assert.match(stopped.stderr, /MAINTENANCE_DIAGNOSTICS_UNAVAILABLE/);
    assert.equal(JSON.parse(await docker(['inspect', container]))[0].State.Running, false);
  } finally { await cleanup(project); }
});

test('delivered scheduler templates expose fixed frequencies and explicit public commands without installation', () => {
  const cron = readFileSync('deploy/scheduling/opengym.cron', 'utf8');
  assert.match(cron, /^0 \*\/3 \* \* \* .*--reason scheduled$/m);
  assert.match(cron, /^@reboot .*--reason startup$/m);
  assert.match(cron, /^0 2 1 \* \* .*operate restore-rehearse --config /m);
  assert.match(cron, /^0 \* \* \* \* .*operate diagnostics-retain --config /m);
  assert.match(cron, /^# .*--reason pre-migration$/m);
  const manual = readFileSync('deploy/scheduling/windows-pre-migration.ps1', 'utf8');
  assert.match(manual, /operate backup --config \$Config --reason pre-migration/);
  assert.match(manual, /exit \$LASTEXITCODE/);
  for (const [name, frequency, command] of [
    ['backup', '<Interval>PT3H</Interval>', 'backup'], ['startup', '<BootTrigger>', 'backup'],
    ['restore', '<ScheduleByMonth>', 'restore-rehearse'], ['retain', '<Interval>PT1H</Interval>', 'diagnostics-retain'],
  ]) {
    const xml = readFileSync(`deploy/scheduling/windows-${name}.xml`, 'utf8');
    assert.ok(xml.includes(frequency));
    assert.ok(xml.includes(`operate ${command} --config`));
    assert.ok(xml.includes('<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>'));
    assert.ok(xml.includes('<StartWhenAvailable>true</StartWhenAvailable>'));
    assert.doesNotMatch(xml, /Register-ScheduledTask|schtasks|ExecutionPolicy|EncodedCommand/);
    if (process.platform === 'win32') {
      const parsed = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
        "$ErrorActionPreference='Stop'; [xml]$x=Get-Content -Raw -LiteralPath $env:OPENGYM_TEMPLATE; if($x.Task.Actions.Exec.Command -ne 'C:\\ABS\\node.exe'){exit 1}"],
      { env: { ...process.env, OPENGYM_TEMPLATE: join(process.cwd(), `deploy/scheduling/windows-${name}.xml`) }, encoding: 'utf8' });
      assert.equal(parsed.status, 0, parsed.stderr);
    }
  }
});
