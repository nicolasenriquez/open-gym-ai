import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, symlinkSync, linkSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const coverage = {
  G0: ['clients_origins', 'client_pending_active_media', 'frontend_api_mapping', 'physical_backup_keys', 'protected_later_access_source', 'rehearsed_window'],
  G1: ['target_environment', 'pool_lifecycle', 'roles_rls_transactions', 'migrations_lock_interrupt', 'backup_restore'],
  GP: ['capability_parity_q6', 'frontend_offline_sync', 'security_audit', 'module_contracts'],
  GO: ['clean_checkout_images_ci', 'runtime_environments', 'restore_rpo_rto', 'diagnostics_privacy_retention', 'forward_repair_new_writes'],
};

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'opengym-gates-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'artifacts'));
  const content = 'Synthetic proof only; no operational acceptance.\n';
  writeFileSync(join(root, 'artifacts/proof.txt'), content);
  const index = {
    version: 1, case: 'pre_cutover', synthetic: true, instance: 'synthetic-instance',
    revision: 'a'.repeat(40), digest: `sha256:${'b'.repeat(64)}`, platform: 'linux/amd64',
    artifactRoot: 'artifacts', artifacts: [{ path: 'proof.txt', sha256: createHash('sha256').update(content).digest('hex') }],
    review: 'proof.txt', authorization: 'proof.txt',
    gates: Object.entries(coverage).map(([gate, names]) => ({ gate, checks: names.map(name => ({
      name, result: 'passed', skipped: 0, command: 'synthetic independent check',
      scope: 'synthetic instance only', limitations: 'No physical devices or production proof',
      binding: { instance: 'synthetic-instance', revision: 'a'.repeat(40), digest: `sha256:${'b'.repeat(64)}`, platform: 'linux/amd64' },
      ev: ['EV-01'], artifacts: ['proof.txt'],
    })) })),
  };
  const f = { root, index, artifact(path, value) {
    const bytes = JSON.stringify(value);
    writeFileSync(join(root, 'artifacts', path), bytes);
    index.artifacts = index.artifacts.filter(entry => entry.path !== path);
    index.artifacts.push({ path, sha256: createHash('sha256').update(bytes).digest('hex') });
  }, run() {
    writeFileSync(join(root, 'index.json'), JSON.stringify(index));
    return spawnSync(process.execPath, ['scripts/platform.mjs', 'verify', 'gates', '--case', 'pre_cutover', '--evidence', join(root, 'index.json')], {
      encoding: 'utf8', timeout: 10_000,
      env: { ...process.env, PATH: '', COMPOSE_FILE: 'foreign.yml', DOCKER_HOST: 'invalid://must-not-contact' },
    });
  } };
  for (const gate of index.gates) for (const check of gate.checks) {
    check.provenance = { ...check.binding, observedAt: '2026-11-01T12:00:00.000Z' };
  }
  releaseFixture(f);
  recoveryFixture(f);
  return f;
}

function releaseFixture(f) {
  const manifest = {
    version: 1, binding: { ...f.index.gates[0].checks[0].binding },
    contentIdentity: `sha256:${'c'.repeat(64)}`, schemaHead: 'p005_subscriptions',
    images: ['api', 'web', 'postgres', 'migrate', 'ops', 'collector'].map(role => ({
      role, digest: f.index.digest, platform: 'linux/amd64', sourceIdentity: 'synthetic pinned source and lock',
    })),
  };
  f.index.releaseManifest = 'release.json';
  f.artifact('release.json', manifest);
  return manifest;
}

function recoveryFixture(f) {
  f.index.recovery = {
    sourceType: 'node_json', sourceCutoffAt: '2026-11-01T06:00:00.000Z',
    capturedAt: '2026-11-01T06:05:00.000Z', importedAt: '2026-11-01T07:00:00.000Z', report: 'rehearsal.json',
  };
  const report = {
    version: 1, binding: { ...f.index.gates[0].checks[0].binding },
    complete: true, closed: true, reviewed: true, unresolved_accesses: 0, operational_acceptance: false,
    snapshot_at: '2026-11-01T11:00:00.000Z', incident_at: '2026-11-01T12:00:00.000Z',
    started_at: '2026-11-01T12:01:00.000Z', finished_at: '2026-11-02T12:00:00.000Z',
    elapsed_ms: 86_400_000, rpo_ms: 3_600_000, rpo_met: true, rto_met: true, rto_credited: true,
    objectives_ms: { rpo: 21_600_000, rto: 86_400_000 },
  };
  f.artifact('rehearsal.json', report);
  f.index.gates.find(g => g.gate === 'GO').checks.find(c => c.name === 'restore_rpo_rto').artifacts = ['proof.txt', 'rehearsal.json'];
  return report;
}

