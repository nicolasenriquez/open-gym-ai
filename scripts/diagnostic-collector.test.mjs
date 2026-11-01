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
    networkNames: ['private'], extraVolumes: {},
  });
  const image = `${project}-diagnostics:local`, container = `${project}-diagnostics-1`;
  const labels = ['--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.platform=synthetic'];
  try {
    await docker(['build', ...labels, '--label', 'com.docker.compose.service=diagnostics', '-t', image,
      '-f', 'backend/diagnostics/Dockerfile', 'backend/diagnostics'], true);
    await docker(['network', 'create', '--internal', ...labels, '--label', 'com.docker.compose.service=private',
      '--label', 'com.docker.compose.network=private', `${project}_private`]);
    await docker(['run', '-d', '--name', container, ...labels, '--label', 'com.docker.compose.service=diagnostics',
      '--network', `${project}_private`, '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
      '--log-driver', 'none', '--tmpfs', '/state:rw,noexec,uid=1000,gid=1000,mode=0700,size=1048576',
      '--tmpfs', '/logs:rw,noexec,uid=1000,gid=1000,mode=0700,size=268435456',
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
    await docker(['stop', '--time', '5', container]);
    await docker(['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
      '--log-driver', 'syslog', '--log-opt', `syslog-address=udp://${ip}:5514`, '--log-opt', 'tag=opengym-postgres',
      '--log-opt', 'mode=non-blocking', '--log-opt', 'cache-disabled=true', '--entrypoint', 'python', image,
      '-c', 'print("sink unavailable",flush=True)']);
    assert.ok(readFileSync('backend/diagnostics/rsyslog.conf', 'utf8').includes('ruleset="native"'));
  } finally { await cleanup(project); }
});
