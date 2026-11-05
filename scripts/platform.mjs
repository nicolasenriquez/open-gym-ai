import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { syntheticHarness } from './synthetic-harness.mjs';

const [action, suite, ...options] = process.argv.slice(2);
const build = (...services) => [
  'build',
  ...(process.env.BUILDX_BUILDER ? ['--builder', process.env.BUILDX_BUILDER] : []),
  ...services,
];
const { docker, compose, execute, cleanup, runProject } = syntheticHarness({
  root: fileURLToPath(new URL('../', import.meta.url)),
  composeFile: fileURLToPath(new URL('../deploy/docker-compose.test.yml', import.meta.url)),
  emptyEnv: fileURLToPath(new URL('../backend/empty.env', import.meta.url)),
  namespace: 'opengym-platform-test', label: 'org.opengym.platform', name: 'Platform',
  services: ['platform-client', 'platform-db', 'platform-test', 'platform-browser'], images: ['platform-client', 'platform-test', 'platform-browser'], database: 'platform-db',
});

function requireProof(output) {
  if (!/\btests [1-9]\d*/.test(output) || /\b(?:skipped|todo|cancelled) [1-9]\d*/.test(output)) {
    throw new Error('PLATFORM_REQUIRED_PROOF_MISSING');
  }
}