test('pre_cutover requires a complete release manifest bound to the candidate', t => {
  const f = fixture(t);
  const manifest = releaseFixture(f);
  assert.equal(f.run().status, 0);
  delete f.index.releaseManifest;
  assert.equal(f.run().status, 1, 'an API digest alone cannot identify the release');
  f.index.releaseManifest = 'release.json';
  const mutations = [
    m => { m.binding.revision = 'd'.repeat(40); },
    m => { delete m.contentIdentity; },
    m => { m.schemaHead = ''; },
    m => { m.images.pop(); },
    m => { m.images.push(m.images[0]); },
    m => { m.images[0].digest = `sha256:${'d'.repeat(64)}`; },
    m => { m.images[1].digest = 'web:latest'; },
    m => { m.images[1].platform = 'linux/arm64'; },
    m => { m.images[1].sourceIdentity = ''; },
  ];
  for (const mutate of mutations) {
    const changed = structuredClone(manifest);
    mutate(changed);
    f.artifact('release.json', changed);
    assert.equal(f.run().status, 1, mutate.toString());
  }
});

test('pre_cutover reads synthetic evidence without Docker and never authorizes a cutover', t => {
  const f = fixture(t);
  const result = f.run();
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {
    code: 'PLATFORM_GATE_STRUCTURE_OK', case: 'pre_cutover', synthetic: true,
    manualReviewRequired: true, cutoverAuthorized: false, realGateCompleted: false,
  });
  f.index.synthetic = false;
  const claimedOperational = JSON.parse(f.run().stdout);
  assert.equal(claimedOperational.synthetic, false);
  assert.equal(claimedOperational.realGateCompleted, false);
  assert.equal(claimedOperational.cutoverAuthorized, false);
});

test('pre_cutover retains original proof identity and requires review before reusing foreign evidence', t => {
  const f = fixture(t);
  for (const gate of f.index.gates) for (const check of gate.checks) {
    check.provenance = { ...check.binding, observedAt: '2026-11-01T12:00:00.000Z' };
  }
  assert.equal(f.run().status, 0);
  const check = f.index.gates[0].checks[0];
  delete check.provenance;
  assert.equal(f.run().status, 1, 'candidate binding does not supply original provenance');
  check.provenance = { ...check.binding, revision: 'd'.repeat(40), observedAt: '2026-11-01T12:00:00.000Z' };
  assert.equal(f.run().status, 1, 'a different source revision needs applicability review');
  check.applicability = 'missing.txt';
  assert.equal(f.run().status, 1);
  check.applicability = 'proof.txt';
  assert.equal(f.run().status, 0);
  assert.equal(JSON.parse(readFileSync(join(f.root, 'index.json'), 'utf8')).gates[0].checks[0].provenance.revision, 'd'.repeat(40));
  for (const observedAt of ['yesterday', '2026-02-30T12:00:00.000Z', '', null]) {
    check.provenance.observedAt = observedAt;
    assert.equal(f.run().status, 1);
  }
});

test('pre_cutover uses the original data cutoff and complete rehearsal time for recovery objectives', t => {
  const f = fixture(t);
  const report = recoveryFixture(f);
  assert.equal(f.run().status, 0, 'inclusive RPO 6h / RTO 24h boundaries');
  const recovery = structuredClone(f.index.recovery);
  delete f.index.recovery;
  assert.equal(f.run().status, 1, 'a passed check alone does not supply recovery timing');
  f.index.recovery = structuredClone(recovery);
  f.index.recovery.sourceCutoffAt = '2026-11-01T05:59:59.999Z';
  assert.equal(f.run().status, 1, 'a fresh Python snapshot cannot rejuvenate old Node data');
  for (const mutate of [
    r => { r.complete = false; }, r => { r.closed = false; },
    r => { r.reviewed = false; }, r => { r.unresolved_accesses = 1; },
    r => { r.binding.digest = `sha256:${'d'.repeat(64)}`; },
    r => { r.finished_at = '2026-11-02T12:00:00.001Z'; r.elapsed_ms++; },
    r => { r.elapsed_ms = 1; }, r => { r.elapsed_ms++; },
    r => { r.rpo_ms = 0; }, r => { r.rto_credited = false; },
    r => { r.objectives_ms.rpo *= 2; },
    r => { r.started_at = '2026-11-01T11:59:00.000Z'; },
    r => { r.snapshot_at = '2026-11-01T12:00:00.001Z'; },
  ]) {
    f.index.recovery = structuredClone(recovery);
    const changed = structuredClone(report);
    mutate(changed);
    f.artifact('rehearsal.json', changed);
    assert.equal(f.run().status, 1, mutate.toString());
  }
  f.artifact('rehearsal.json', report);
  f.index.recovery = structuredClone(recovery);
  f.index.recovery.importedAt = '2026-11-01T11:00:00.001Z';
  assert.equal(f.run().status, 1, 'import cannot postdate the restored snapshot');
  f.index.recovery.importedAt = null;
  assert.equal(f.run().status, 1, 'Node source needs its import time');
  f.index.recovery.sourceType = 'python_postgresql';
  assert.equal(f.run().status, 0, 'native Python source has no Node import');
  f.index.recovery.sourceType = 'unknown';
  assert.equal(f.run().status, 1);
});

