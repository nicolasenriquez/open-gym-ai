import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { syntheticHarness } from './synthetic-harness.mjs';
import { createDockerNodeControl, drainAndCaptureNode } from './platform-node-drain.mjs';

test('real Docker capture enforces the frozen-source drain protocol and refuses live writers or missing proof', { timeout: 300_000 }, async t => {
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
  const unproved = join(temporary, 'unproved');
  for (const dir of [data, configuration, unproved]) mkdirSync(dir);
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
    services: ['platform-client', 'drain-api', 'drain-writer', 'drain-reader', 'drain-unproved'],
    images: ['platform-client'], database: 'platform-db' });
  const fixture = JSON.parse(await docker(['compose', '--project-directory', root, '--env-file', emptyEnv,
    '-f', 'deploy/docker-compose.test.yml', '-p', 'opengym-platform-test-template', 'config', '--format', 'json']));
  delete fixture.name;
  for (const network of Object.values(fixture.networks)) delete network.name;
  for (const volume of Object.values(fixture.volumes)) delete volume.name;
  const base = fixture.services['platform-client'];
  base.image = '${COMPOSE_PROJECT_NAME}-platform-client:local';
  base.build.labels['com.docker.compose.project'] = '${COMPOSE_PROJECT_NAME}';
  const service = (directory, command) => ({ image: base.image, platform: 'linux/amd64',
    user: process.platform === 'win32' ? 'node' : `${process.getuid()}:${process.getgid()}`, read_only: true, cap_drop: ['ALL'], security_opt: ['no-new-privileges:true'],
    tmpfs: ['/tmp:rw,nosuid,nodev,mode=1777,size=67108864'], restart: 'no',
    networks: ['private'], labels: { 'org.opengym.platform': 'synthetic' },
    entrypoint: ['node'], command, volumes: [{ type: 'bind', source: directory, target: '/data' }],
  });
  // Fixture of the preserved release's drain protocol, not another business API.
  fixture.services['drain-api'] = service(data, ['-e', `
    const fs=require('fs');
    process.on('SIGTERM',()=>{const timer=setInterval(()=>{
      if(!fs.existsSync('/data/release'))return;
      clearInterval(timer);
      fs.writeFileSync('/data/db.json',JSON.stringify({users:[{id:'A',name:'Fixture in-flight'}]}));
      process.stdout.write('NODE_DRAINED '+JSON.stringify({version:1,pid:process.pid,finishedAt:new Date().toISOString()})+'\\n',()=>process.exit(0));
    },20);});
    console.log('ready');setInterval(()=>{},1000);
  `]);
  fixture.services['drain-writer'] = service(data, ['-e', "setInterval(()=>require('fs').writeFileSync('/data/writer-probe','synthetic'),25)"]);
  fixture.services['drain-reader'] = { ...service(data, ['-e', 'setInterval(()=>{},1000)']),
    volumes: [{ type: 'bind', source: data, target: '/data', read_only: true }] };
  fixture.services['drain-unproved'] = service(unproved, ['-e', "process.on('SIGTERM',()=>process.exit(0));console.log('ready');setInterval(()=>{},1000)"]);
  writeFileSync(composeFile, JSON.stringify(fixture));
  const waitFor = async check => {
    const deadline = Date.now() + 15_000;
    while (!await check()) { if (Date.now() > deadline) throw new Error('Synthetic readiness timeout'); await new Promise(r => setTimeout(r, 50)); }
  };
  await runProject(async (step, project) => {
    const evidence = join(temporary, 'capture-evidence'); mkdirSync(evidence, { recursive: true });
    await step(['config', '--quiet']); await step(['build', 'platform-client']);
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
    await waitFor(async () => (await docker(['logs', '--tail', '5', apiId])).includes('ready'));
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
    const capture = drainAndCaptureNode(options, control);
    capture.catch(() => {});
    await Promise.race([signalled, capture.then(() => { throw new Error('Capture finished before signal observation'); })]);
    assert.equal((await control.inspect(apiId)).running, true, 'fixture writer is still draining');
    assert.equal(existsSync(destination), false);
    writeFileSync(join(data, 'release'), 'finish fixture write');
    const result = await capture;
    const captured = JSON.parse(readFileSync(join(destination, 'data/db.json'), 'utf8'));
    assert.equal(captured.users[0].name, 'Fixture in-flight');
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
      frozenSourceProtocolVerified: true, liveHostWriterRejected: true, liveContainerWriterRejected: true,
      foreignCandidateRejected: true, missingDrainProofRejected: true, readOnlyContainerPreserved: true,
      cutoverAuthorized: false, realGateCompleted: false, drain: result.drain }));
    writeFileSync(join(evidence, 'docker-commands.json'), JSON.stringify(commands));
    console.log(`Real Docker evidence: ${evidence}`);
  });
});
