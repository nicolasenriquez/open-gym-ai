import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { syntheticHarness } from './synthetic-harness.mjs';
import { checkBaseline } from './platform-baseline.mjs';

const [action, suite, ...options] = process.argv.slice(2);
const { docker, compose, execute, cleanup, runProject } = syntheticHarness({
  root: fileURLToPath(new URL('../', import.meta.url)),
  composeFile: fileURLToPath(new URL('../deploy/docker-compose.test.yml', import.meta.url)),
  emptyEnv: fileURLToPath(new URL('../backend/empty.env', import.meta.url)),
  namespace: 'opengym-platform-test', label: 'org.opengym.platform', name: 'Platform',
  services: ['platform-contracts', 'platform-db', 'platform-test', 'platform-browser'], images: ['platform-contracts', 'platform-test', 'platform-browser'], database: 'platform-db',
});

try {
  if (action === 'cleanup' && options.length === 0) {
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
    for (const entry of selected) {
      if (entry.target === 'host') {
        const output = await execute(process.execPath, entry.command);
        if (!/\btests [1-9]\d*/.test(output) || /\b(?:skipped|todo|cancelled) [1-9]\d*/.test(output)) {
          throw new Error('PLATFORM_REQUIRED_PROOF_MISSING');
        }
      } else if (entry.target === 'platform-browser') {
        await runProject(async (step, project) => {
          await step(['config', '--quiet']);
          await step(['build', 'platform-test', 'platform-browser']);
          await step(['up', '--detach', '--wait', '--wait-timeout', '60', 'platform-db', 'platform-browser']);
          try {
            await step(['run', '--rm', '--no-deps', '--use-aliases', 'platform-test', ...entry.command]);
          } finally {
            await docker([...compose(project), 'logs', '--no-color', 'platform-browser'], true);
            const evidence = fileURLToPath(new URL(`../.scratch/platform-browser/${project}`, import.meta.url));
            mkdirSync(evidence, { recursive: true });
            const files = JSON.parse(await docker(['exec', `${project}-platform-browser-1`, 'node', '-e',
              "const fs=require('node:fs');console.log(JSON.stringify(fs.readdirSync('/tmp/evidence').map(name=>({name,data:fs.readFileSync('/tmp/evidence/'+name).toString('base64')}))))"]));
            for (const { name, data } of files) {
              assert.match(name, /^(?:(?:passkeys|login|offline|auth|conflicts|lost-reply|restore|reset|links|media|FAIL)\.png|result\.json)$/, 'PLATFORM_BROWSER_ARTIFACT_INVALID');
              assert.ok(Buffer.from(data, 'base64').length > 0, 'PLATFORM_BROWSER_ARTIFACT_EMPTY');
              writeFileSync(new URL(name, new URL(`../.scratch/platform-browser/${project}/`, import.meta.url)), Buffer.from(data, 'base64'));
            }
            const result = JSON.parse(readFileSync(new URL(`../.scratch/platform-browser/${project}/result.json`, import.meta.url)));
            if (result.completed) {
              assert.deepEqual(result.cases, ['passkeys', 'login', 'offline', 'auth', 'conflicts', 'lost-reply', 'restore', 'reset', 'links', 'media']);
              for (const id of result.cases) assert.ok(files.some(file => file.name === `${id}.png`), 'PLATFORM_BROWSER_SCREENSHOT_MISSING');
            }
            console.log(`Platform browser evidence: ${evidence}`);
          }
        });
      } else if (entry.target === 'platform-test') {
        await runProject(async step => {
          await step(['config', '--quiet']);
          await step(['build', entry.target]);
          await step(['up', '--detach', '--wait', '--wait-timeout', '60', 'platform-db']);
          await step(['run', '--rm', '--no-deps', entry.target, ...entry.command]);
        });
      } else if (entry.target === 'platform-contracts') {
        checkBaseline();
        await runProject(async step => {
          await step(['config', '--quiet']);
          await step(['build', entry.target]);
          await step(['run', '--rm', '--no-deps', entry.target, ...entry.command]);
        });
      } else throw new Error('PLATFORM_MAPPING_INVALID');
      console.log(JSON.stringify({ code: 'PLATFORM_CASE_OK', suite, case: entry.id }));
    }
  }
} catch (error) {
  console.error(error.message);
  process.exitCode ||= 1;
}
