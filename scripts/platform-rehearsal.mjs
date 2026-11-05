// Host-only coordinator. An incomplete report is never authority to admit traffic.
import { mkdirSync, readFileSync, existsSync, lstatSync } from 'node:fs';
import { isAbsolute, join } from 'node:path';
import { createHash, randomBytes } from 'node:crypto';
import { setTimeout as sleep } from 'node:timers/promises';
import { docker, safePath, fileProof, operatorPrivate, journalWrite } from './platform-maintenance.mjs';

function privateInput(path) {
  safePath(path); operatorPrivate(path);
  if (process.platform!=='win32' && lstatSync(path).uid!==process.getuid()) throw new Error('REHEARSAL_INPUT_OWNER_INVALID');
  const proof=fileProof(path), bytes=readFileSync(path);
  if (createHash('sha256').update(bytes).digest('hex')!==proof.sha256) throw new Error('REHEARSAL_INPUT_CHANGED');
  return {value:JSON.parse(bytes),proof};
}

export async function rehearse(options) {
  if (options.length !== 2 || options[0] !== '--config' || !isAbsolute(options[1])) {
    process.exitCode = 2;
    throw new Error('REHEARSAL_ARGUMENTS_INVALID');
  }
  let config, inputProof;
  const started = Date.now(), monotonic = performance.now();
  try {
    const loaded=privateInput(options[1]);config=loaded.value;inputProof=loaded.proof;
    const keys = ['instance_id','project','project_directory','compose_files','env_file','state_root','bundle','incident_at','review_file'];
    if (Object.keys(config).some(key => ![...keys,'runtime_image','verification_file'].includes(key)) || keys.some(key => !Object.hasOwn(config,key))
      || !/^[a-z0-9][a-z0-9-]{0,47}$/.test(config.instance_id)
      || !/^[a-z][a-z0-9-]{1,63}$/.test(config.project) || !/^[a-f0-9]{32}$/.test(config.bundle)
      || !['project_directory','env_file','state_root','review_file'].every(key => typeof config[key] === 'string' && isAbsolute(config[key]))
      || !Array.isArray(config.compose_files) || !config.compose_files.length
      || !config.compose_files.every(path => typeof path === 'string' && isAbsolute(path))
      || typeof config.incident_at !== 'string' || !config.incident_at.endsWith('Z')
      || !Number.isFinite(Date.parse(config.incident_at)) || Date.parse(config.incident_at) > started
      || (config.runtime_image !== undefined && !/^sha256:[a-f0-9]{64}$/.test(config.runtime_image))
      || (config.verification_file !== undefined && (typeof config.verification_file !== 'string' || !isAbsolute(config.verification_file)))) throw new Error();
    safePath(config.project_directory,true); safePath(config.state_root,true); operatorPrivate(config.state_root);
    if (process.platform!=='win32' && lstatSync(config.state_root).uid!==process.getuid()) throw new Error();
    for (const path of [config.env_file,...config.compose_files]) safePath(path);
  } catch {
    process.exitCode = 2;
    throw new Error('REHEARSAL_CONFIG_INVALID');
  }
  const root = join(config.state_root, config.instance_id);
  try { mkdirSync(root, { mode: 0o700 }); }
  catch { throw new Error('REHEARSAL_TARGET_REUSE_BLOCKED'); }
  const report = { version: 1, operation: randomBytes(16).toString('hex'), target: config.instance_id,
    bundle: config.bundle, incident_at: config.incident_at, started_at: new Date(started).toISOString(),
    complete: false, rto_credited: false, access: 'not_admitted', phase: 'preflight',
    scope:'isolated-data-new-password-and-client-reconciliation',
    exclusions:['public-traffic','real-identity-and-device-acceptance','physical-storage','historical-credential-continuity','account-purge','external-delivery'],
    timings_ms: { preparation_including_review: started-Date.parse(config.incident_at) },
    snapshot_at: null, rpo_ms: null, rpo_met: null, rto_met: false, elapsed_ms: 0,
    objectives_ms: {rpo:6*3600_000,rto:24*3600_000}, host:{os:process.platform,arch:process.arch,node:process.version} };
  const elapsed = () => Math.max(Date.now()-Date.parse(config.incident_at), report.timings_ms.preparation_including_review+performance.now()-monotonic);
  const save = () => {
    report.elapsed_ms = elapsed();
    journalWrite(root, report, 'report.json');
  };
  save();
  const prefix = ['compose','--project-directory',config.project_directory,'--env-file',config.env_file,
    '-p',config.project,...config.compose_files.flatMap(path => ['-f',path])];
  const run = (args, timeout=30_000) => docker([...prefix,...args],config.project_directory,timeout);
  let guardian, api;
  const probeArgs = command => ['python','-m','opengym_platform.rehearsal',command,'/run/operator/restore.json',config.instance_id];
  const status = async (stopped=false) => JSON.parse(stopped
    ? await run(['run','--rm','--no-deps','ops',...probeArgs('status').slice(1)])
    : await docker(['exec',guardian,...probeArgs('status')],config.project_directory));
  try {
    const model = JSON.parse(await run(['--profile','*','config','--format','json']));
    if (Object.keys(model.services).sort().join(',') !== 'bootstrap,db,migrate,ops'
      || Object.values(model.networks).some(network => network.internal !== true)
      || Object.values(model.services).some(service => service.ports?.length || service.privileged || service.cap_add?.length
        || !service.read_only || service.restart !== 'no' || service.logging?.driver !== 'none'
        || Object.keys(service.networks ?? {}).some(name => !model.networks[name]?.internal)
        || service.volumes?.some(mount => mount.target.includes('docker.sock')))
      || !/^[1-9][0-9]*:[1-9][0-9]*$/.test(model.services.ops.user ?? '')
      || !/^sha256:[a-f0-9]{64}$/.test(model.services.ops.image)) throw new Error('REHEARSAL_ISOLATION_REQUIRED');
    report.images = {ops:model.services.ops.image,runtime:config.runtime_image ?? null,database:model.services.db.image};
    if (config.runtime_image && JSON.parse(await docker(['image','inspect',config.runtime_image],config.project_directory))[0].Id!==config.runtime_image) throw new Error('REHEARSAL_RUNTIME_IMAGE_UNAVAILABLE');
    const databaseId = (await run(['ps','--quiet','db'])).trim();
    if (!/^[a-f0-9]{64}$/.test(databaseId)) throw new Error('REHEARSAL_DATABASE_NOT_READY');
    const database = JSON.parse(await docker(['inspect',databaseId],config.project_directory))[0];
    const networkState = JSON.parse(await docker(['network','inspect',model.networks.private.name],config.project_directory))[0];
    if (!database.State.Running || database.State.Health?.Status!=='healthy'
      || database.Config.Labels['com.docker.compose.project']!==config.project
      || Object.values(database.HostConfig.PortBindings ?? {}).some(ports=>ports?.length)
      || database.HostConfig.Privileged || !database.HostConfig.ReadonlyRootfs || database.HostConfig.CapAdd?.length
      || Object.keys(database.NetworkSettings.Networks).join(',')!==model.networks.private.name
      || networkState.Internal!==true || Object.keys(networkState.Containers ?? {}).some(id=>id!==databaseId)
      || database.Image!==JSON.parse(await docker(['image','inspect',model.services.db.image],config.project_directory))[0].Id) throw new Error('REHEARSAL_LIVE_ISOLATION_REQUIRED');
    const mark = performance.now();
    report.phase = 'restoring'; save();
    const result = JSON.parse(await run(['run','--rm','--no-deps','ops','-m','opengym_platform.operations','restore',
      '--config','/run/operator/restore.json','--bundle',config.bundle,'--target',config.instance_id],300_000));
    if (result.code !== 'RESTORE_QUARANTINED') throw new Error('REHEARSAL_RESTORE_FAILED');
    report.timings_ms.restore = performance.now()-mark;
    report.access = 'quarantined';
    const metadata = JSON.parse(await run(['run','--rm','--no-deps','ops','-c',
      "import json,sys;from pathlib import Path;p=Path('/data')/sys.argv[1];r=json.loads((p/'restore.json').read_text());m=json.loads((p/'manifest.json').read_text());print(json.dumps({'snapshot_at':r['snapshot_at'],'bytes':sum(f.get('size',0) for f in m['files']),'timings_ms':r['timings_ms']}))",config.instance_id]));
    report.snapshot_at = metadata.snapshot_at;
    report.size_bytes = metadata.bytes;
    report.restore_phases_ms = metadata.timings_ms;
    report.rpo_ms = Date.parse(config.incident_at)-Date.parse(metadata.snapshot_at);
    report.rpo_met = Number.isFinite(report.rpo_ms) && report.rpo_ms >= 0 && report.rpo_ms <= 6*3600_000;
    report.phase = 'review_pending'; save();
    if (!existsSync(config.review_file)) return;
    safePath(config.review_file); operatorPrivate(config.review_file);
    if (lstatSync(config.review_file).mtimeMs < Date.parse(config.incident_at)) throw new Error('REHEARSAL_REVIEW_PREDATES_INCIDENT');
    const loadedReview=privateInput(config.review_file);
    const review=loadedReview.value,reviewProof=loadedReview.proof;
    const reviewStart = performance.now();
    report.phase = 'reviewing'; save();
    const recovered = JSON.parse(await run(['run','--rm','--no-deps','--volume',`${config.review_file}:/run/review-source.json:ro`,
      'ops','-c',"import hashlib,subprocess,sys;from pathlib import Path;from opengym_platform.restore_access import exclusive;source=Path('/run/review-source.json').read_bytes();assert hashlib.sha256(source).hexdigest()==sys.argv[2];p=Path('/data')/sys.argv[1]/'review-input.json';exclusive(p,source);raise SystemExit(subprocess.run([sys.executable,'-m','opengym_platform.operations','restore-access-recover','--config','/run/operator/restore.json','--target',sys.argv[1],'--review',str(p)]).returncode)",
      config.instance_id,reviewProof.sha256],60_000));
    if (recovered.code !== 'RESTORE_ACCESS_REVIEWED' || fileProof(config.review_file).sha256 !== reviewProof.sha256) throw new Error('REHEARSAL_REVIEW_FAILED');
    report.reviewed = true;
    report.review_sha256 = reviewProof.sha256;
    report.blocked_accesses = review.accounts.filter(account => account.decision === 'block').length;
    report.unresolved_accesses = review.accounts.filter(account => account.status === 'unknown').length;
    report.timings_ms.access_recovery = performance.now()-reviewStart;
    report.phase = 'verification_pending'; save();
    if (!config.runtime_image) return;
    const verifyStart = performance.now();
    guardian = (await run(['run','--detach','--no-deps','-e',`PLATFORM_REHEARSAL_OPERATION=${report.operation}`,'--name',`${config.project}-ops-run-${report.operation.slice(0,12)}`,
      'ops','-m','opengym_platform.rehearsal','watch','/run/operator/restore.json',config.instance_id])).trim();
    if (!/^[a-f0-9]{64}$/.test(guardian)) throw new Error('REHEARSAL_GUARDIAN_UNCERTAIN');
    for (let attempt=0;;attempt++) {
      if ((await status()).ready?.ready) break;
      if (attempt===50) throw new Error('REHEARSAL_GUARDIAN_NOT_READY');
      await sleep(100);
    }
    const volume = model.volumes['restore-data'].name;
    const network = model.networks.private.name;
    const apiName = `${config.project}-api-run-${report.operation.slice(0,12)}`;
    report.probe = { name:apiName, network, volume, client_subpath:`${config.instance_id}/rehearsal/client` };
    const environment = {PLATFORM_ENV:'ops',PLATFORM_DB_MODE:'local_compose',PLATFORM_DB_HOST:'db',PLATFORM_DB_PORT:'5432',
      PLATFORM_DB_NAME:'opengym',PLATFORM_DB_TLS:'disable',PLATFORM_DB_PASSWORD_FILE:'/run/secrets/runtime',
      PLATFORM_SESSION_SECRET_FILE:'/run/secrets/session-secret',PLATFORM_COACH_SECRET_FILE:'/run/secrets/coach-secret',
      PLATFORM_INSTANCE_ID:config.instance_id,PLATFORM_MAINTENANCE_GATE_DIR:'/run/secrets/gate',DATA_DIR:'/data',
      PASSWORD_LOGIN:'1',COACH_DISABLED:'1',MEDIA_UPLOADS:'1',DEFAULT_LANG:'es',RP_ID:'localhost',ORIGIN:'http://localhost:8080'};
    api = (await docker(['run','--detach','--name',apiName,'--network',network,'--network-alias','rehearsal-api',
      '--read-only','--user',model.services.ops.user,'--cap-drop','ALL','--security-opt','no-new-privileges:true',
      '--log-driver','none','--tmpfs','/tmp:rw,noexec,nosuid,nodev,mode=1777,size=67108864',
      '--label',`com.docker.compose.project=${config.project}`,'--label','com.docker.compose.service=api',
      '--label',`org.opengym.platform=${model.services.db.labels?.['org.opengym.platform']==='synthetic'?'synthetic':'rehearsal'}`,'--label',`org.opengym.rehearsal.operation=${report.operation}`,
      '--mount',`type=volume,source=${volume},target=/run/secrets,volume-subpath=${config.instance_id}/rehearsal/keys,readonly`,
      '--mount',`type=volume,source=${volume},target=/data,volume-subpath=${config.instance_id}/data`,
      ...Object.entries(environment).flatMap(([key,value]) => ['-e',`${key}=${value}`]),
      '--entrypoint','timeout',config.runtime_image,'240','python','-m','uvicorn','opengym_platform.application:create_app',
      '--factory','--host','0.0.0.0','--port','3000','--no-access-log','--no-proxy-headers'],config.project_directory)).trim();
    if (!/^[a-f0-9]{64}$/.test(api)) throw new Error('REHEARSAL_API_UNCERTAIN');
    for (let attempt=0;;attempt++) {
      const current = await status();
      if (current.checks) { report.checks=current.checks; break; }
      if (current.closed || attempt===100) throw new Error('REHEARSAL_CHECK_FAILED');
      await sleep(100);
    }
    report.phase = 'client_verification'; save();
    if (config.verification_file) {
      for (let attempt=0; !existsSync(config.verification_file); attempt++) {
        if (attempt===360) throw new Error('REHEARSAL_CLIENT_TIMEOUT');
        await sleep(500);
      }
      const loadedEvidence=privateInput(config.verification_file);
      const evidence=loadedEvidence.value;
      const required = ['dirty_preserved','lineage_reconciled','lost_reply_reconciled','persisted'];
      if (evidence.operation !== report.operation || evidence.target !== config.instance_id || evidence.bundle !== config.bundle || evidence.completed !== true
        || required.some(key => evidence.checks?.[key] !== true) || !Array.isArray(evidence.artifacts) || !evidence.artifacts.length
        || lstatSync(config.verification_file).mtimeMs < Date.parse(config.incident_at)) throw new Error('REHEARSAL_CLIENT_EVIDENCE_INVALID');
      for (const artifact of evidence.artifacts) {
        if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,100}$/.test(artifact.name) || !/^[a-f0-9]{64}$/.test(artifact.sha256)) throw new Error('REHEARSAL_CLIENT_ARTIFACT_INVALID');
        const path = join(config.verification_file,'..',artifact.name);
        safePath(path); operatorPrivate(path);
        if (fileProof(path).sha256 !== artifact.sha256) throw new Error('REHEARSAL_CLIENT_ARTIFACT_CHANGED');
      }
      const confirmed=JSON.parse(await run(['run','--rm','--no-deps','--volume',`${config.verification_file}:/run/client-evidence.json:ro`,
        'ops','-m','opengym_platform.rehearsal','confirm','/run/operator/restore.json',config.instance_id,loadedEvidence.proof.sha256]));
      if (!confirmed.persisted || fileProof(config.verification_file).sha256!==loadedEvidence.proof.sha256) throw new Error('REHEARSAL_CLIENT_PERSISTENCE_FAILED');
      report.client = { mode:'operator-evidence-and-pg-observation', sha256:loadedEvidence.proof.sha256 };
    }
    report.timings_ms.verification = performance.now()-verifyStart;
    report.phase = 'verification_pending';
    report.complete = Boolean(report.client && report.unresolved_accesses===0 && report.rpo_ms>=0);
    if (report.complete) report.phase='checked';
  } catch {
    report.failure = 'REHEARSAL_BLOCKED';
  } finally {
    try {
      report.closed = Boolean(report.snapshot_at);
      if (api) await docker(['rm','--force',api],config.project_directory);
      if (guardian) {
        await docker(['exec',guardian,...probeArgs('stop')],config.project_directory);
        const code=(await docker(['wait',guardian],config.project_directory,20_000)).trim();
        if (code!=='0' || !(await status(true)).closed?.closed) {
          report.complete=false; report.closed=false; report.failure='REHEARSAL_CLOSE_UNVERIFIED';
        } else await docker(['rm',guardian],config.project_directory);
      }
    } catch { report.complete=false; report.closed=false; report.failure='REHEARSAL_CLOSE_UNVERIFIED'; }
    if (fileProof(options[1]).sha256 !== inputProof.sha256) { report.complete=false; report.rto_credited=false; report.failure='REHEARSAL_CONFIG_CHANGED'; }
    report.elapsed_ms = elapsed();
    report.rto_met = report.complete && report.elapsed_ms<=24*3600_000;
    report.rto_credited = report.rto_met;
    report.operational_acceptance = false;
    report.finished_at = new Date().toISOString();
    save();
    const passed = report.complete && report.rpo_met && report.rto_met;
    const code = passed ? 'REHEARSAL_VERIFIED' : report.complete ? 'REHEARSAL_OBJECTIVE_FAILED' : 'REHEARSAL_INCOMPLETE';
    process.exitCode = passed ? 0 : 1;
    console.log(JSON.stringify({ code, target: config.instance_id, complete: report.complete, access: report.access }));
  }
}
