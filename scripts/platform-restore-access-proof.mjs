import assert from 'node:assert/strict';

export async function reviewedAccessProof({ ops, sql, docker, image, project, user }) {
  await sql("INSERT INTO coach.jobs VALUES ('A','queued-before-review','create','manual','queued',clock_timestamp(),0),('B','running-before-review','review','manual','running',clock_timestamp(),0)");
  const trainingBefore = await sql("SELECT md5(jsonb_agg(to_jsonb(t) ORDER BY owner_id)::text) FROM training.documents t");
  await ops(`import json,os
from pathlib import Path
root=Path('/data/restored-b')
restored=json.loads((root/'restore.json').read_text())
review={'target':'restored-b','instance_id':'restored-b','bundle':restored['bundle'],
 'snapshot_at':restored['snapshot_at'],'session_secret':'session','coach_secret':'session',
 'accounts':[
 {'uid':'A','decision':'recover','status':'active','identity_verified':True,'evidence':['protected-independent-identity-A'], 'password':True,'passkeys':['old-zero','old-counter']},
 {'uid':'B','decision':'block','status':'unknown','identity_verified':False,'evidence':[], 'password':False,'passkeys':['old-b']},
 {'uid':'C','decision':'block','status':'disabled','identity_verified':False,'evidence':[], 'password':False,'passkeys':[]},
 {'uid':'D','decision':'block','status':'deleted','identity_verified':False,'evidence':['protected-later-deletion-D'], 'password':False,'passkeys':[]}]}
p=Path('/data/review.json');p.write_text(json.dumps(review));p.chmod(0o600)`);
  const invoke = () => ops(`import subprocess,sys,json
p=subprocess.run([sys.executable,'-m','opengym_platform.operations','restore-access-recover','--config','/run/operator/restore.json','--target','restored-b','--review','/data/review.json'],capture_output=True)
print(json.dumps({'status':p.returncode,'out':p.stdout.decode(),'err':p.stderr.decode()}))`);
  const before = await sql("SELECT md5(jsonb_agg(to_jsonb(t) ORDER BY id)::text) FROM identity.users t");
  const mutations = [
    "review['target']='foreign'",
    "review['instance_id']='foreign'",
    "review['bundle']='0'*32",
    "review['snapshot_at']='2000-01-01T00:00:00+00:00'",
    "review['coach_secret']='runtime'",
    "review['accounts'].pop()",
    "review['accounts'][0]['identity_verified']=False",
    "review['accounts'][0]['evidence']=[]",
    "review['accounts'][0]['passkeys'].pop()",
    "review['accounts'][0]['password']=False",
    "review['accounts'][2].update(decision='recover',status='active',identity_verified=True,evidence=['not-enough-for-disabled'])",
    "review['accounts'][3].update(decision='recover',identity_verified=True,evidence=['known-deleted'])",
    "p.chmod(0o644)",
    "(root/'access').mkdir(mode=0o700)",
  ];
  await ops(`import json,subprocess,sys
from pathlib import Path
root=Path('/data/restored-b');p=Path('/data/review.json');original=p.read_bytes()
mutations=json.loads(${JSON.stringify(JSON.stringify(mutations))})
for mutation in mutations:
 review=json.loads(original)
 exec(mutation)
 p.write_text(json.dumps(review))
 result=subprocess.run([sys.executable,'-m','opengym_platform.operations','restore-access-recover','--config','/run/operator/restore.json','--target','restored-b','--review',str(p)],capture_output=True)
 assert result.returncode==1 and json.loads(result.stdout)=={'code':'RESTORE_ACCESS_BLOCKED'} and not result.stderr,mutation
 if (root/'access').exists():(root/'access').rmdir()
 p.write_bytes(original);p.chmod(0o600)`);
  assert.equal(await sql("SELECT md5(jsonb_agg(to_jsonb(t) ORDER BY id)::text) FROM identity.users t"), before);
  console.log('WRONG_TARGET_INSTANCE_BUNDLE_SNAPSHOT_COVERAGE_IDENTITY_DISABLED_DELETED_PERMISSIONS_OUTPUT_DENIED_OK');
  for (const fault of ['foreign', 'exposed']) {
    await sql(fault === 'foreign' ? "COMMENT ON DATABASE opengym IS 'foreign'" : 'GRANT CONNECT ON DATABASE opengym TO opengym_api_runtime');
    try {
      const denied = JSON.parse(await invoke());
      assert.equal(denied.status, 1);
      assert.deepEqual(JSON.parse(denied.out), { code: 'RESTORE_ACCESS_BLOCKED' });
      assert.equal(denied.err, '');
    } finally {
      await sql("COMMENT ON DATABASE opengym IS 'opengym-restore:restored-b'; REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime");
    }
  }
  // A real SQL failure after private delivery must roll back access and prohibit retry.
  await ops(`import json,shutil\nfrom pathlib import Path\nroot=Path('/data/failed-access');shutil.copytree('/data/restored-b',root)\nr=json.loads((root/'restore.json').read_text());r['target']='failed-access';(root/'restore.json').write_text(json.dumps(r))\ng=json.loads((root/'gate/admission.json').read_text());g['instance_id']='failed-access';(root/'gate/admission.json').write_text(json.dumps(g))\nr=json.loads(Path('/data/review.json').read_text());r.update(target='failed-access',instance_id='failed-access')\np=Path('/data/failed-review.json');p.write_text(json.dumps(r));p.chmod(0o600)\nc=json.loads(Path('/run/operator/restore.json').read_text());c['instance_id']='failed-access';Path('/data/failed-config.json').write_text(json.dumps(c))`);
  await sql("COMMENT ON DATABASE opengym IS 'opengym-restore:failed-access'; CREATE FUNCTION identity.reject_recovery_test() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic recovery fault'; END $$; CREATE TRIGGER reject_recovery_test BEFORE UPDATE ON identity.users FOR EACH ROW EXECUTE FUNCTION identity.reject_recovery_test()");
  try {
    await ops(`import subprocess,sys,json\nfrom pathlib import Path\nfor _ in range(2):\n p=subprocess.run([sys.executable,'-m','opengym_platform.operations','restore-access-recover','--config','/data/failed-config.json','--target','failed-access','--review','/data/failed-review.json'],capture_output=True)\n assert p.returncode==1 and json.loads(p.stdout)=={'code':'RESTORE_ACCESS_BLOCKED'} and not p.stderr\nroot=Path('/data/failed-access')\nassert (root/'access/credential-0.json').exists()\nassert not (root/'access/result.json').exists()\nassert json.loads((root/'gate/admission.json').read_text())['allowed'] is False`);
    assert.equal(await sql("SELECT md5(jsonb_agg(to_jsonb(t) ORDER BY id)::text) FROM identity.users t"), before);
    assert.equal(await sql('SELECT count(*) FROM identity.passkeys'), '3');
    assert.equal(await sql('SELECT count(*) FROM identity.device_links'), '1');
    assert.equal(await sql('SELECT count(*) FROM coach.jobs'), '2');
  } finally {
    await sql("DROP TRIGGER reject_recovery_test ON identity.users; DROP FUNCTION identity.reject_recovery_test(); COMMENT ON DATABASE opengym IS 'opengym-restore:restored-b'");
  }
  console.log('SQL_FAILURE_ROLLS_BACK_ACCESS_PRESERVES_QUARANTINE_AND_BLOCKS_UNCERTAIN_RETRY_OK');
  const result = JSON.parse(await invoke());
  assert.equal(result.status, 0, JSON.stringify(result));
  assert.deepEqual(JSON.parse(result.out), { code: 'RESTORE_ACCESS_REVIEWED', target: 'restored-b', access: 'quarantined' });
  assert.equal(result.err, '');
  assert.equal(await sql("SELECT string_agg(id||':'||disabled||':'||is_admin,',' ORDER BY id) FROM identity.users"), 'A:false:false,B:true:true,C:true:false,D:true:false');
  assert.equal(await sql('SELECT count(*) FROM identity.passkeys'), '0');
  assert.equal(await sql('SELECT count(*) FROM identity.password_credentials'), '1');
  assert.equal(await sql("SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"), 'f');
  assert.equal(await sql('SELECT count(*) FROM identity.device_links'), '0');
  assert.equal(await sql('SELECT count(*) FROM identity.password_resets'), '0');
  assert.equal(await sql('SELECT count(*) FROM coach.jobs'), '0');
  assert.equal(await sql("SELECT count(*) FROM coach.history_events WHERE job_id IN ('queued-before-review','running-before-review') AND outcome='failed' AND error_class='restart'"), '2');
  assert.equal(await sql("SELECT md5(jsonb_agg(to_jsonb(t) ORDER BY owner_id)::text) FROM training.documents t"), trainingBefore);
  await ops(`import os,json,stat
from pathlib import Path
root=Path('/data/restored-b');out=root/'access'
assert stat.S_IMODE(out.stat().st_mode)==0o700
for p in out.iterdir():assert stat.S_IMODE(p.stat().st_mode)==0o600
assert json.loads((root/'gate/admission.json').read_text())['allowed'] is False
assert (out/'session-secret').read_bytes()!=(root/'runtime-secrets/session').read_bytes()
assert (out/'coach-secret').read_bytes()==(root/'runtime-secrets/session').read_bytes()
os.environ['DATA_DIR']=str(root/'data');os.environ['PLATFORM_COACH_SECRET_FILE']=str(out/'coach-secret')
from opengym_platform.coach.secrets import SecretFiles
files=SecretFiles()
assert files.decrypt(files.read('coach-auth-A.json'))=={'token':'SYNTHETIC_COACH_DECRYPT_10_5'}
os.environ['PLATFORM_COACH_SECRET_FILE']=str(out/'session-secret')
assert SecretFiles().decrypt(files.read('coach-auth-A.json')) is None`, true);
  console.log('PRIVATE_OUTPUT_COACH_DECRYPT_AND_SIGNING_KEY_SEPARATION_OK');
  // Dedicated private HTTP fixture: only runtime keys/data, never bootstrap or bundles.
  await ops(`import json,shutil
from pathlib import Path
probe=Path('/data/runtime-probe');probe.mkdir(mode=0o700)
for name in ('session-secret','coach-secret'):shutil.copyfile('/data/restored-b/access/'+name,probe/name);(probe/name).chmod(0o600)
shutil.copyfile('/run/secrets/runtime',probe/'runtime');(probe/'runtime').chmod(0o600)
(probe/'gate').mkdir(mode=0o700)
(probe/'gate/admission.json').write_text(json.dumps({'instance_id':'proof-only','operation':'0'*32,'allowed':True}))`);
  const api = `${project}-api-1`;
  let started = false;
  await sql('GRANT CONNECT ON DATABASE opengym TO opengym_api_runtime');
  try {
    const environment = { PLATFORM_ENV: 'ops', PLATFORM_DB_MODE: 'local_compose', PLATFORM_DB_HOST: 'db',
      PLATFORM_DB_PORT: '5432', PLATFORM_DB_NAME: 'opengym', PLATFORM_DB_TLS: 'disable',
      PLATFORM_DB_PASSWORD_FILE: '/run/secrets/runtime', PLATFORM_SESSION_SECRET_FILE: '/run/secrets/session-secret',
      PLATFORM_COACH_SECRET_FILE: '/run/secrets/coach-secret', DATA_DIR: '/data', PASSWORD_LOGIN: '1', COACH_DISABLED: '1',
      PLATFORM_INSTANCE_ID: 'proof-only', PLATFORM_MAINTENANCE_GATE_DIR: '/run/secrets/gate', RP_ID: 'localhost', ORIGIN: 'http://localhost:3000' };
    await docker(['run', '--detach', '--rm', '--name', api, '--network', `${project}_private`, '--read-only', '--user', user,
      '--label', `com.docker.compose.project=${project}`, '--label', 'com.docker.compose.service=api', '--label', 'org.opengym.platform=synthetic',
      '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--log-driver', 'none', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,mode=1777,size=67108864',
      '--mount', `type=volume,source=${project}_restore-data,target=/run/secrets,volume-subpath=runtime-probe,readonly`,
      '--mount', `type=volume,source=${project}_restore-data,target=/data,volume-subpath=restored-b/data`,
      ...Object.entries(environment).flatMap(([key,value]) => ['-e', `${key}=${value}`]),
      '--entrypoint', 'python', image, '-m', 'uvicorn', 'opengym_platform.application:create_app', '--factory', '--host', '0.0.0.0', '--port', '3000', '--no-access-log']);
    started = true;
    await docker(['exec', api, 'python', '-c', "from pathlib import Path; assert {p.name for p in Path('/run/secrets').iterdir()}=={'runtime','session-secret','coach-secret','gate'}; assert not Path('/bundles').exists() and not Path('/run/operator').exists() and not Path('/data/database.dump').exists()"]);
    await ops(`import json,time,urllib.request,urllib.error,hmac,hashlib,base64
from pathlib import Path
root=Path('/data/restored-b');out=root/'access'
credential=json.loads((out/'credential-0.json').read_text())
def request(path,body=None,headers=None):
 raw=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request('http://${api}:3000/api/v1'+path,data=raw,headers={'Content-Type':'application/json',**(headers or {})})
 try:
  with urllib.request.urlopen(req,timeout=3) as response:return response.status,json.load(response),response.headers
 except urllib.error.HTTPError as error:return error.code,json.load(error),error.headers
for _ in range(100):
 try:
  if request('/health/ready')[0]==200:break
 except OSError:pass
 time.sleep(.1)
else:raise AssertionError('review HTTP not ready')
status,body,headers=request('/login/password',{'identifier':credential['identifier'],'password':credential['password']})
assert status==200,(status,body)
assert body['user']['id']=='A' and body['user']['admin'] is False
cookie=headers['Set-Cookie'].split(';')[0]
assert request('/me',headers={'Cookie':cookie})[0]==200
assert request('/data',headers={'Cookie':cookie})[1]['rev']==7
assert request('/login/password',{'identifier':'old-a','password':'old-synthetic-password'})[0]==401
old=(root/'runtime-secrets/session').read_text().strip()
for version in (0,1):
 payload='A:'+str(int(time.time()*1000+86400000))+':'+str(version)
 token=payload+'.'+base64.urlsafe_b64encode(hmac.new(old.encode(),payload.encode(),hashlib.sha256).digest()).decode().rstrip('=')
 assert request('/me',headers={'Cookie':'gymsid='+token})[0]==401
 assert request('/me',headers={'Authorization':'Bearer '+token})[0]==401
for owner in ('B','C','D'):
 payload=owner+':'+str(int(time.time()*1000+86400000))+':0'
 key=(out/'session-secret').read_bytes()
 token=payload+'.'+base64.urlsafe_b64encode(hmac.new(key,payload.encode(),hashlib.sha256).digest()).decode().rstrip('=')
 assert request('/me',headers={'Authorization':'Bearer '+token})[0]==401
assert not any(b'AGE-SECRET-KEY-' in p.read_bytes() for p in out.iterdir())
assert json.loads((root/'gate/admission.json').read_text())['allowed'] is False`, true);
  } finally {
    if (started) await docker(['rm', '--force', api]);
    await sql('REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime');
  }
  assert.notEqual(JSON.parse(await invoke()).status, 0);
  console.log('NEW_VERIFIED_ACCESS_ONLY_HISTORICAL_CREDENTIALS_AND_OTHER_ACCOUNTS_BLOCKED_OK');
  console.log('PRIVATE_HTTP_NO_BOOTSTRAP_NEW_LOGIN_OLD_COOKIE_BEARER_REJECTED_COACH_DECRYPT_INTACT_NO_REPLAY_OK');
}
