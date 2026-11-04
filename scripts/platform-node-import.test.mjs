import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { syntheticHarness } from './synthetic-harness.mjs';

test('stopped Node capture imports into a new isolated PostgreSQL target without promoting access', { timeout: 540_000 }, async () => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const { docker, compose, runProject } = syntheticHarness({ root,
    composeFile: fileURLToPath(new URL('../deploy/docker-compose.test.yml', import.meta.url)),
    emptyEnv: fileURLToPath(new URL('../backend/empty.env', import.meta.url)),
    namespace: 'opengym-platform-test', label: 'org.opengym.platform', name: 'Node import',
    services: ['platform-client', 'platform-db', 'platform-test'], images: ['platform-client', 'platform-test'],
    database: 'platform-db', extraVolumes: { 'node-capture': { name: 'node-capture', service: 'platform-client' } },
  });
  const proof = (output, path) => {
    writeFileSync(path, output);
    process.stdout.write(output);
    assert.match(output, /(?:\btests [1-9]\d*|\b[1-9]\d* passed)/);
    assert.match(output, /NODE_CHAIN_EXIT_0\b/);
    assert.doesNotMatch(output, /\b(?:skipped|todo|cancelled) [1-9]\d*|[1-9]\d* (?:skipped|xfailed|deselected)/);
  };
  await runProject(async (step, project) => {
    const evidence = join(root, '.scratch', 's11-node-import', project);
    mkdirSync(evidence, { recursive: true });
    console.log(`NODE_CAPTURE_IMPORT_EVIDENCE ${evidence}`);
    await step(['config', '--quiet']);
    await step(['build', 'platform-client', 'platform-test']);
    const volume = `${project}_node-capture`;
    assert.equal((await docker(['volume', 'create',
      '--label', `com.docker.compose.project=${project}`, '--label', 'org.opengym.platform=synthetic',
      '--label', 'com.docker.compose.service=platform-client', '--label', 'com.docker.compose.volume=node-capture', volume])).trim(), volume);
    // Keep synthetic test diagnostics visible even on failure; the exit marker is mandatory.
    proof(await docker([...compose(project), 'run', '--rm', '--no-deps', '--entrypoint', 'sh',
      '--volume', `${volume}:/app/node-capture-fixtures`, 'platform-client',
      '-c', 'node --test --test-reporter=tap scripts/platform-node-import-source.mjs 2>&1; node_chain_status=$?; printf "\\nNODE_CHAIN_EXIT_%s\\n" "$node_chain_status"']), join(evidence, 'node-capture.log'));
    await step(['up', '--detach', '--wait', '--wait-timeout', '60', 'platform-db']);
    proof(await docker([...compose(project), 'run', '--rm', '--no-deps', '--entrypoint', 'sh',
      '--volume', `${volume}:/run/node-capture:ro`, 'platform-test', '-c',
      'python -m pytest -q -p no:cacheprovider --tb=short tests/platform/node_capture_import.py 2>&1; node_chain_status=$?; printf "\\nNODE_CHAIN_EXIT_%s\\n" "$node_chain_status"']), join(evidence, 'postgres-import.log'));
  });
});
