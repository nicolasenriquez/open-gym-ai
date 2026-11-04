// Synthetic seeding only; backup/restore still run their existing operator commands.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
function files(root, prefix = '') {
  return Object.fromEntries(readdirSync(join(root, prefix), { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))
    .flatMap(entry => {
      const path = prefix ? `${prefix}/${entry.name}` : entry.name;
      assert.equal(entry.isSymbolicLink(), false);
      return entry.isDirectory() ? Object.entries(files(root, path)) : [[path, readFileSync(join(root, path))]];
    }));
}

export async function prepareNodeRecoverySource(ctx) {
  const { root, temporary, project, image, docker, compose, sql, data, composeFile, evidence } = ctx;
  const nodeImage = `${project}-platform-contracts:local`;
  await docker(['build', '--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.platform=synthetic',
    '--label', 'com.docker.compose.service=platform-contracts', '-t', nodeImage, '-f', 'backend/Dockerfile.contracts', root], true);
  const produced = await docker([...compose, 'run', '--rm', '--no-deps', 'node-source']);
  writeFileSync(join(evidence, 'node-capture.log'), produced);
  assert.match(produced, /NODE_CHAIN_EXIT_0\b/);
  assert.match(produced, /# pass 1\b/);
  assert.doesNotMatch(produced, /# (?:skipped|todo|cancelled) [1-9]/);
  const source = join(temporary, 'node-source');
  const before = Object.fromEntries(Object.entries(files(source)).map(([path, bytes]) => [path, sha(bytes)]));
  const capture = JSON.parse(readFileSync(join(source, 'capture/capture.json')));
  const expected = JSON.parse(readFileSync(join(source, 'expected.json')));
  assert.equal(capture.sourceCutoffAt, expected.sourceCutoffAt);
  const targets = join(temporary, 'node-targets'); mkdirSync(targets, { mode: 0o700 });
  await sql("COMMENT ON DATABASE opengym_dev IS 'opengym-import:node-chain'; REVOKE CONNECT ON DATABASE opengym_dev FROM opengym_api_runtime");
  const output = await docker([...compose, 'run', '--rm', '--no-deps',
    '--volume', `${join(source, 'capture/data')}:/run/import/source:ro`, '--volume', `${targets}:/run/import/export`,
    '--entrypoint', 'python', 'migrate', '-c', `import json,shutil,subprocess,sys
from pathlib import Path
root=Path('/tmp/node-targets');root.mkdir(mode=0o700)
config=Path('/tmp/node-import.json');config.write_text(json.dumps({'target_id':'node-chain','target_root':str(root),'admin_uids':[]}))
process=subprocess.run([sys.executable,'-m','opengym_platform.operations','import','--config',str(config),'--source','/run/import/source','--target','node-chain'],capture_output=True)
assert process.stderr==b''
if process.returncode==0:shutil.copytree(root/'node-chain','/run/import/export/node-chain')
print(json.dumps({'status':process.returncode,'out':json.loads(process.stdout)}))`]);
  writeFileSync(join(evidence, 'postgres-import.log'), output);
  const imported = JSON.parse(output);
  assert.equal(imported.status, 0, output);
  assert.equal(imported.out.code, 'IMPORT_OK');
  const destination = join(targets, 'node-chain');
  const completion = JSON.parse(readFileSync(join(destination, 'import.json')));
  assert.equal(completion.access, 'quarantined');
  assert.equal((await sql("SELECT has_database_privilege('opengym_api_runtime',current_database(),'CONNECT')")).trim(), 'f');
  assert.equal((await sql('SELECT count(*) FROM identity.users')).trim(), '2');
  for (const user of expected.users) {
    assert.match(user.id, /^[A-Za-z0-9_-]+$/);
    const actual = JSON.parse((await sql(`SELECT document FROM training.documents WHERE owner_id='${user.id}'`)).trim());
    assert.deepEqual(actual, JSON.parse(readFileSync(join(source, `capture/data/state-${user.id}.json`))));
    assert.equal(actual.workouts[0].id, user.workout);
    assert.equal(actual._rev, user.rev);
  }
  cpSync(join(destination, 'data'), data, { recursive: true, force: false, errorOnExist: true });
  for (const [from, to] of [['session-secret', 'session'], ['coach-secret', 'coach']]) {
    const secret = readFileSync(join(destination, from));
    assert.deepEqual(secret, readFileSync(join(source, 'capture/data/secret')));
    writeFileSync(join(temporary, to), secret, { mode: 0o600 });
  }
  const expectedFiles = files(data);
  const medium = `uploads/${expected.users[0].id}/${expected.hash}.jpg`;
  assert.deepEqual(expectedFiles[medium], Buffer.from(expected.mediaHex, 'hex'));
  const lineage = { version: 1, synthetic: true, sourceCutoffAt: capture.sourceCutoffAt,
    nodeCapturedAt: capture.capturedAt, importedAt: new Date().toISOString(), sourceSha256: completion.source_sha256,
    captureSha256: sha(readFileSync(join(source, 'capture/capture.json'))),
    nodeImage: JSON.parse(await docker(['image', 'inspect', nodeImage]))[0].Id,
    pythonImage: JSON.parse(await docker(['image', 'inspect', image]))[0].Id };
  const lineageFile = join(temporary, 'node-lineage.json');
  writeFileSync(lineageFile, JSON.stringify(lineage), { mode: 0o600 });
  writeFileSync(join(evidence, 'lineage.json'), JSON.stringify(lineage));
  const model = JSON.parse(readFileSync(composeFile));
  for (const [path, name] of [[lineageFile, 'node-lineage'], [join(source, 'capture/capture.json'), 'node-capture'],
    [join(source, 'capture/configuration/release.json'), 'node-release']]) {
    model.services.migrate.volumes.push({ type: 'bind', source: path, target: `/run/operator/${name}.json`, read_only: true });
  }
  writeFileSync(composeFile, JSON.stringify(model));
  // Only this private fixture may start its source runtime for the real maintenance wrapper.
  await sql('GRANT CONNECT ON DATABASE opengym_dev TO opengym_api_runtime');
  return { expectedFiles, owners: expected.users, sessionHash: sha(readFileSync(join(temporary, 'session'))),
    coachHash: sha(readFileSync(join(temporary, 'coach'))), lineageHash: sha(readFileSync(lineageFile)),
    verifyNodeSource() {
      assert.deepEqual(Object.fromEntries(Object.entries(files(source)).map(([path, bytes]) => [path, sha(bytes)])), before);
    } };
}