try {
  if (action === 'verify' && suite === 'gates' && options.includes('--evidence')) {
    if (options.length !== 4 || options[0] !== '--case' || !['pre_cutover', 'authorized_cutover'].includes(options[1]) || options[2] !== '--evidence' || !options[3]) {
      process.exitCode = 2;
      throw new Error('PLATFORM_SUITE_OR_CASE_NOT_IMPLEMENTED');
    }
    try {
      const { verifyPreCutover, verifyAuthorizedCutover } = await import('./platform-gates.mjs');
      console.log(JSON.stringify((options[1] === 'pre_cutover' ? verifyPreCutover : verifyAuthorizedCutover)(options[3])));
    } catch {
      throw new Error('PLATFORM_GATE_EVIDENCE_REJECTED');
    }
  } else if (action === 'operate') {
    if (suite === 'restore-rehearse') {
      const { rehearse } = await import('./platform-rehearsal.mjs');
      await rehearse(options);
    } else {
      const { operate } = await import('./platform-maintenance.mjs');
      await operate(suite, options);
    }
  } else if (action === 'cleanup' && options.length === 0) {
    if (!/^opengym-platform-test-[a-f0-9]{16}$/.test(suite ?? '')) throw new Error('Refusing non-test target');
    await cleanup(suite);
  } else if (action === 'config' && suite === undefined && options.length === 0) {
    console.log(await docker([...compose('opengym-platform-test'), 'config', '--format', 'json']));
  } else {
    const manifest = JSON.parse(readFileSync(new URL('../backend/platform-suites.json', import.meta.url), 'utf8'));
    const cases = Object.hasOwn(manifest, suite ?? '') ? manifest[suite] : undefined;
    const selected = options.length === 0 ? cases : options.length === 2 && options[0] === '--case'
      ? cases?.filter(entry => entry.id === options[1]) : undefined;
    if (action !== 'verify' || !selected?.length) {
      process.exitCode = 2;
      throw new Error('PLATFORM_SUITE_OR_CASE_NOT_IMPLEMENTED');
    }
    const batches = selected.every(entry => entry.target === 'platform-test')
      ? [selected]
      : selected.map(entry => [entry]);
    for (const batch of batches) {
      const entry = batch[0];
      if (entry.target === 'host') {
        const output = await execute(process.execPath, entry.command, false,
          suite === 'images' && entry.id === 'reproducibility' ? 3_600_000 : suite === 'backup' || suite === 'repair'
            || (suite === 'restore' && entry.id === 'full_timing') || (suite === 'gates' && entry.id === 'node_capture_recovery') ? 600_000 : 300_000);
        requireProof(output);
      } else if (entry.target === 'platform-browser') {
        await runProject(async (step, project) => {
          await step(['config', '--quiet']);
          await step(build('platform-test', 'platform-browser'));
          await step(['up', '--detach', '--wait', '--wait-timeout', '60', 'platform-db', 'platform-browser']);
          try {
            await step(['run', '--rm', '--no-deps', '--use-aliases', 'platform-test', ...entry.command]);
          } finally {
            await docker([...compose(project), 'logs', '--no-color', 'platform-browser'], true);
            const evidence = mkdtempSync(join(tmpdir(), 'opengym-platform-browser-'));
            const files = JSON.parse(await docker(['exec', `${project}-platform-browser-1`, 'node', '-e',
              `const fs=require('node:fs');
               const dirs=fs.readdirSync('/tmp',{withFileTypes:true})
                 .filter(entry=>entry.isDirectory()&&entry.name.startsWith('opengym-browser-evidence-'));
               if(dirs.length!==1)throw new Error('PLATFORM_BROWSER_EVIDENCE_DIRECTORY_INVALID');
               const root='/tmp/'+dirs[0].name;
               console.log(JSON.stringify(fs.readdirSync(root).map(name=>({
                 name,data:fs.readFileSync(root+'/'+name).toString('base64')
               }))));`]));
            for (const { name, data } of files) {
              assert.match(name, /^(?:(?:passkeys|login|offline|auth|conflicts|lost-reply|restore|reset|links|media|media-queue|media-gc|admin-invites|admin-audit|FAIL)\.png|result\.json)$/, 'PLATFORM_BROWSER_ARTIFACT_INVALID');
              assert.ok(Buffer.from(data, 'base64').length > 0, 'PLATFORM_BROWSER_ARTIFACT_EMPTY');
              writeFileSync(join(evidence, name), Buffer.from(data, 'base64'));
            }
            const result = JSON.parse(readFileSync(join(evidence, 'result.json')));
            if (result.completed) {
              assert.deepEqual(result.cases, ['passkeys', 'login', 'offline', 'auth', 'conflicts', 'lost-reply', 'restore', 'reset', 'links', 'media', 'media-queue', 'media-gc', 'admin-invites', 'admin-audit']);
              for (const id of result.cases) assert.ok(files.some(file => file.name === `${id}.png`), 'PLATFORM_BROWSER_SCREENSHOT_MISSING');
            }
            console.log(`Platform browser evidence: ${evidence}`);
          }
        });
      } else if (entry.target === 'platform-test') {
        await runProject(async step => {
          await step(['config', '--quiet']);
          await step(build(entry.target));
          await step(['up', '--detach', '--wait', '--wait-timeout', '60', 'platform-db']);
          for (const current of batch) {
            await step(['run', '--rm', '--no-deps', current.target, ...current.command]);
          }
        });
      } else if (entry.target === 'platform-client') {
        await runProject(async (step, project) => {
          await step(['config', '--quiet']);
          await step(build(entry.target));
          const args = ['run', '--rm', '--no-deps', ...(entry.entrypoint ? ['--entrypoint', entry.entrypoint] : []), entry.target, ...entry.command];
          if (suite === 'gates') {
            const output = await docker([...compose(project), ...args]);
            process.stdout.write(output);
            requireProof(output);
          } else await step(args);
        });
      } else throw new Error('PLATFORM_MAPPING_INVALID');
      for (const current of batch) {
        console.log(JSON.stringify({ code: 'PLATFORM_CASE_OK', suite, case: current.id,
          ...(suite === 'gates' ? { synthetic: true, realGateCompleted: false, cutoverAuthorized: false } : {}) }));
      }
    }
  }
} catch (error) {
  console.error(action === 'operate' && !/^(?:MAINTENANCE|REHEARSAL)_[A-Z_]+$/.test(error.message)
    ? suite === 'restore-rehearse' ? 'REHEARSAL_FAILED' : 'MAINTENANCE_FAILED' : error.message);
  process.exitCode ||= 1;
}
