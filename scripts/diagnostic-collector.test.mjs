import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { syntheticHarness } from './synthetic-harness.mjs';

test('private collector: Docker native transport, Unix API, quota, age and stopped sink', async () => {
  const project = `opengym-platform-test-${randomBytes(8).toString('hex')}`;
  const { docker, cleanup } = syntheticHarness({
    root: fileURLToPath(new URL('../', import.meta.url)), namespace: 'opengym-platform-test',
    label: 'org.opengym.platform', name: 'Platform', services: ['diagnostics'], images: ['diagnostics'],
    networkNames: ['private'], extraVolumes: { 'diagnostic-logs': { name: 'diagnostic-logs', service: 'diagnostics' } },
  });
  const image = `${project}-diagnostics:local`, container = `${project}-diagnostics-1`;
  const labels = ['--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.platform=synthetic'];
  try {
    await docker(['build', ...labels, '--label', 'com.docker.compose.service=diagnostics', '-t', image,
      '-f', 'backend/diagnostics/Dockerfile', 'backend/diagnostics'], true);
    await docker(['network', 'create', '--internal', ...labels, '--label', 'com.docker.compose.service=private',
      '--label', 'com.docker.compose.network=private', `${project}_private`]);
    const volume = `${project}_diagnostic-logs`;
    await docker(['volume', 'create', ...labels, '--label', 'com.docker.compose.service=diagnostics',
      '--label', 'com.docker.compose.volume=diagnostic-logs', volume]);
    await docker(['run', '-d', '--name', container, ...labels, '--label', 'com.docker.compose.service=diagnostics',
      '--network', `${project}_private`, '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
      '--log-driver', 'none', '--tmpfs', '/state:rw,noexec,uid=1000,gid=1000,mode=0700,size=1048576',
      '--mount', `type=volume,source=${volume},target=/logs`,
      '--tmpfs', '/run/diagnostics:rw,noexec,uid=1000,gid=1000,mode=0711', image]);
    await docker(['exec', container, 'python', '-c', `import pathlib,time
for _ in range(100):
 if pathlib.Path('/run/diagnostics/log').is_socket(): break
 time.sleep(.05)
else: raise AssertionError('socket not ready')`]);
    const meta = JSON.parse(await docker(['inspect', container]))[0];
    const ip = meta.NetworkSettings.Networks[`${project}_private`].IPAddress;
    assert.deepEqual(meta.HostConfig.PortBindings, {});
    for (const source of ['nginx', 'postgres']) {
      await docker(['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--log-driver', 'syslog', '--log-opt', `syslog-address=udp://${ip}:5514`,
        '--log-opt', `tag=opengym-${source}`, '--log-opt', 'mode=non-blocking', '--log-opt', 'max-buffer-size=1m',
        '--log-opt', 'cache-disabled=true', '--entrypoint', 'python', image, '-c', 'print("private-native-marker",flush=True)']);
    }
    await docker(['exec', container, 'python', '-c', `import socket,time,pathlib,json
s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);s.connect('/run/diagnostics/log')
s.send(b'<14>opengym-api: {"service":"api","request_id":"00112233445566778899aabbccddeeff","result":200}')
u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
u.sendto(b'<14>opengym-api: private-forged-marker',('127.0.0.1',5514))
for _ in range(100):
 if all(pathlib.Path('/logs/'+n+'.log').exists() for n in ('api','nginx','postgres','ops')): break
 time.sleep(.05)
else: raise AssertionError('missing source')
for p in pathlib.Path('/logs').glob('*.log'):
 data=p.read_text();assert 'private-' not in data
 assert p.stat().st_mode & 0o777 == 0o600
assert '"service":"api"' in pathlib.Path('/logs/api.log').read_text()
assert '"service":"nginx"' in pathlib.Path('/logs/nginx.log').read_text()
assert '"service":"postgres"' in pathlib.Path('/logs/postgres.log').read_text()
print('NATIVE_AND_UNIX_PRIVACY_OK')`], true);
    await docker(['exec', container, 'rotate']);
    const correlated = await docker(['exec', container, 'grep', '-hF',
      '00112233445566778899aabbccddeeff', '/logs/api.log.1']);
    assert.equal(JSON.parse(correlated.trim()).request_id, '00112233445566778899aabbccddeeff');
    console.log('PRIVATE_CORRELATION_LOOKUP_AFTER_ROTATION_OK');
    await docker(['exec', container, 'python', '-c', `import pathlib,subprocess,os,time
root=pathlib.Path('/logs')
for name in ('api','nginx','postgres','ops'):
 for i in range(169):
  p=root/(name+'.log'+('.'+str(i) if i else ''));p.write_bytes(b'x'*(352*1024))
subprocess.run(['/usr/local/bin/rotate'],check=True,timeout=10)
assert sum(p.stat().st_size for p in root.iterdir()) < 256*1024*1024
workers=[subprocess.Popen(['/usr/local/bin/rotate'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) for _ in range(32)]
codes=[p.wait(timeout=10) for p in workers]
assert 0 in codes and set(codes)<={0,3}
assert sum(p.stat().st_size for p in root.iterdir()) < 256*1024*1024
assert sum(p.stat().st_blocks*512 for p in root.iterdir()) < 256*1024*1024
for name in ('api','nginx','postgres','ops'):
 for suffix in ('','.1'):
  p=root/(name+'.log'+suffix);p.write_text('expired-marker');os.utime(p,(time.time()-8*86400,)*2)
subprocess.run(['/usr/local/bin/rotate'],check=True,timeout=10)
assert not any(b'expired-marker' in p.read_bytes() for p in root.iterdir())
foreign=root/'api.log.foreign-sentinel';foreign.write_text('foreign-sentinel')
os.utime(foreign,(time.time()-8*86400,)*2)
subprocess.run(['/usr/local/bin/rotate'],check=True,timeout=10)
assert foreign.read_text()=='foreign-sentinel'
print('ALL_SOURCE_QUOTA_AND_AGE_OK')`], true);
    await docker(['exec', container, 'python', '-c', `import socket,pathlib,time,json
s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);s.connect('/run/diagnostics/log');s.setblocking(False)
packet=('<14>opengym-api: '+json.dumps({'service':'api','operation':'bounded-ingress','result':200,'padding':'x'*4000})).encode()
sent=0
for _ in range(1500):
 try:s.send(packet);sent+=1
 except BlockingIOError:time.sleep(.001)
assert sent>100
time.sleep(1)
assert sum(p.stat().st_size for p in pathlib.Path('/logs').iterdir()) < 256*1024*1024
assert pathlib.Path('/state/ready').exists()
assert sum(p.stat().st_size for p in pathlib.Path('/state').iterdir()) < 1024*1024
print('CONCURRENT_ROTATION_AND_BOUNDED_INGRESS_OK')`], true);
    // Preserve files across a real stop/start; a container tmpfs would hide expiry bugs.
    await docker(['exec', container, 'python', '-c', `import pathlib,os,time
for name in ('api','nginx','postgres','ops'):
 for suffix in ('','.1'):
  p=pathlib.Path('/logs/'+name+'.log'+suffix);p.write_text('startup-expired-marker');os.utime(p,(time.time()-8*86400,)*2)
pathlib.Path('/logs/api.log.2').write_text('fresh-retained-marker')`]);
    let started = Date.now();
    await docker(['stop', '--time', '5', container]);
    assert.ok(Date.now() - started < 5000, 'collector shutdown exceeds five seconds');
    assert.notEqual(JSON.parse(await docker(['inspect', container]))[0].State.ExitCode, 137);
    await docker(['start', container]);
    await docker(['exec', container, 'python', '-c', `import pathlib,time
for _ in range(100):
 if pathlib.Path('/state/ready').exists():break
 time.sleep(.05)
else:raise AssertionError('restart not ready')
files=list(pathlib.Path('/logs').glob('*.log*'))
assert not any(b'startup-expired-marker' in p.read_bytes() for p in files)
assert any(b'fresh-retained-marker' in p.read_bytes() for p in files)
assert pathlib.Path('/logs/api.log.foreign-sentinel').read_text()=='foreign-sentinel'
print('PERSISTENT_RESTART_RETENTION_OK')`], true);
    await docker(['stop', '--time', '5', container]);
    await docker(['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
      '--log-driver', 'syslog', '--log-opt', `syslog-address=udp://${ip}:5514`, '--log-opt', 'tag=opengym-postgres',
      '--log-opt', 'mode=non-blocking', '--log-opt', 'cache-disabled=true', '--entrypoint', 'python', image,
      '-c', 'print("sink unavailable",flush=True)']);
    // Advance only the supervisor's monotonic clock; real rsyslog, commands and I/O stay intact.
    // This exercises the hourly branch without a one-hour wall-clock wait or a product test flag.
    await docker(['rm', container]);
    await docker(['run', '-d', '--name', container, ...labels, '--label', 'com.docker.compose.service=diagnostics',
      '--network', `${project}_private`, '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
      '--log-driver', 'none', '--tmpfs', '/state:rw,noexec,uid=1000,gid=1000,mode=0700,size=1048576',
      '--mount', `type=volume,source=${volume},target=/logs`,
      '--tmpfs', '/run/diagnostics:rw,noexec,uid=1000,gid=1000,mode=0711', '--entrypoint', 'python', image, '-c',
      "import pathlib,time,subprocess,runpy; clock=time.monotonic; time.monotonic=lambda:clock()+(7200 if pathlib.Path('/state/advance').exists() else 0); runpy.run_path('/usr/local/bin/diagnostics.py',run_name='__main__')"]);
    await docker(['exec', container, 'python', '-c', `import pathlib,time,os
for _ in range(100):
 if pathlib.Path('/state/ready').exists():break
 time.sleep(.05)
else:raise AssertionError('timer supervisor not ready')
for name in ('api','nginx','postgres','ops'):
 for suffix in ('','.1'):
  p=pathlib.Path('/logs/'+name+'.log'+suffix);p.write_text('idle-expired-marker');os.utime(p,(time.time()-8*86400,)*2)
pathlib.Path('/state/advance').touch()
for _ in range(100):
 try:
  if not any(b'idle-expired-marker' in p.read_bytes() for p in pathlib.Path('/logs').glob('*.log*')):break
 except FileNotFoundError:pass
 time.sleep(.05)
else:raise AssertionError('hourly retention did not run without API or traffic')
assert pathlib.Path('/logs/api.log.foreign-sentinel').read_text()=='foreign-sentinel'
print('HOURLY_RETENTION_WITHOUT_API_OR_TRAFFIC_OK')`], true);
    assert.ok(readFileSync('backend/diagnostics/rsyslog.conf', 'utf8').includes('ruleset="native"'));
  } finally { await cleanup(project); }
});
