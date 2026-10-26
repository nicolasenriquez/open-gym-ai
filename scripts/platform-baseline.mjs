import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// Expectations are reviewed inputs, never generated from the implementation under test.
export function checkBaseline(root = new URL('../', import.meta.url)) {
  const manifest = JSON.parse(readFileSync(new URL('backend/contracts/port-baseline.v1.json', root), 'utf8'));
  if (!/^[a-f0-9]{40}$/.test(manifest.sourceRevision) || !Object.keys(manifest.files ?? {}).length) {
    throw new Error('PLATFORM_BASELINE_INVALID');
  }
  for (const [path, expected] of Object.entries(manifest.files)) {
    if (!/^(?:api|frontend|backend)\/[a-zA-Z0-9_./-]+$/.test(path) || path.split('/').includes('..')) {
      throw new Error('PLATFORM_BASELINE_INVALID');
    }
    const text = readFileSync(new URL(path, root), 'utf8').replaceAll('\r\n', '\n');
    if (createHash('sha256').update(text).digest('hex') !== expected) throw new Error('PLATFORM_BASELINE_DRIFT');
  }
  return manifest.sourceRevision;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv.length !== 2) throw new Error('PLATFORM_BASELINE_USAGE');
    console.log(JSON.stringify({ code: 'PLATFORM_BASELINE_OK', sourceRevision: checkBaseline() }));
  } catch {
    console.error('PLATFORM_BASELINE_REJECTED');
    process.exitCode = 1;
  }
}
