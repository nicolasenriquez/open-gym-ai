import assert from 'node:assert/strict';
import { createHash, randomBytes } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { syntheticHarness } from './synthetic-harness.mjs';
import { reviewedAccessProof } from './platform-restore-access-proof.mjs';
import { rehearsalProof } from './platform-rehearsal-proof.mjs';

export async function restoreProof(ctx) {
  const { root, temporary, image, user, expectedFiles, expectedDigests, digestSQL } = ctx;
  const project = `opengym-platform-test-${randomBytes(8).toString('hex')}`;
  const { docker, cleanup } = syntheticHarness({ root, namespace: 'opengym-platform-test',
    label: 'org.opengym.platform', name: 'Restore', services: ['db', 'api', 'ops', 'migrate', 'bootstrap'],
    images: [], database: 'db', volumeName: 'restore-postgres-data', extraVolumes: { 'restore-data': { name: 'restore-data', service: 'ops' } } });
  const directory = join(temporary, 'restore');
  mkdirSync(directory, { mode: 0o700 });
  const source = JSON.parse(readFileSync(ctx.config)).bundle;
  const original = readFileSync(join(source.destination, `${ctx.receipt.operation}.age`));
  const config = join(directory, 'restore.json');
  writeFileSync(config, JSON.stringify({ instance_id: 'restored-b', target_root: '/data',
    bundle_root: '/bundles', identity_file: '/identity' }), { mode: 0o600 });
  for (const name of ['bootstrap', 'migrator', 'runtime']) {
    writeFileSync(join(directory, name), `synthetic-restore-${name}-only-0123456789`, { mode: 0o600 });
  }
  const imageId = JSON.parse(await docker(['image', 'inspect', image]))[0].Id.slice(7);
  const envFile = join(directory, 'restore.env');
  writeFileSync(envFile, Object.entries({ PLATFORM_RESTORE_TARGET: 'restored-b', PLATFORM_MIGRATE_DIGEST: imageId,
    PLATFORM_OPS_DIGEST: imageId, PLATFORM_RESTORE_SECRETS_DIR: directory, PLATFORM_RESTORE_BUNDLES: source.destination,
    PLATFORM_RESTORE_IDENTITY: source.identity_file, PLATFORM_RESTORE_CONFIG: config })
    .map(([key,value]) => `${key}=${value.replaceAll('\\','/')}`).join('\n'));
  const model = JSON.parse(await docker(['compose', '--project-directory', root, '--env-file', envFile,
    '-p', project, '--profile', '*', '-f', join(root, 'deploy/docker-compose.restore.yml'), 'config', '--format', 'json']));
  assert.deepEqual(Object.keys(model.services).sort(), ['bootstrap', 'db', 'migrate', 'ops']);
  assert.equal(model.networks.private.internal, true);
  assert.equal(model.services.db.image, JSON.parse(readFileSync('backend/versions.json')).postgresImage);
  assert.deepEqual(model.services.db.healthcheck.test.slice(-2), ['-d', 'postgres']);
  for (const [service, definition] of Object.entries(model.services)) {
    assert.ok(!definition.ports?.length && !definition.privileged && !definition.cap_add?.length);
    assert.deepEqual(Object.keys(definition.networks), ['private']);
    assert.equal(definition.read_only, true);
    assert.equal(definition.logging.driver, 'none');
    definition.labels = { 'org.opengym.platform': 'synthetic' };
    definition.user = user;
    if (service !== 'db') definition.entrypoint = service === 'ops' ? ['python'] : ['python', '-m', 'opengym_platform.platform_migrate'];
  }
  model.services.ops.tmpfs.push(`/small:size=64m,mode=0700,uid=${user.split(':')[0]},gid=${user.split(':')[1]}`);
  model.networks.private.labels = { 'org.opengym.platform': 'synthetic', 'com.docker.compose.service': 'private' };
  for (const [name, volume] of Object.entries(model.volumes)) volume.labels = {
    'org.opengym.platform': 'synthetic', 'com.docker.compose.service': name === 'postgres-data' ? 'db' : 'ops',
  };
  const file = join(directory, 'compose.json');
  writeFileSync(file, JSON.stringify(model));
  const compose = ['compose', '--project-directory', root, '--env-file', join(temporary, 'empty.env'), '-p', project, '-f', file];
  const sql = async query => (await docker([...compose, 'exec', '-T', 'db', 'psql', '-U', 'opengym_platform_bootstrap',
    '-d', 'opengym', '-v', 'ON_ERROR_STOP=1', '-Atc', query])).trim();
  const ops = (code, live = false) => docker([...compose, 'run', '--rm', '--no-deps', 'ops', '-c', code], live);
  const invoke = async (target, options = [], probe) => JSON.parse(await docker([...compose, 'run', '--rm', '--no-deps', ...options, 'ops', '-c', `import subprocess,sys,json
p=subprocess.run([sys.executable,${probe ? "'/app/tests/platform/restore_probe.py','"+probe+"','restore'" : "'-m','opengym_platform.operations','restore'"},
 '--config','/run/operator/restore.json','--bundle','${ctx.receipt.operation}','--target','${target}'],capture_output=True)
print(json.dumps({'status':p.returncode,'out':p.stdout.decode(),'err':p.stderr.decode()}))`]));
  const select = async (target, targetRoot = '/data') => {
    writeFileSync(config, JSON.stringify({ instance_id: target, target_root: targetRoot, bundle_root: '/bundles', identity_file: '/identity' }));
    await sql(`COMMENT ON DATABASE opengym IS 'opengym-restore:${target}'`);
  };
  try {
    await docker([...compose, 'up', '-d', '--wait', 'db']);
    await docker([...compose, 'run', '--rm', '--no-deps', 'bootstrap'], true);
    await docker([...compose, 'run', '--rm', '--no-deps', 'migrate'], true);
    await sql(readFileSync('backend/backup-role.sql', 'utf8'));
    await sql("COMMENT ON DATABASE opengym IS 'opengym-restore:restored-b'; REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime");
    const [uid, gid] = user.split(':').map(Number);
    await docker([...compose, 'run', '--rm', '--no-deps', '--user', '0:0', '--cap-add', 'CHOWN', 'ops', '-c',
      `import os; os.chmod('/data',0o700); os.chown('/data',${uid},${gid})`]);
    if (ctx.fullTiming) {
      await rehearsalProof({ ...ctx, directory, file, envFile, project, sql, config, ops, docker, compose, select });
      assert.deepEqual(readFileSync(join(source.destination, `${ctx.receipt.operation}.age`)), original);
      assert.equal((await ctx.sql(digestSQL)).trim(), expectedDigests);
      await ctx.ready();
      return;
    }
    writeFileSync(config, JSON.stringify({ instance_id: 'wrong-key', target_root: '/data', bundle_root: '/bundles', identity_file: '/wrong-identity' }));
    await sql("COMMENT ON DATABASE opengym IS 'opengym-restore:wrong-key'");
    const wrongKey = JSON.parse(await docker([...compose, 'run', '--rm', '--no-deps', '--volume', `${join(temporary, 'wrong-identity')}:/wrong-identity:ro`, 'ops', '-c', `import subprocess,sys,json
p=subprocess.run([sys.executable,'-m','opengym_platform.operations','restore','--config','/run/operator/restore.json','--bundle','${ctx.receipt.operation}','--target','wrong-key'],capture_output=True)
print(json.dumps({'status':p.returncode,'out':p.stdout.decode(),'err':p.stderr.decode()}))`]));
    assert.equal(wrongKey.status, 1);
    assert.equal(wrongKey.err, '', wrongKey.err);
    assert.match(wrongKey.out, /RESTORE_BLOCKED/);
    const bad = join(directory, 'bad');
    mkdirSync(bad, { mode: 0o700 });
    for (const fault of ['missing-secret', 'truncated', 'checksum', 'duplicate', 'traversal', 'link', 'schema', 'major', 'format']) {
    await docker([...compose, 'run', '--rm', '--no-deps', '--volume', `${bad}:/faults`, 'ops', '-c', `import io,json,subprocess,tarfile
from pathlib import Path
plain=subprocess.check_output(['age','-d','-i','/identity','/bundles/${ctx.receipt.operation}.age'],stderr=subprocess.DEVNULL)
fault='${fault}'
if fault=='truncated':
 Path('/faults/${ctx.receipt.operation}.age').write_bytes(Path('/bundles/${ctx.receipt.operation}.age').read_bytes()[:-1])
 raise SystemExit(0)
changed=io.BytesIO()
with tarfile.open(fileobj=io.BytesIO(plain)) as source:
 manifest=json.load(source.extractfile('manifest.json'))
 if fault=='missing-secret':manifest['files']=[item for item in manifest['files'] if item['path']!='runtime-secrets/session']
 if fault=='schema':manifest['schema']='unknown'
 if fault=='major':manifest['tools']['postgres']='99.0'
 if fault=='format':manifest['version']=99
 with tarfile.open(fileobj=changed,mode='w',format=tarfile.USTAR_FORMAT) as archive:
  for member in source:
   if fault=='missing-secret' and member.name=='runtime-secrets/session':continue
   content=json.dumps(manifest).encode() if member.name=='manifest.json' else source.extractfile(member).read() if member.isfile() else None
   if fault=='checksum' and member.name.startswith('data/uploads/A/') and member.isfile():content=b'z'*member.size
   if content is not None:member.size=len(content)
   archive.addfile(member,io.BytesIO(content) if content is not None else None)
  if fault in ('duplicate','traversal','link'):
   name={'duplicate':'manifest.json','traversal':'../escape','link':'data/unsafe'}[fault]
   member=tarfile.TarInfo(name)
   if fault=='link':member.type=tarfile.SYMTYPE;member.linkname='/identity'
   archive.addfile(member,io.BytesIO(b''))
recipient=subprocess.check_output(['age-keygen','-y','/identity'],text=True).strip()
with Path('/faults/${ctx.receipt.operation}.age').open('wb') as output:
 subprocess.run(['age','-r',recipient],input=changed.getvalue(),stdout=output,stderr=subprocess.DEVNULL,check=True)`]);
    writeFileSync(config, JSON.stringify({ instance_id: fault, target_root: '/data', bundle_root: '/bad', identity_file: '/identity' }));
    await sql(`COMMENT ON DATABASE opengym IS 'opengym-restore:${fault}'`);
    const rejected = JSON.parse(await docker([...compose, 'run', '--rm', '--no-deps', '--volume', `${bad}:/bad:ro`, 'ops', '-c', `import subprocess,sys,json
p=subprocess.run([sys.executable,'-m','opengym_platform.operations','restore','--config','/run/operator/restore.json','--bundle','${ctx.receipt.operation}','--target','${fault}'],capture_output=True)
print(json.dumps({'status':p.returncode,'out':p.stdout.decode(),'err':p.stderr.decode()}))`]));
    assert.equal(rejected.status, 1, JSON.stringify({fault,...rejected}));
    assert.equal(rejected.err, '');
    assert.match(rejected.out, /RESTORE_BLOCKED/);
    assert.equal(await sql('SELECT count(*) FROM identity.users'), '0');
    assert.equal(await sql('SELECT count(*) FROM coach.settings'), '1');
    await ops(`from pathlib import Path
assert not Path('/data/${fault}/restore.json').exists()`);
    console.log(`RESTORE_${fault.toUpperCase()}_BLOCKED_WITHOUT_SQL_MUTATION_OK`);
    }
    for (const fault of ['foreign', 'exposed', 'nonempty', 'foreign-table', 'foreign-reference', 'in-use', 'mutex']) {
      await select(fault);
      let peer;
      try {
        if (fault === 'foreign') await sql("COMMENT ON DATABASE opengym IS 'foreign-unowned'");
        if (fault === 'exposed') await sql("GRANT CONNECT ON DATABASE opengym TO opengym_api_runtime");
        if (fault === 'nonempty') await sql("INSERT INTO identity.users(id,display_name) VALUES ('sentinel','untouched target')");
        if (fault === 'foreign-table') await sql('CREATE TABLE identity.unrelated_sentinel(id int); INSERT INTO identity.unrelated_sentinel VALUES (123)');
        if (fault === 'foreign-reference') await sql('CREATE SCHEMA unrelated; CREATE TABLE unrelated.sentinel(id int, owner_id text REFERENCES identity.users(id)); INSERT INTO unrelated.sentinel VALUES (123,NULL)');
        if (fault === 'in-use' || fault === 'mutex') {
          peer = `${project}-ops-run-${randomBytes(6).toString('hex')}`;
          await docker([...compose, 'run', '--rm', '-d', '--no-deps', '--name', peer, 'ops', '-c', `import asyncio,asyncpg
from pathlib import Path
async def run():
 c=await asyncpg.connect(host='db',database='opengym',user='opengym_platform_bootstrap',password=Path('/run/secrets/bootstrap').read_text())
 ${fault === 'mutex' ? "await c.execute('SELECT pg_advisory_lock(728322)')" : "await c.execute('SELECT 1')"}
 Path('/data/peer-ready').write_text('ready')
 await asyncio.sleep(60)
asyncio.run(run())`]);
          await docker(['exec', peer, 'python', '-c', "import time; from pathlib import Path\nfor _ in range(100):\n if Path('/data/peer-ready').exists():break\n time.sleep(.05)\nelse:raise AssertionError('PEER_NOT_READY')"]);
        }
        const failure = await invoke(fault);
        if (fault === 'foreign-table') assert.equal(await sql('SELECT count(*) FROM identity.unrelated_sentinel'), '1', JSON.stringify({ fault, ...failure }));
        if (fault === 'foreign-reference') assert.equal(await sql('SELECT count(*) FROM unrelated.sentinel'), '1', JSON.stringify({ fault, ...failure }));
        assert.equal(failure.status, 1, JSON.stringify({ fault, ...failure }));
        assert.equal(failure.err, '');
        assert.match(failure.out, /RESTORE_BLOCKED/);
        assert.equal(await sql('SELECT count(*) FROM identity.users'), fault === 'nonempty' ? '1' : '0');
        await ops(`from pathlib import Path
assert not Path('/data/${fault}').exists()`);
      } finally {
        if (peer) {
          await docker(['stop', peer]);
          await ops("from pathlib import Path; Path('/data/peer-ready').unlink()");
        }
        if (fault === 'exposed') await sql("REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime");
        if (fault === 'nonempty') await sql("DELETE FROM identity.users WHERE id='sentinel'");
        if (fault === 'foreign-table') await sql('DROP TABLE identity.unrelated_sentinel');
        if (fault === 'foreign-reference') await sql('DROP SCHEMA unrelated CASCADE');
      }
      console.log(`RESTORE_${fault.toUpperCase()}_TARGET_REJECTED_UNCHANGED_OK`);
    }
    await select('post-extract');
    const changed = await invoke('post-extract', [], 'post-extract');
    assert.equal(changed.status, 1, JSON.stringify(changed));
    assert.equal(changed.err, '');
    assert.equal(await sql('SELECT count(*) FROM identity.users'), '0');
    console.log('POST_EXTRACTION_DESTINATION_MUTATION_REJECTED_BEFORE_SQL_OK');
    await select('disk-full', '/small');
    const full = await invoke('disk-full', [], 'full');
    assert.equal(full.status, 1, JSON.stringify(full));
    assert.equal(full.err, '');
    assert.match(full.out, /SYNTHETIC_RESTORE_ENOSPC_OBSERVED/);
    assert.match(full.out, /RESTORE_BLOCKED/);
    assert.equal(await sql('SELECT count(*) FROM identity.users'), '0');
    console.log('RESTORE_REAL_EXTRACTION_ENOSPC_REMAINS_BLOCKED_OK');
    await select('interrupted');
    const paused = `${project}-ops-run-${randomBytes(6).toString('hex')}`;
    await docker([...compose, 'run', '--rm', '-d', '--no-deps', '--name', paused, 'ops',
      '/app/tests/platform/restore_probe.py', 'pause', 'restore', '--config', '/run/operator/restore.json',
      '--bundle', ctx.receipt.operation, '--target', 'interrupted']);
    await docker(['exec', paused, 'python', '-c', "import time; from pathlib import Path\nfor _ in range(1000):\n if Path('/data/interrupted/decrypt-started').exists():break\n time.sleep(.02)\nelse:raise AssertionError('REAL_DECRYPT_NOT_STARTED')"]);
    await docker(['kill', paused]);
    await ops(`import json
from pathlib import Path
root=Path('/data/interrupted')
assert not (root/'restore.json').exists()
assert json.loads((root/'gate/admission.json').read_text())['allowed'] is False
assert (root/'journal.json').exists()`);
    assert.notEqual((await invoke('interrupted')).status, 0);
    assert.equal(await sql('SELECT count(*) FROM identity.users'), '0');
    console.log('REAL_DECRYPT_INTERRUPTION_PRESERVES_QUARANTINE_AND_REFUSES_REUSE_OK');
    await select('restored-b');
    const result = await ops(`import subprocess,sys,json
p=subprocess.run([sys.executable,'-m','opengym_platform.operations','restore','--config','/run/operator/restore.json','--bundle','${ctx.receipt.operation}','--target','restored-b'],capture_output=True)
print(json.dumps({'status':p.returncode,'out':p.stdout.decode(),'err':p.stderr.decode()}))`);
    const outcome = JSON.parse(result);
    assert.equal(outcome.status, 0, JSON.stringify(outcome));
    assert.match(outcome.out, /RESTORE_QUARANTINED/);
    assert.equal(outcome.err, '');
    assert.equal(await sql(digestSQL), expectedDigests);
    for (const [name, value, called] of [['audit.events_id_seq', '987', 't'], ['coach.history_events_event_id_seq', '123', 'f'], ['coach.instance_results_event_id_seq', '456', 't']]) {
      assert.equal(await sql(`SELECT last_value::text || ':' || is_called::text FROM ${name}`), `${value}:${called === 't' ? 'true' : 'false'}`);
    }
    const catalog = "SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text FROM (SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity,c.relforcerowsecurity,c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('identity','training','coach','administration','notifications','audit') AND c.relkind IN ('r','S')) t";
    assert.equal(await sql(catalog), (await ctx.sql(catalog)).trim());
    const policies = "SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text FROM pg_policies t WHERE schemaname IN ('identity','training','coach','administration','notifications','audit')";
    assert.equal(await sql(policies), (await ctx.sql(policies)).trim());
    await sql("GRANT CONNECT ON DATABASE opengym TO opengym_api_runtime");
    try {
      await docker([...compose, 'run', '--rm', '--no-deps', 'ops', '-c', `import asyncio,asyncpg
from datetime import datetime,UTC,timedelta
from pathlib import Path
async def check():
 c=await asyncpg.connect(host='db',database='opengym',user='opengym_api_runtime',password=Path('/run/secrets/runtime').read_text())
 assert await c.fetchval('SELECT current_user')=='opengym_api_runtime'
 assert not await c.fetchval("SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user")
 assert await c.fetchval('SELECT count(*) FROM training.documents')==0
 for owner,other,rev in [('A','B',7),('B','A',11)]:
  async with c.transaction():
   assert await c.fetchval('SELECT id FROM identity.lock_actor($1,0,$2)',owner,datetime.now(UTC)+timedelta(minutes=1))==owner
   await c.execute("SELECT set_config('app.owner_id',$1,true)",owner)
   assert await c.fetchval('SELECT revision FROM training.documents WHERE owner_id=$1',owner)==rev
   assert await c.fetchval('SELECT revision FROM training.documents WHERE owner_id=$1',other) is None
 assert await c.fetchval('SELECT count(*) FROM training.documents')==0
 try:
  old=await asyncpg.connect(host='db',database='opengym',user='opengym_api_runtime',password=Path('/data/restored-b/runtime-secrets/runtime').read_text())
 except asyncpg.InvalidPasswordError:pass
 else:
  await old.close()
  raise AssertionError('old cluster password inherited')
 try:await c.execute('CREATE TABLE public.forbidden_restore_ddl(id int)')
 except asyncpg.InsufficientPrivilegeError:pass
 else:raise AssertionError('runtime DDL allowed')
 await c.close()
asyncio.run(check())`], true);
    } finally { await sql("REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime"); }
    console.log('RESTORED_ROLE_OWNERSHIP_ACL_FORCE_RLS_AND_REAL_RUNTIME_A_B_SEQUENCES_OK');
    const hashes = JSON.parse(await ops(`import json,hashlib
from pathlib import Path
root=Path('/data/restored-b')
assert json.loads((root/'gate/admission.json').read_text())['allowed'] is False
assert json.loads((root/'restore.json').read_text())['access']=='quarantined'
assert (root/'runtime-secrets/session').read_bytes()==b'synthetic-maintenance-session-only-0123456789'
assert hashlib.sha256((root/'configuration/0').read_bytes()).hexdigest()=='${createHash('sha256').update(readFileSync(ctx.config)).digest('hex')}'
assert not any(b'AGE-SECRET-KEY-' in p.read_bytes() for p in root.rglob('*') if p.is_file())
print(json.dumps({p.relative_to(root/'data').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'data').rglob('*') if p.is_file()}))`));
    for (const [path, bytes] of Object.entries(expectedFiles)) assert.equal(hashes[path], createHash('sha256').update(bytes).digest('hex'));
    const sourceApi = (await ctx.docker(['ps', '-q', '--filter', `label=com.docker.compose.project=${ctx.project}`, '--filter', 'label=com.docker.compose.service=api'])).trim();
    const apiInfo = JSON.parse(await ctx.docker(['inspect', sourceApi]))[0];
    const sourceIP = Object.values(apiInfo.NetworkSettings.Networks)[0].IPAddress;
    await ops(`import socket
try:
 socket.create_connection(('${sourceIP}',3000),timeout=1)
except OSError:pass
else:raise AssertionError('restore can reach live instance')
assert not any(line.split()[1]=='00000000' for line in open('/proc/net/route').readlines()[1:])`);
    assert.equal(await sql("SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"), 'f');
    assert.equal(await sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND usename='opengym_api_runtime'"), '0');
    const containers = JSON.parse(await docker(['inspect', (await docker([...compose, 'ps', '-q', 'db'])).trim()]));
    assert.equal(Object.keys(containers[0].NetworkSettings.Ports ?? {}).filter(port => containers[0].NetworkSettings.Ports[port]).length, 0);
    const networks = Object.keys(containers[0].NetworkSettings.Networks);
    assert.equal(networks.length, 1);
    assert.equal(JSON.parse(await docker(['network', 'inspect', networks[0]]))[0].Internal, true);
    assert.deepEqual(readFileSync(join(source.destination, `${ctx.receipt.operation}.age`)), original);
    await ctx.ready();
    assert.equal((await ctx.sql(digestSQL)).trim(), expectedDigests);
    assert.notEqual((await invoke('restored-b')).status, 0);
    assert.equal(await sql(digestSQL), expectedDigests);
    await docker(['run', '--rm', '--network', 'none', '--read-only', '--user', user, '--cap-drop', 'ALL',
      '--security-opt', 'no-new-privileges:true', '--label', `com.docker.compose.project=${project}`,
      '--label', 'com.docker.compose.service=api', '--label', 'org.opengym.platform=synthetic',
      '--mount', `type=volume,src=${project}_restore-data,dst=/run/maintenance-gate,volume-subpath=restored-b/gate,readonly`,
      '-e', 'PLATFORM_INSTANCE_ID=restored-b', '-e', 'PLATFORM_MAINTENANCE_GATE_DIR=/run/maintenance-gate',
      '--entrypoint', 'python', image, '-c', `from pathlib import Path
from opengym_platform.application import create_app
assert not Path('/run/secrets/bootstrap').exists()
try:create_app()
except RuntimeError as error:assert str(error)=='PLATFORM_MAINTENANCE_BLOCKED',str(error)
else:raise AssertionError('RESTORED_API_ADMITTED')`], true);
    console.log('REAL_RESTORE_SQL_FILES_SOURCE_UNCHANGED_AND_QUARANTINED_OK');
    if (ctx.reviewedAccess) await reviewedAccessProof({ ops, sql, docker, compose, image, project, user });
  } finally { await cleanup(project); }
}
