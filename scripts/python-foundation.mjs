import { fileURLToPath } from 'node:url';
import { syntheticHarness } from './synthetic-harness.mjs';

const [action, value, ...extra] = process.argv.slice(2);
const root = fileURLToPath(new URL('../', import.meta.url));
const { docker, compose, execute, cleanup, runProject } = syntheticHarness({
  root, composeFile: fileURLToPath(new URL('../compose.python-foundation.yml', import.meta.url)),
  emptyEnv: fileURLToPath(new URL('../backend/empty.env', import.meta.url)),
  namespace: 'opengym-python-foundation-test', label: 'org.opengym.python-foundation', name: 'Python Foundation',
  services: ['foundation-db', 'foundation-test', 'foundation-contracts'],
  images: ['foundation-test', 'foundation-contracts'], database: 'foundation-db',
});

async function run(group) {
  if (group === 'all') {
    for (const proof of ['contracts', 'environment', 'pool', 'migrations', 'isolation', 'recovery', 'checks']) await run(proof);
    const output = await execute(process.execPath, ['--test', 'scripts/python-foundation.test.mjs']);
    if (/\bskipped [1-9]\d*|\b[1-9]\d* skipped\b/.test(output)) throw new Error('Required Docker proof skipped');
    console.log(JSON.stringify({ code: 'FOUNDATION_DOCKER_REGRESSIONS_OK' }));
    console.log(JSON.stringify({ code: 'FOUNDATION_ALL_OK' }));
    return;
  }
  if (!['environment', 'contracts', 'pool', 'migrations', 'isolation', 'recovery', 'checks'].includes(group)) throw new Error(`Python Foundation group not implemented: ${group}`);
  await runProject(async step => {
    await step(['config', '--quiet']);
    if (['contracts', 'checks'].includes(group)) {
      const service = group === 'contracts' ? 'foundation-contracts' : 'foundation-test';
      await step(['build', service]);
      await step(['run', '--rm', '--no-deps', service, group]);
    } else {
      await step(['build', 'foundation-test', ...(group === 'environment' ? ['foundation-contracts'] : [])]);
      if (group === 'environment') await step(['run', '--rm', '--no-deps', 'foundation-contracts', 'environment']);
      await step(['up', '--detach', '--wait', '--wait-timeout', '60', 'foundation-db']);
      await step(['run', '--rm', '--no-deps', 'foundation-test', group]);
    }
  });
}

try {
  if (extra.length) throw new Error('Unexpected Python Foundation arguments');
  if (action === 'config' && !value) {
    console.log(await docker([...compose('opengym-python-foundation-test'), 'config', '--format', 'json']));
  } else if (action === 'run') {
    if (!['contracts', 'environment', 'pool', 'migrations', 'isolation', 'recovery', 'all'].includes(value)) {
      throw new Error('Unknown Python Foundation group');
    }
    await run(value);
  } else if (action !== 'cleanup' || !/^opengym-python-foundation-test-[a-f0-9]{16}$/.test(value ?? '')) {
    throw new Error('Refusing non-test target');
  } else {
    await cleanup(value);
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
