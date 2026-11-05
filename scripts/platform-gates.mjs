import { constants, openSync, closeSync, readSync, fstatSync, lstatSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, resolve, parse, join, relative } from 'node:path';

function readEvidence(path, limit) {
  const absolute = resolve(path);
  let parent = parse(absolute).root;
  for (const part of relative(parent, absolute).split(/[\\/]/)) {
    parent = join(parent, part);
    if (lstatSync(parent).isSymbolicLink()) throw new Error('Unsafe evidence path');
  }
  const expected = lstatSync(absolute);
  if (!expected.isFile() || expected.nlink !== 1 || expected.size === 0 || expected.size > limit) throw new Error('Unsafe evidence file');
  const fd = openSync(absolute, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
  try {
    const before = fstatSync(fd);
    if (!before.isFile() || before.nlink !== 1 || before.size === 0 || before.size > limit
      || before.ino !== expected.ino || before.dev !== expected.dev) throw new Error('Changed evidence file');
    const bytes = Buffer.alloc(expected.size + 1);
    let size = 0;
    while (size < bytes.length) {
      const count = readSync(fd, bytes, size, bytes.length - size, null);
      if (!count) break;
      size += count;
    }
    const after = fstatSync(fd);
    if (!after.isFile() || after.nlink !== 1
      || size !== expected.size || after.size !== expected.size || after.mtimeMs !== expected.mtimeMs || after.ctimeMs !== expected.ctimeMs) throw new Error('Changed evidence file');
    return bytes.subarray(0, size);
  } finally {
    closeSync(fd);
  }
}

const coverage = {
  G0: ['clients_origins', 'client_pending_active_media', 'frontend_api_mapping', 'physical_backup_keys', 'protected_later_access_source', 'rehearsed_window'],
  G1: ['target_environment', 'pool_lifecycle', 'roles_rls_transactions', 'migrations_lock_interrupt', 'backup_restore'],
  GP: ['capability_parity_q6', 'frontend_offline_sync', 'security_audit', 'module_contracts'],
  GO: ['clean_checkout_images_ci', 'runtime_environments', 'restore_rpo_rto', 'diagnostics_privacy_retention', 'forward_repair_new_writes'],
};

export function verifyPreCutover(indexPath) {
  return verifyCutoverEvidence(indexPath, 'pre_cutover');
}

export function verifyAuthorizedCutover(indexPath) {
  return verifyCutoverEvidence(indexPath, 'authorized_cutover');
}

function verifyCutoverEvidence(indexPath, expectedCase) {
  const require = condition => { if (!condition) throw new Error('PLATFORM_GATE_EVIDENCE_REJECTED'); };
  const text = value => typeof value === 'string' && value.trim().length > 0;
  const digest = value => typeof value === 'string' && /^sha256:[a-f0-9]{64}$/.test(value);
  const identity = value => text(value?.instance) && typeof value.revision === 'string'
    && /^[a-f0-9]{40}$/.test(value.revision) && digest(value.digest) && text(value.platform);
  const timestamp = value => typeof value === 'string' && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString() === value;
  const bound = value => ['instance', 'revision', 'digest', 'platform'].every(key => value?.[key] === index[key]);
  const index = JSON.parse(readEvidence(indexPath, 1024 * 1024).toString('utf8'));
  require(index.version === 1 && index.case === expectedCase && typeof index.synthetic === 'boolean');
  require(identity(index));
  require(index.artifactRoot === 'artifacts');
  const root = resolve(dirname(indexPath), 'artifacts');
  require(Array.isArray(index.artifacts) && index.artifacts.length > 0 && index.artifacts.length <= 128);
  const artifacts = new Map();
  let total = 0;
  for (const artifact of index.artifacts) {
    require(typeof artifact.path === 'string' && artifact.path.split('/').every(part => /^[a-zA-Z0-9_-][a-zA-Z0-9_.-]*$/.test(part)));
    require(!artifacts.has(artifact.path) && text(artifact.sha256) && /^[a-f0-9]{64}$/.test(artifact.sha256));
    const bytes = readEvidence(resolve(root, artifact.path), 4 * 1024 * 1024);
    total += bytes.length;
    require(total <= 32 * 1024 * 1024);
    require(bytes.length > 0 && createHash('sha256').update(bytes).digest('hex') === artifact.sha256);
    artifacts.set(artifact.path, bytes);
  }
  require(artifacts.has(index.review) && artifacts.has(index.authorization));
  require(artifacts.has(index.releaseManifest));
  const release = JSON.parse(artifacts.get(index.releaseManifest).toString('utf8'));
  require(release.version === 1 && bound(release.binding) && digest(release.contentIdentity) && text(release.schemaHead));
  require(Array.isArray(release.images) && release.images.length >= 6 && release.images.length <= 128);
  const roles = new Set();
  for (const image of release.images) {
    require(text(image.role) && !roles.has(image.role) && digest(image.digest)
      && image.platform === index.platform && text(image.sourceIdentity));
    if (image.role === 'api') require(image.digest === index.digest);
    roles.add(image.role);
  }
  require(['api', 'web', 'postgres', 'migrate', 'ops', 'collector'].every(role => roles.has(role)));
  const recovery = index.recovery;
  require(['node_json', 'python_postgresql'].includes(recovery?.sourceType) && artifacts.has(recovery.report));
  const report = JSON.parse(artifacts.get(recovery.report).toString('utf8'));
  require(report.version === 1 && bound(report.binding) && report.complete === true && report.closed === true
    && report.reviewed === true && report.unresolved_accesses === 0 && report.operational_acceptance === false);
  const times = [recovery.sourceCutoffAt, recovery.capturedAt];
  if (recovery.sourceType === 'node_json') times.push(recovery.importedAt);
  else require(recovery.importedAt === null);
  times.push(report.snapshot_at, report.incident_at, report.started_at, report.finished_at);
  require(times.every(timestamp));
  const sequence = times.map(Date.parse);
  require(sequence.every((time, i) => i === 0 || time >= sequence[i - 1]));
  const rpo = Date.parse(report.incident_at) - Date.parse(recovery.sourceCutoffAt);
  const rto = Date.parse(report.finished_at) - Date.parse(report.incident_at);
  require(rpo <= 6 * 3600_000 && rto <= 24 * 3600_000);
  require(report.objectives_ms?.rpo === 6 * 3600_000 && report.objectives_ms.rto === 24 * 3600_000
    && report.rpo_ms === Date.parse(report.incident_at) - Date.parse(report.snapshot_at)
    && Number.isFinite(report.elapsed_ms) && report.elapsed_ms >= rto && report.elapsed_ms <= 24 * 3600_000
    && report.rpo_met === true && report.rto_met === true && report.rto_credited === true);
  require(Array.isArray(index.gates) && index.gates.length === 4);
  for (const [gate, names] of Object.entries(coverage)) {
    const matches = index.gates.filter(entry => entry.gate === gate);
    require(matches.length === 1 && Array.isArray(matches[0].checks));
    const checks = matches[0].checks;
    require(checks.length === names.length);
    for (const name of names) {
      const selected = checks.filter(check => check.name === name);
      require(selected.length === 1);
      const check = selected[0];
      require(bound(check.binding));
      require(identity(check.provenance) && timestamp(check.provenance.observedAt));
      if (!bound(check.provenance)) require(artifacts.has(check.applicability));
      require(check.result === 'passed' && check.skipped === 0 && text(check.command) && text(check.scope) && text(check.limitations));
      require(Array.isArray(check.ev) && check.ev.length > 0 && check.ev.every(ev => /^EV-0[1-9]$/.test(ev)));
      require(Array.isArray(check.artifacts) && check.artifacts.length > 0 && check.artifacts.every(path => artifacts.has(path)));
      if (gate === 'GO' && name === 'restore_rpo_rto') require(check.artifacts.includes(recovery.report));
    }
  }
  if (expectedCase === 'authorized_cutover') {
    require(artifacts.has(index.cutover));
    const authorization = JSON.parse(artifacts.get(index.authorization).toString('utf8'));
    const cutover = JSON.parse(artifacts.get(index.cutover).toString('utf8'));
    require(authorization.version === 1 && bound(authorization.binding)
      && authorization.scope === 'cutover' && authorization.decision === 'approved'
      && text(authorization.operator) && text(authorization.approvedBy)
      && authorization.releaseManifestSha256 === index.artifacts.find(a => a.path === index.releaseManifest).sha256);
    require(cutover.version === 1 && bound(cutover.binding) && cutover.authorization === index.authorization);
    const window = [authorization.approvedAt, authorization.window?.start, cutover.startedAt,
      cutover.finishedAt, authorization.window?.end];
    require(window.every(timestamp));
    require(window.map(Date.parse).every((time, i, times) => i === 0 || time >= times[i - 1]));
    require(Date.parse(report.finished_at) <= Date.parse(authorization.approvedAt)
      && index.gates.every(gate => gate.checks.every(check => Date.parse(check.provenance.observedAt) <= Date.parse(authorization.approvedAt))));
    require(Date.parse(authorization.window.end) > Date.parse(authorization.window.start));
    require(timestamp(cutover.protectedUntil)
      && Date.parse(cutover.protectedUntil) - Date.parse(cutover.finishedAt) >= 30 * 24 * 3600_000);
    require(Number.isSafeInteger(cutover.acknowledgedNewWrites) && cutover.acknowledgedNewWrites >= 0);
    require(['cutover', 'rollback_before_writes', 'forward_repair'].includes(cutover.outcome));
    require(cutover.authority === (cutover.outcome === 'rollback_before_writes' ? 'node_json' : 'python_postgresql'));
    const proofs = ['writersStopped', 'equivalentImport', 'singleAuthority', 'protectedOriginReleaseConfigurationSecrets'];
    if (cutover.outcome === 'rollback_before_writes') {
      require(cutover.acknowledgedNewWrites === 0);
      proofs.push('validatedOriginRollback');
    }
    if (cutover.outcome === 'forward_repair') {
      require(cutover.acknowledgedNewWrites > 0);
      proofs.push('preservedNewWrites');
    }
    require(proofs.every(proof => artifacts.has(cutover.evidence?.[proof])));
  }
  return { code: 'PLATFORM_GATE_STRUCTURE_OK', case: expectedCase, synthetic: index.synthetic,
    manualReviewRequired: true, cutoverAuthorized: false, realGateCompleted: false };
}
