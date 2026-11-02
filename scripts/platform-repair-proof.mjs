import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createHmac, createHash } from 'node:crypto';
import { setTimeout as sleep } from 'node:timers/promises';
import { join } from 'node:path';

export async function repairProof(ctx) {
  const { root, temporary, image, docker, config, state, data, compose, composeFile, fault, project, ready } = ctx;
  const sql = async query => (await ctx.sql(query)).trim();
  const release = JSON.parse(await docker(['image', 'inspect', image]))[0].Id;
  const originFiles = ['db.json', 'secret', 'state-A.json', 'state-B.json'];
  const frozen = originFiles.map(name => readFileSync(join(temporary, 'frozen-source', name)));
  const db = (await docker([...compose, 'ps', '-q', 'db'])).trim();
  const tokens = Object.fromEntries(['A', 'B'].map(owner => {
    const payload = `${owner}:${Date.now() + 3600_000}:0`;
    return [owner, `${payload}.${createHmac('sha256', readFileSync(join(temporary, 'session'), 'utf8')).update(payload).digest('base64url')}`];
  }));
  const request = async (owner, method, path, body) => JSON.parse(await docker([...compose, 'exec', '-T', 'api', 'python', '-c', `
import urllib.request,urllib.error,json,hashlib
r=urllib.request.Request('http://127.0.0.1:3000${path}',method='${method}',headers={'Authorization':'Bearer ${tokens[owner]}','Content-Type':'application/json'},data=${body === undefined ? 'None' : `${JSON.stringify(JSON.stringify(body))}.encode()`})
try:
 with urllib.request.urlopen(r) as response: print(json.dumps({'status':response.status,'body':{'sha256':hashlib.sha256(response.read()).hexdigest()} if '/media/' in '${path}' else json.load(response)}))
except urllib.error.HTTPError as e: print(json.dumps({'status':e.code,'body':json.load(e)}))
`]));
  const writes = [];
  for (const [owner, label] of [['A', 'W1'], ['B', 'W2']]) {
    const before = (await request(owner, 'GET', '/api/v1/data')).body;
    const bytes = `${label}-independent-new-media`;
    const hash = createHash('sha256').update(bytes).digest('hex');
    writeFileSync(join(data, 'uploads', owner, `${hash}.jpg`), bytes);
    const payload = { ...before.state, notes: `${label}-independent-receipt`, workouts: [{ id: label, d: '2026-11-02', media: [{ hash }] }] };
    const response = await request(owner, 'PUT', '/api/v1/data', { baseRev: before.rev, state: payload });
    assert.equal(response.status, 200);
    const saved = (await request(owner, 'GET', '/api/v1/data')).body;
    assert.equal(saved.state.notes, `${label}-independent-receipt`);
    assert.deepEqual(saved.state.workouts, payload.workouts);
    assert.equal(saved.state._wid, response.body.wid);
    assert.equal(await sql(`SELECT write_id FROM training.documents WHERE owner_id='${owner}'`), response.body.wid);
    writes.push({ owner, rev: saved.rev, wid: response.body.wid, state: saved.state, media: [{ name: `${hash}.jpg`, sha256: hash }] });
  }
  const witness = join(temporary, 'witness.json');
  writeFileSync(config, JSON.stringify({ ...JSON.parse(readFileSync(config)), repair: { witness_file: witness } }));
  writeFileSync(join(state, 'allow-capture'), '');
  const selected = JSON.parse(readFileSync(composeFile));
  const original = structuredClone(selected);
  const scenarios = fault === 'repair' ? ['image', 'ddl', 'uncertain'] : [fault.slice(7)];
  for (const scenario of scenarios) {
    const incident = `synthetic-${scenario}`;
    const receipts = structuredClone(writes);
    if (scenario === 'missing') receipts.pop();
    if (scenario === 'content') receipts[1].state.notes = 'wrong-independent-expectation';
    if (scenario === 'media') receipts[1].media[0].sha256 = '0'.repeat(64);
    writeFileSync(witness, JSON.stringify({ instance_id: 'synthetic-a', incident, writes: receipts }), { mode: 0o600 });
    let selectedRelease = release;
    if (scenario === 'image' || scenario === 'incompatible') {
      const tag = `${project}-platform-repair:local`, build = join(temporary, 'Dockerfile.repair');
      writeFileSync(build, `FROM ${image}\nRUN ${scenario === 'image' ? 'rm /app/src/opengym_platform/application.py' : "sed -i 's/p004_audit/p999_incompatible/g' /app/src/opengym_platform/application.py"}\n`);
      await docker(['build', '--label', `com.docker.compose.project=${project}`, '--label', 'com.docker.compose.service=platform-repair',
        '--label', 'org.opengym.platform=synthetic', '-t', tag, '-f', build, temporary]);
      if (scenario === 'image') {
        selected.services.api.image = tag;
        writeFileSync(composeFile, JSON.stringify(selected));
        await docker([...compose, 'up', '-d', '--no-deps', '--force-recreate', 'api']);
        for (let i = 0; i < 100; i++) {
          if (!JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running) break;
          await sleep(50);
        }
        assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
      } else selectedRelease = JSON.parse(await docker(['image', 'inspect', tag]))[0].Id;
    }
    if (scenario === 'ddl') {
      await docker([...compose, 'stop', '--timeout', '30', 'api']);
      // Run the real migrator with one test-only failing forward revision.
      const failed = JSON.parse(await docker([...compose, 'run', '--rm', '--no-deps', '--entrypoint', 'python',
        '-e', 'PLATFORM_DB_PASSWORD_FILE=/run/secrets/migrator', 'migrate', '-c', `
import shutil,pathlib,subprocess,sys,os
p=pathlib.Path('/tmp/q2/opengym_platform');shutil.copytree('/app/src/opengym_platform',p)
(p/'platform_migrations/versions/q2_failed.py').write_text("revision='q2_failed'\\ndown_revision='p004_audit'\\nfrom alembic import op\\ndef upgrade():\\n op.execute('CREATE TABLE public.q2_failed_ddl(id int)')\\n op.execute('SELECT 1/0')\\n")
r=subprocess.run([sys.executable,'-m','opengym_platform.platform_migrate','--deployment','up'],env={**os.environ,'PYTHONPATH':'/tmp/q2'},capture_output=True)
assert r.returncode==1 and not r.stderr;print(r.stdout.decode())
`]));
      assert.equal(failed.code, 'PLATFORM_MIGRATION_FAILED');
      assert.equal(await sql("SELECT to_regclass('public.q2_failed_ddl') IS NULL"), 't');
      assert.equal(await sql('SELECT version_num FROM public.alembic_version'), 'p004_audit');
    }
    if (scenario === 'uncertain') {
      // A committed HTTP request whose response is deliberately discarded by the client.
      const payload = { baseRev: writes[0].rev, state: { ...writes[0].state, theme: 'dark' } };
      await docker([...compose, 'exec', '-T', 'api', 'python', '-c', `
import http.client,json
c=http.client.HTTPConnection('127.0.0.1',3000);c.request('PUT','/api/v1/data',${JSON.stringify(JSON.stringify(payload))},{'Authorization':'Bearer ${tokens.A}','Content-Type':'application/json'})
import time;time.sleep(.5)
c.close()
`]);
      const observed = (await request('A', 'GET', '/api/v1/data')).body;
      assert.equal(observed.state.theme, 'dark');
      assert.deepEqual(observed.state.workouts, writes[0].state.workouts);
      assert.equal(observed.state.notes, writes[0].state.notes);
      assert.ok(observed.state._wids.includes(writes[0].wid));
      writes[0] = { ...writes[0], state: observed.state, rev: observed.rev, wid: observed.state._wid };
      writeFileSync(witness, JSON.stringify({ instance_id: 'synthetic-a', incident, writes }), { mode: 0o600 });
    }
    const before = await sql("SELECT jsonb_agg(to_jsonb(t) ORDER BY owner_id) FROM training.documents t");
    const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'operate', 'forward-repair',
      '--config', config, '--incident', incident, '--release', selectedRelease],
    { cwd: root, encoding: 'utf8', timeout: 180_000 });
    assert.equal(result.status, ['missing', 'incompatible', 'content', 'media'].includes(scenario) ? 1 : 0, result.stdout + result.stderr);
    const journal = JSON.parse(readFileSync(join(state, 'journal.json')));
    assert.ok(existsSync(join(state, journal.operation, 'database.dump')));
    assert.equal((await docker([...compose, 'ps', '-q', 'db'])).trim(), db);
    assert.equal(await sql("SELECT jsonb_agg(to_jsonb(t) ORDER BY owner_id) FROM training.documents t"), before);
    for (const [index, name] of originFiles.entries()) assert.deepEqual(readFileSync(join(temporary, 'frozen-source', name)), frozen[index]);
    if (['missing', 'incompatible', 'content', 'media'].includes(scenario)) {
      assert.equal(result.status, 1, result.stdout + result.stderr);
      assert.equal(JSON.parse(readFileSync(join(state, 'gate', 'admission.json'))).allowed, false);
      assert.ok(existsSync(join(state, 'exclusive')));
      assert.equal(JSON.parse(await docker(['inspect', `${project}-api-1`]))[0].State.Running, false);
      console.log(`Q2_${scenario.toUpperCase()}_NO_GO_SURVIVING_WRITES_INTACT_OK`);
      const evidence = join(root, '.scratch', 'repair-10-6');
      mkdirSync(evidence, { recursive: true });
      writeFileSync(join(evidence, `${scenario}.json`), JSON.stringify({ incident, no_go: true, surviving_writes: true, gate_closed: true, synthetic: true }, null, 2));
      continue;
    }
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).code, 'FORWARD_REPAIR_VERIFIED');
    assert.equal(journal.preservation_verified, true);
    assert.equal(existsSync(join(state, 'exclusive')), false);
    writeFileSync(composeFile, JSON.stringify(original));
    Object.assign(selected, structuredClone(original));
    await ready();
    for (const receipt of writes) {
      assert.deepEqual((await request(receipt.owner, 'GET', '/api/v1/data')).body, { state: receipt.state, rev: receipt.rev });
      for (const media of receipt.media) {
        assert.equal(createHash('sha256').update(readFileSync(join(data, 'uploads', receipt.owner, media.name))).digest('hex'), media.sha256);
        assert.deepEqual(await request(receipt.owner, 'GET', `/api/v1/media/${media.sha256}`), { status: 200, body: { sha256: media.sha256 } });
        assert.equal((await request(receipt.owner === 'A' ? 'B' : 'A', 'GET', `/api/v1/media/${media.sha256}`)).status, 404);
      }
    }
    const w3 = await request('A', 'PUT', '/api/v1/data', { baseRev: writes[0].rev, state: { ...writes[0].state, notes: `W3-${scenario}` } });
    assert.equal(w3.status, 200);
    const saved = (await request('A', 'GET', '/api/v1/data')).body;
    assert.equal(saved.state.notes, `W3-${scenario}`);
    assert.equal(saved.state._wid, w3.body.wid);
    assert.equal(await sql("SELECT write_id FROM training.documents WHERE owner_id='A'"), w3.body.wid);
    writes[0] = { ...writes[0], rev: saved.rev, wid: w3.body.wid, state: saved.state };
    assert.equal((await request('A', 'GET', '/api/v1/data?owner_id=B')).body.state._wid, w3.body.wid);
    assert.equal((await request('unauthenticated', 'GET', '/api/v1/data')).status, 401);
    const evidence = join(root, '.scratch', 'repair-10-6');
    mkdirSync(evidence, { recursive: true });
    writeFileSync(join(evidence, `${scenario}.json`), JSON.stringify({ incident, release, operation: journal.operation,
      preservation_verified: true, w3_verified: true, surviving_database: true, synthetic: true }, null, 2));
    console.log(`Q2_${scenario.toUpperCase()}_W1_W2_MEDIA_SURVIVE_AND_W3_HTTP_PG_OK`);
  }
}
