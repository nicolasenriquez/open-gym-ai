import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { syntheticHarness } from './synthetic-harness.mjs';
import { createDockerNodeControl, drainAndCaptureNode } from './platform-node-drain.mjs';

test('real Docker drain captures admitted writes and refuses live writers or missing drain proof', { timeout: 300_000 }, async t => {
  const root = resolve('.'), temporary = mkdtempSync(join(tmpdir(), 'opengym-drain-docker-'));
  let hostWriter;
  t.after(async () => {
    if (hostWriter && hostWriter.exitCode === null && hostWriter.signalCode === null) {
      const closed = once(hostWriter, 'close'); hostWriter.kill('SIGKILL'); await closed;
    }
    assert(resolve(temporary).startsWith(resolve(tmpdir()) + sep));
    rmSync(temporary, { recursive: true, force: true });
  });
  const data = join(temporary, 'data'), configuration = join(temporary, 'configuration');
  const client = join(temporary, 'client'), unproved = join(temporary, 'unproved');
  for (const dir of [data, configuration, client, unproved]) mkdirSync(dir);
  for (const dir of [data, unproved]) {
    writeFileSync(join(dir, 'db.json'), '{"users":[],"creds":[],"subs":[],"invites":[]}');
    writeFileSync(join(dir, 'secret'), 'c'.repeat(64));
  }
  writeFileSync(join(configuration, 'release.json'), '{"synthetic":true}');
  const sentinel = join(temporary, 'foreign-sentinel'); writeFileSync(sentinel, 'preserve');
  const composeFile = join(temporary, 'compose.json');
  const emptyEnv = join(root, 'backend/empty.env');
  const { docker, compose, runProject } = syntheticHarness({ root, composeFile, emptyEnv,
    namespace: 'opengym-platform-test', label: 'org.opengym.platform', name: 'Docker Node drain',
    services: ['platform-contracts', 'drain-api', 'drain-writer', 'drain-reader', 'drain-unproved', 'drain-client'],
    images: ['platform-contracts'], database: 'platform-db' });
  const fixture = JSON.parse(await docker(['compose', '--project-directory', root, '--env-file', emptyEnv,
    '-f', 'deploy/docker-compose.test.yml', '-p', 'opengym-platform-test-template', 'config', '--format', 'json']));
  delete fixture.name;
  for (const network of Object.values(fixture.networks)) delete network.name;
  for (const volume of Object.values(fixture.volumes)) delete volume.name;
  const base = fixture.services['platform-contracts'];
  base.image = '${COMPOSE_PROJECT_NAME}-platform-contracts:local';
  base.build.labels['com.docker.compose.project'] = '${COMPOSE_PROJECT_NAME}';
  const service = (directory, command) => ({ image: base.image, platform: 'linux/amd64',
    user: process.platform === 'win32' ? 'node' : `${process.getuid()}:${process.getgid()}`, read_only: true, cap_drop: ['ALL'], security_opt: ['no-new-privileges:true'],
    tmpfs: ['/tmp:rw,nosuid,nodev,mode=1777,size=67108864'], restart: 'no',
    networks: ['private'], labels: { 'org.opengym.platform': 'synthetic' },
    entrypoint: ['node'], command, volumes: [{ type: 'bind', source: directory, target: '/data' }],
  });
  fixture.services['drain-api'] = { ...service(data, ['/app/api/server.js']),
    environment: { DATA_DIR: '/data', PORT: '3000', ORIGIN: 'http://localhost:8080',
      PASSWORD_LOGIN: '1', COACH_DISABLED: '1', AUDIT_LOG: '0', NODE_DRAIN_TIMEOUT_MS: '20000' } };
  fixture.services['drain-writer'] = service(data, ['-e', "setInterval(()=>require('fs').writeFileSync('/data/writer-probe','synthetic'),25)"]);
  fixture.services['drain-reader'] = { ...service(data, ['-e', 'setInterval(()=>{},1000)']),
    volumes: [{ type: 'bind', source: data, target: '/data', read_only: true }] };
  fixture.services['drain-unproved'] = service(unproved, ['-e', "process.on('SIGTERM',()=>process.exit(0));console.log('ready');setInterval(()=>{},1000)"]);
  // The independent client survives API exit and records the actual HTTP response.
  const clientCode = `const fs=require('fs'),http=require('http');
    const body=JSON.stringify({name:'Docker in-flight',password:'orchard bicycle summer 42!'});
    const req=http.request('http://drain-api:3000/api/register/password',{method:'POST',headers:{Origin:'http://localhost:8080','Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}},res=>{res.resume();res.on('end',()=>fs.writeFileSync('/data/result.json',JSON.stringify({status:res.statusCode})));});
    req.on('error',()=>{fs.writeFileSync('/data/result.json',JSON.stringify({status:'failed'}));process.exitCode=1});
    req.write(body.slice(0,-1));
    fetch('http://drain-api:3000/api/config').then(r=>{if(r.status!==200)throw Error('not ready');fs.writeFileSync('/data/started','yes');const tick=setInterval(()=>{if(fs.existsSync('/data/release')){clearInterval(tick);req.end(body.slice(-1));}},20);}).catch(()=>process.exit(1));`;
  fixture.services['drain-client'] = service(client, ['-e', clientCode]);
  writeFileSync(composeFile, JSON.stringify(fixture));
  const waitFor = async check => {
    const deadline = Date.now() + 15_000;
    while (!await check()) { if (Date.now() > deadline) throw new Error('Synthetic readiness timeout'); await new Promise(r => setTimeout(r, 50)); }
  };
  await runProject(async (step, project) => {
    const evidence = join(root, '.scratch/s11-node-capture', project); mkdirSync(evidence, { recursive: true });
    await step(['config', '--quiet']); await step(['build', 'platform-contracts']);
    await step(['up', '--detach', '--no-deps', 'drain-api', 'drain-writer', 'drain-reader', 'drain-unproved']);
    const owned = new Set((await docker([...compose(project), 'ps', '--all', '--quiet'])).trim().split(/\s+/));
    const idFor = async name => (await docker([...compose(project), 'ps', '--all', '--quiet', name])).trim();
    const apiId = await idFor('drain-api'), writerId = await idFor('drain-writer');
    const readerId = await idFor('drain-reader'), unprovedId = await idFor('drain-unproved');
    const commands = [];
    let signalSeen;
    const signalled = new Promise(r => { signalSeen = r; });
    const control = createDockerNodeControl(async args => {
      // Restrict only discovery to this owned fixture; every Docker operation is real.
      const actual = args[0] === 'ps' ? [...args, '--filter', `label=com.docker.compose.project=${project}`] : args;
      if (args[0] !== 'ps') {
        const targets = args.filter(v => /^[a-f0-9]{64}$/.test(v));
        assert(targets.length && targets.every(id => owned.has(id)), 'never inspect, signal or log an unowned container');
      }
      commands.push(actual);
      const result = await docker(actual);
      if (args[0] === 'kill' && args.at(-1) === apiId) signalSeen();
      return result;
    });
    await waitFor(async () => (await docker(['logs', '--tail', '5', apiId])).includes('gym-api on :3000'));
    await waitFor(async () => (await docker(['logs', '--tail', '5', unprovedId])).includes('ready'));
    const api = await control.inspect(apiId);
    const sources = [{ name: 'data', path: data }, { name: 'configuration', path: configuration }];
    const destination = join(temporary, 'capture');
    hostWriter = spawn(process.execPath, ['-e', "setInterval(()=>require('fs').writeFileSync(process.argv[1],'host writer'),25)", join(configuration, 'writer')], { windowsHide: true, stdio: 'ignore' });
    const externalWritersStopped = () => hostWriter.exitCode !== null || hostWriter.signalCode !== null;
    const options = { api, sources, destination, externalWritersStopped, timeoutMs: 30_000 };
    await assert.rejects(drainAndCaptureNode(options, control), /NODE_DRAIN_CAPTURE_REJECTED/);
    assert.equal((await control.inspect(apiId)).running, true);
    const hostClosed = once(hostWriter, 'close'); hostWriter.kill('SIGTERM'); await hostClosed;
    await assert.rejects(drainAndCaptureNode(options, control), /NODE_DRAIN_CAPTURE_REJECTED/);
    assert.equal((await control.inspect(apiId)).running, true, 'real RW overlap blocks before signal');
    assert.equal(commands.filter(c => c[0] === 'kill').length, 0);
    await docker(['kill', '--signal', 'SIGKILL', writerId]);
    await assert.rejects(drainAndCaptureNode({ ...options, api: { ...api, image: `sha256:${'f'.repeat(64)}` } }, control), /NODE_DRAIN_CAPTURE_REJECTED/);
    assert.equal(commands.filter(c => c[0] === 'kill').length, 0, 'foreign candidate cannot stop source');
    await step(['up', '--detach', '--no-deps', 'drain-client']); owned.add(await idFor('drain-client'));
    await waitFor(() => existsSync(join(client, 'started')));
    const capture = drainAndCaptureNode(options, control);
    capture.catch(() => {});
    await Promise.race([signalled, capture.then(() => { throw new Error('Capture finished before signal observation'); })]);
    assert.equal((await control.inspect(apiId)).running, true, 'admitted HTTP is still draining');
    assert.equal(existsSync(destination), false);
    writeFileSync(join(client, 'release'), 'finish accepted write');
    const result = await capture;
    await waitFor(() => existsSync(join(client, 'result.json')));
    assert.equal(JSON.parse(readFileSync(join(client, 'result.json'), 'utf8')).status, 200);
    const captured = JSON.parse(readFileSync(join(destination, 'data/db.json'), 'utf8'));
    assert.equal(captured.users[0].name, 'Docker in-flight');
    assert.equal(result.receipt.sourceCutoffAt, result.drain.finishedAt);
    assert.equal(result.cutoverAuthorized, false); assert.equal(result.realGateCompleted, false);
    assert.equal((await control.inspect(apiId)).running, false);
    assert.equal((await control.inspect(readerId)).running, true, 'read-only container is preserved');
    const missingProof = await control.inspect(unprovedId);
    const rejectedDestination = join(temporary, 'unproved-capture');
    await assert.rejects(drainAndCaptureNode({ ...options, api: missingProof,
      sources: [{ name: 'data', path: unproved }, sources[1]], destination: rejectedDestination }, control), /NODE_DRAIN_CAPTURE_REJECTED/);
    assert.equal((await control.inspect(unprovedId)).exitCode, 0, 'exit 0 alone is insufficient');
    assert.equal(existsSync(rejectedDestination), false);
    assert.equal(readFileSync(sentinel, 'utf8'), 'preserve');
    assert(commands.some(c => c[0] === 'kill') && commands.some(c => c[0] === 'logs'));
    writeFileSync(join(evidence, 'result.json'), JSON.stringify({ synthetic: true, realDocker: true,
      admittedWriteCaptured: true, liveHostWriterRejected: true, liveContainerWriterRejected: true,
      foreignCandidateRejected: true, missingDrainProofRejected: true, readOnlyContainerPreserved: true,
      cutoverAuthorized: false, realGateCompleted: false, drain: result.drain }));
    writeFileSync(join(evidence, 'docker-commands.json'), JSON.stringify(commands));
    console.log(`Real Docker evidence: ${evidence}`);
  });
});
