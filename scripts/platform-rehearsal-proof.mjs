import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

export async function rehearsalProof(ctx) {
  const { root, directory, file, envFile, project, receipt, sql, config, compose, docker, select, image } = ctx;
  const state = join(directory, 'reports');
  mkdirSync(state, { mode: 0o700 });
  const host = join(directory, 'rehearse.json');
  const clock=offset=>{const path=join(directory,`clock-${offset}.mjs`);writeFileSync(path,`const Native=Date;globalThis.Date=class extends Native{constructor(...args){super(...(args.length?args:[Native.now()+${offset}]));}static now(){return Native.now()+${offset}}};`);return pathToFileURL(path).href;};
  writeFileSync(host, JSON.stringify({ instance_id: 'restored-b', project, project_directory: root,
    compose_files: [file], env_file: envFile, state_root: state, bundle: receipt.operation,
    incident_at: new Date(Date.now()+7*3600_000-2000).toISOString(), review_file: join(directory, 'missing-review.json') }), { mode: 0o600 });
  const originalConfig=readFileSync(host);
  const peer=`${project}-ops-run-111111111111`;
  await docker(['run','--detach','--name',peer,'--network',`${project}_private`,'--user',ctx.user,'--read-only','--cap-drop','ALL',
    '--security-opt','no-new-privileges:true','--label',`com.docker.compose.project=${project}`,'--label','com.docker.compose.service=ops',
    '--label','org.opengym.platform=synthetic','--entrypoint','python',image,'-c','import time;time.sleep(300)']);
  try {
    writeFileSync(host,JSON.stringify({...JSON.parse(originalConfig),instance_id:'unexpected-peer',incident_at:new Date(Date.now()-2000).toISOString()}));
    const denied=spawnSync(process.execPath,['scripts/platform.mjs','operate','restore-rehearse','--config',host],{cwd:root,encoding:'utf8',timeout:30_000});
    assert.equal(denied.status,1,denied.stderr);
    const record=JSON.parse(readFileSync(join(state,'unexpected-peer','report.json')));
    assert.equal(record.phase,'preflight');assert.equal(record.access,'not_admitted');assert.equal(record.closed,false);assert.equal(record.complete,false);
    assert.equal(await sql('SELECT count(*) FROM training.documents'),'0');
  }finally{await docker(['rm','--force',peer]);writeFileSync(host,originalConfig);}
  console.log('ACTUAL_UNKNOWN_NETWORK_PEER_BLOCKS_BEFORE_RESTORE_WITHOUT_FALSE_ISOLATION_CREDIT_OK');
  const result = spawnSync(process.execPath, ['--import',clock(7*3600_000),'scripts/platform.mjs', 'operate', 'restore-rehearse', '--config', host],
    { cwd: root, encoding: 'utf8', timeout: 120_000 });
  assert.equal(result.status, 1, result.stderr);
  assert.equal(JSON.parse(result.stdout).code, 'REHEARSAL_INCOMPLETE');
  const report = JSON.parse(readFileSync(join(state, 'restored-b', 'report.json')));
  assert.equal(report.complete, false);
  assert.equal(report.rto_credited, false);
  assert.equal(report.access, 'quarantined');
  assert.ok(report.elapsed_ms >= 2000);
  assert.equal(report.phase, 'review_pending');
  for(const name of ['authenticate_ms','extract_verify_ms','load_sql_ms'])assert.ok(report.restore_phases_ms[name]>0,name);
  assert.ok(report.rpo_ms>6*3600_000);assert.equal(report.rpo_met,false);
  assert.equal(await sql("SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"), 'f');
  assert.equal(JSON.parse(readFileSync(config)).instance_id, 'restored-b');
  assert.equal(await sql(ctx.digestSQL),ctx.expectedDigests);
  for(const [name,value] of [['audit.events_id_seq','987:true'],['coach.history_events_event_id_seq','123:false'],['coach.instance_results_event_id_seq','456:true']])assert.equal(await sql(`SELECT last_value||':'||is_called FROM ${name}`),value);
  console.log('UNREVIEWED_RESTORE_REMAINS_PARTIAL_WITH_FULL_ELAPSED_TIME_OK');
  await docker([...compose,'exec','-T','db','psql','-U','opengym_platform_bootstrap','-d','postgres','-c','DROP DATABASE opengym','-c','CREATE DATABASE opengym']);
  await docker([...compose,'run','--rm','--no-deps','bootstrap']);
  await docker([...compose,'run','--rm','--no-deps','migrate']);
  await select('reviewed-partial');
  await sql('REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime');
  const review = join(directory,'review.json');
  writeFileSync(review,JSON.stringify({target:'reviewed-partial',instance_id:'reviewed-partial',bundle:receipt.operation,
    snapshot_at:receipt.snapshot_at,session_secret:'session',coach_secret:'session',accounts:[
      {uid:'A',decision:'recover',status:'active',identity_verified:true,evidence:['independent-identity-A'],password:true,passkeys:['old-zero','old-counter']},
      {uid:'B',decision:'block',status:'unknown',identity_verified:false,evidence:[],password:false,passkeys:['old-b']},
      {uid:'C',decision:'block',status:'disabled',identity_verified:false,evidence:[],password:false,passkeys:[]},
      {uid:'D',decision:'block',status:'deleted',identity_verified:false,evidence:['protected-later-deletion-D'],password:false,passkeys:[]}
    ]}),{mode:0o600});
  writeFileSync(host,JSON.stringify({...JSON.parse(readFileSync(host)),instance_id:'reviewed-partial',review_file:review,incident_at:new Date(Date.now()-2000).toISOString(),
    runtime_image:JSON.parse(await docker(['image','inspect',image]))[0].Id}));
  const reviewed = spawnSync(process.execPath,['scripts/platform.mjs','operate','restore-rehearse','--config',host],
    {cwd:root,encoding:'utf8',timeout:120_000});
  assert.equal(reviewed.status,1,reviewed.stderr);
  const partial=JSON.parse(readFileSync(join(state,'reviewed-partial','report.json')));
  assert.equal(partial.phase,'verification_pending',JSON.stringify(partial));
  assert.equal(partial.reviewed,true);
  assert.equal(partial.complete,false);
  assert.equal(partial.rto_credited,false);
  assert.equal(partial.blocked_accesses,3);
  assert.equal(partial.unresolved_accesses,1);
  assert.equal(partial.checks.http,true);
  assert.equal(partial.checks.rls,true);
  assert.equal(await sql("SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"),'f');
  console.log('REVIEWED_PARTIAL_ACCESS_REAL_HTTP_RLS_WATCHDOG_CLOSED_OK');
  const browserImage=`${project}-browser-rehearsal:local`;
  await docker(['build','--label',`com.docker.compose.project=${project}`,'--label','com.docker.compose.service=platform-browser',
    '--label','org.opengym.platform=synthetic','-t',browserImage,'-f','backend/Dockerfile.browser','.']);
  let controller;
  try {
    for(const [target,offset,expectedCode] of [['reviewed-complete',0,'REHEARSAL_VERIFIED'],['rto-exceeded',25*3600_000,'REHEARSAL_OBJECTIVE_FAILED']]) {
    await docker([...compose,'exec','-T','db','psql','-U','opengym_platform_bootstrap','-d','postgres','-c','DROP DATABASE opengym','-c','CREATE DATABASE opengym']);
    await docker([...compose,'run','--rm','--no-deps','bootstrap']);
    await docker([...compose,'run','--rm','--no-deps','migrate']);
    await select(target);
    await sql('REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime');
    const fullReview=JSON.parse(readFileSync(review));
    fullReview.target=fullReview.instance_id=target;
    fullReview.accounts[1].status='deleted';fullReview.accounts[1].evidence=['independent-later-deletion-B'];
    writeFileSync(review,JSON.stringify(fullReview));
    const evidence=join(directory,target+'-client');mkdirSync(evidence,{mode:0o700});
    writeFileSync(host,JSON.stringify({...JSON.parse(readFileSync(host)),instance_id:target,verification_file:join(evidence,'verification.json')}));
    const child=spawn(process.execPath,['--import',clock(offset),'scripts/platform.mjs','operate','restore-rehearse','--config',host],{cwd:root,stdio:['ignore','pipe','pipe']});
    controller=child;
    let out='',err='';child.stdout.on('data',data=>out+=data);child.stderr.on('data',data=>err+=data);
    const finished=new Promise((accept,reject)=>{child.on('error',reject);child.on('close',code=>accept(code));});
    const reportPath=join(state,target,'report.json');
    let live;
    for(let i=0;i<300;i++){
      try{live=JSON.parse(readFileSync(reportPath));if(live.phase==='client_verification')break;}catch{}
      assert.equal(child.exitCode,null,err+out+JSON.stringify(live));await sleep(100);
    }
    assert.equal(live?.phase,'client_verification',JSON.stringify(live));
    const clientName=`${project}-api-run-123456789abc`;
    let clientError;
    const clientRun=docker(['run','--rm','--name',clientName,'--network',live.probe.network,'--user',ctx.user,'--read-only','--cap-drop','ALL',
      '--security-opt','no-new-privileges:true','--shm-size','256m','--tmpfs','/tmp:rw,nosuid,nodev,mode=1777,size=536870912',
      '--label',`com.docker.compose.project=${project}`,'--label','com.docker.compose.service=api','--label','org.opengym.platform=synthetic',
      '--mount',`type=volume,source=${live.probe.volume},target=/run/client,volume-subpath=${live.probe.client_subpath},readonly`,
      '--volume',`${evidence}:/evidence`,'--entrypoint','node',browserImage,'rehearsal.mjs'],true).catch(error=>{clientError=error;});
    let dirty;
    for(let i=0;i<300;i++){
      assert.equal(clientError,undefined);
      try{dirty=JSON.parse(readFileSync(join(evidence,'dirty.json')));break;}catch{}await sleep(100);
    }
    assert.ok(dirty,'Browser did not establish pending work');
    assert.equal(Number(await sql("SELECT revision FROM training.documents WHERE owner_id='A'")),dirty.base);
    await sql(`UPDATE training.documents SET document=jsonb_build_object('_rev',revision,'_wid','rehearsal-restored-branch','_wids','[]'::jsonb,'workouts','[{"id":"rehearsal-restored-workout","d":"2026-01-01","entries":[]}]'::jsonb,'routines','[]'::jsonb) WHERE owner_id='A'`);
    writeFileSync(join(evidence,'rewound.json'),JSON.stringify({ready:true}),{mode:0o600});
    await clientRun;
    assert.equal(clientError,undefined);
    assert.equal(await finished,offset===0?0:1,err+out+readFileSync(reportPath));
    const full=JSON.parse(readFileSync(reportPath));
    const admission=JSON.parse(await ctx.ops(`from pathlib import Path;print((Path('/data')/'${target}'/'gate/admission.json').read_text())`));
    assert.equal(admission.allowed,false);
    assert.equal(JSON.parse(out).code,expectedCode);
    assert.equal(full.complete,true);assert.equal(full.rto_credited,offset===0);
    assert.equal(full.operational_acceptance,false);assert.equal(full.scope,'isolated-data-new-password-and-client-reconciliation');
    if(offset)assert.ok(full.elapsed_ms>=25*3600_000);assert.equal(full.rpo_met,true);assert.equal(full.closed,true);
    const observed=JSON.parse(readFileSync(join(evidence,'observed.json')));
    assert.equal(await sql("SELECT write_id FROM training.documents WHERE owner_id='A'"),observed.wid);
    assert.equal(await sql("SELECT document->>'theme' FROM training.documents WHERE owner_id='A'"),'dark');
    assert.equal(await sql("SELECT document->>'notes' FROM training.documents WHERE owner_id='B'"),'synthetic B');
    assert.equal(await sql("SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"),'f');
    const saved=join(directory, target + '-evidence');
    mkdirSync(saved,{recursive:true,mode:0o700});writeFileSync(join(saved,'report.json'),JSON.stringify(full,null,2));
    for(const name of ['client.png','observed.json','verification.json'])writeFileSync(join(saved,name),readFileSync(join(evidence,name)),{mode:0o600});
    console.log(offset?'RTO_INCLUDES_FULL_REVIEW_PREPARATION_AND_VERIFICATION_EXCEEDED_IS_FAILURE_OK':'COMPLETE_REAL_HOST_RESTORE_REVIEW_HTTP_PG_MEDIA_COACH_CLIENT_FULL_TIMING_OK');
    }
    for(const target of ['stale-evidence','forged-observation','host-interrupted']) {
      await docker([...compose,'exec','-T','db','psql','-U','opengym_platform_bootstrap','-d','postgres','-c','DROP DATABASE opengym','-c','CREATE DATABASE opengym']);
      await docker([...compose,'run','--rm','--no-deps','bootstrap']);await docker([...compose,'run','--rm','--no-deps','migrate']);
      await select(target);await sql('REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime');
      const r=JSON.parse(readFileSync(review));r.target=r.instance_id=target;writeFileSync(review,JSON.stringify(r));
      const destination=join(directory,target+'-client');mkdirSync(destination,{mode:0o700});
      writeFileSync(host,JSON.stringify({...JSON.parse(readFileSync(host)),instance_id:target,incident_at:new Date(Date.now()-2000).toISOString(),verification_file:join(destination,'verification.json')}));
      const child=spawn(process.execPath,['scripts/platform.mjs','operate','restore-rehearse','--config',host],{cwd:root,stdio:['ignore','pipe','pipe']});
      controller=child;let out='',err='';child.stdout.on('data',v=>out+=v);child.stderr.on('data',v=>err+=v);
      const finished=new Promise((accept,reject)=>{child.on('error',reject);child.on('close',accept);});
      const reportPath=join(state,target,'report.json');let live;
      for(let i=0;i<300;i++) {try{live=JSON.parse(readFileSync(reportPath));if(live.phase==='client_verification')break;}catch{}assert.equal(child.exitCode,null,err+out);await sleep(100);}
      assert.equal(live?.phase,'client_verification',JSON.stringify(live));
      if(target!=='host-interrupted') {
        const old=JSON.parse(readFileSync(join(directory,'rto-exceeded-client','verification.json')));old.target=target;
        if(target==='forged-observation') {
          old.operation=live.operation;
          old.observation={uid:'A',...JSON.parse(await sql("SELECT json_build_object('rev',revision,'wid',write_id) FROM training.documents WHERE owner_id='A'")),sha256:'0'.repeat(64)};
        }
        for(const name of ['client.png','observed.json'])writeFileSync(join(destination,name),readFileSync(join(directory,'rto-exceeded-client',name)),{mode:0o600});
        writeFileSync(join(destination,'verification.json'),JSON.stringify(old),{mode:0o600});
        assert.equal(await finished,1,err+out);
        const denied=JSON.parse(readFileSync(reportPath));assert.equal(denied.complete,false);assert.equal(denied.rto_credited,false);assert.equal(denied.closed,true);
        assert.equal(denied.failure,'REHEARSAL_BLOCKED');
        console.log(target==='stale-evidence'?'OLD_CLIENT_PROOF_WITH_VALID_ARTIFACT_HASHES_CANNOT_CREDIT_NEW_REHEARSAL_OK':'FRESH_OPERATION_VALID_ARTIFACTS_FALSE_STATE_HASH_BLOCKED_BY_INDEPENDENT_PG_READBACK_OK');
      } else {
        child.kill('SIGKILL');await finished;
        const guard=`${project}-ops-run-${live.operation.slice(0,12)}`;
        await docker(['kill','--signal','TERM',guard]);assert.equal((await docker(['wait',guard])).trim(),'0');
        const retained=readFileSync(reportPath);assert.equal(JSON.parse(retained).complete,false);assert.equal(JSON.parse(retained).rto_credited,false);
        const retry=spawnSync(process.execPath,['scripts/platform.mjs','operate','restore-rehearse','--config',host],{cwd:root,encoding:'utf8',timeout:5000});
        assert.equal(retry.status,1);assert.match(retry.stderr,/REHEARSAL_TARGET_REUSE_BLOCKED/);assert.deepEqual(readFileSync(reportPath),retained);
        await docker(['rm','--force',live.probe.name]);await docker(['rm',guard]);
        console.log('KILLED_HOST_PARTIAL_REPORT_RETRY_DENIED_INDEPENDENT_GUARDIAN_REVOKES_RUNTIME_OK');
      }
      assert.equal(await sql("SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')"),'f');
    }
  }finally{
    if(controller && controller.exitCode===null && controller.signalCode===null){controller.kill();await new Promise(done=>controller.once('close',done));}
    await docker(['image','rm',browserImage]);
  }
}