test('pre_cutover rejects missing proof, skipped checks, foreign bindings and missing human references', t => {
  const f = fixture(t);
  const original = structuredClone(f.index);
  const mutations = [
    i => { i.gates.pop(); },
    i => { i.gates[0].checks.pop(); },
    i => { i.gates[0].checks[0].result = 'failed'; },
    i => { i.gates[0].checks[0].skipped = 1; },
    i => { i.gates[0].checks[0].binding.digest = `sha256:${'c'.repeat(64)}`; },
    i => { delete i.authorization; },
    i => { i.review = 'missing.txt'; },
    i => { i.artifacts[0].sha256 = '0'.repeat(64); },
    i => { i.gates[0].checks[0].command = ''; },
    i => { i.gates[0].checks[0].ev = []; },
    i => { i.gates[0].checks[0].artifacts = ['missing.txt']; },
    i => { i.gates[1] = i.gates[0]; },
    i => { i.artifacts.push(i.artifacts[0]); },
    i => { i.gates[0].checks[0].scope = ''; },
    i => { delete i.synthetic; },
  ];
  for (const mutate of mutations) {
    Object.assign(f.index, structuredClone(original));
    mutate(f.index);
    const result = f.run();
    assert.equal(result.status, 1, mutate.toString());
    assert.equal(result.stdout, '');
    assert.equal(result.stderr.trim(), 'PLATFORM_GATE_EVIDENCE_REJECTED');
  }
});

test('pre_cutover refuses escaped paths, links and excessive files without exposing their content', t => {
  const f = fixture(t);
  const marker = 'PRIVATE_MARKER_MUST_NOT_BE_PRINTED';
  writeFileSync(join(f.root, 'outside.txt'), marker);
  const sha = createHash('sha256').update(marker).digest('hex');
  const select = path => {
    f.index.artifacts = f.index.artifacts.filter(entry => entry.path === f.index.releaseManifest || entry.path === f.index.recovery.report);
    f.index.artifacts.push({ path, sha256: sha });
    f.index.review = f.index.authorization = path;
    for (const gate of f.index.gates) for (const check of gate.checks) {
      check.artifacts = [path, f.index.recovery.report];
    }
  };
  writeFileSync(join(f.root, 'artifacts/ordinary.txt'), marker);
  select('ordinary.txt');
  assert.equal(f.run().status, 0, 'all unrelated evidence remains valid for path rejection tests');
  for (const path of ['../outside.txt', join(f.root, 'outside.txt'), '..\\outside.txt']) {
    select(path);
    assert.equal(f.run().status, 1, path);
  }
  f.index.artifactRoot = '..';
  select('outside.txt');
  assert.equal(f.run().status, 1);
  f.index.artifactRoot = 'artifacts';
  mkdirSync(join(f.root, 'external'));
  writeFileSync(join(f.root, 'external/private.txt'), marker);
  symlinkSync(join(f.root, 'external'), join(f.root, 'artifacts/linked'), process.platform === 'win32' ? 'junction' : 'dir');
  select('linked/private.txt');
  assert.equal(f.run().status, 1);
  linkSync(join(f.root, 'outside.txt'), join(f.root, 'artifacts/hardlink.txt'));
  select('hardlink.txt');
  assert.equal(f.run().status, 1);
  const large = Buffer.alloc(4 * 1024 * 1024 + 1);
  writeFileSync(join(f.root, 'artifacts/large.txt'), large);
  select('large.txt');
  f.index.artifacts.find(entry => entry.path === 'large.txt').sha256 = createHash('sha256').update(large).digest('hex');
  const result = f.run();
  assert.equal(result.status, 1);
  assert.doesNotMatch(result.stdout + result.stderr, new RegExp(marker));
});

test('pre_cutover rejects malformed, missing and oversized indexes and never runs evidence commands', t => {
  const f = fixture(t);
  const sentinel = join(f.root, 'must-not-exist.txt');
  f.index.gates[0].checks[0].command = `node -e "require('fs').writeFileSync('${sentinel.replaceAll('\\', '/')}', 'bad')"`;
  f.index.config = join(f.root, 'missing-private-config.json');
  assert.equal(f.run().status, 0);
  assert.equal(existsSync(sentinel), false);
  for (const content of ['{', 'null', '{}', JSON.stringify({ ...f.index, padding: ' '.repeat(1024 * 1024) })]) {
    writeFileSync(join(f.root, 'bad.json'), content);
    const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'verify', 'gates', '--case', 'pre_cutover', '--evidence', join(f.root, 'bad.json')], { encoding: 'utf8' });
    assert.equal(result.status, 1);
    assert.equal(result.stderr.trim(), 'PLATFORM_GATE_EVIDENCE_REJECTED');
  }
  const result = spawnSync(process.execPath, ['scripts/platform.mjs', 'verify', 'gates', '--case', 'pre_cutover', '--evidence', join(f.root, 'missing.json')], { encoding: 'utf8' });
  assert.equal(result.status, 1);
});
