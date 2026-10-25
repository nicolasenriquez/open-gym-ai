import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const [action, value, ...extra] = process.argv.slice(2);
const root = fileURLToPath(new URL('../', import.meta.url));
const composeFile = fileURLToPath(new URL('../compose.python-foundation.yml', import.meta.url));
const emptyEnv = fileURLToPath(new URL('../backend/empty.env', import.meta.url));
const dockerEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith('COMPOSE_')));
dockerEnv.COMPOSE_DISABLE_ENV_FILE = 'true';
const compose = project => ['compose', '--project-directory', root, '--env-file', emptyEnv, '-f', composeFile, '-p', project];
let activeChild;

const docker = (args, live = false) => execute('docker', args, live);

function execute(program, args, live = false) {
  return new Promise((resolve, reject) => {
    const child = spawn(program, args, { cwd: root, env: dockerEnv, timeout: 300_000, stdio: ['ignore', 'pipe', 'pipe'] });
    activeChild = child;
    const chunks = [];
    let size = 0;
    let overflow = false;
    child.stdout.on('data', data => {
      if (live) process.stdout.write(data);
      else if (!overflow) {
        size += data.length;
        if (size > 4 * 1024 * 1024) { overflow = true; child.kill('SIGTERM'); }
        else chunks.push(data);
      }
    });
    child.stderr.on('data', data => {
      if (live) process.stderr.write(data);
      else {
        size += data.length;
        if (size > 4 * 1024 * 1024) { overflow = true; child.kill('SIGTERM'); }
      }
    });
    child.on('error', () => reject(new Error(program === 'docker' ? 'Docker unavailable' : 'Foundation harness unavailable')));
    child.on('close', code => {
      activeChild = undefined;
      if (code === 0 && !overflow) resolve(Buffer.concat(chunks).toString('utf8'));
      else reject(new Error(program === 'docker' ? `Docker ${args[0]} failed` : 'Foundation Docker regressions failed; run node --test scripts/python-foundation.test.mjs'));
    });
  });
}

async function resources(project) {
  const result = [];
  for (const type of ['container', 'volume', 'network', 'image']) {
    const selected = new Set();
    for (const filter of [`label=com.docker.compose.project=${project}`,
      type === 'image' ? `reference=${project}-*` : `name=^/?${project}[-_]`]) {
      const ids = await docker([type, 'ls', '--quiet', ...(type === 'container' ? ['--all'] : []), '--filter', filter]);
      for (const id of ids.trim().split(/\s+/).filter(Boolean)) selected.add(id);
    }
    if (selected.size) {
      for (const item of JSON.parse(await docker([type, 'inspect', ...selected]))) result.push({ type, item });
    }
  }
  return result;
}

async function cleanup(project) {
  const targets = [];
  for (const { type, item } of await resources(project)) {
    const labels = ['container', 'image'].includes(type) ? item.Config.Labels : item.Labels;
    const service = labels?.['com.docker.compose.service'];
    let valid = labels?.['com.docker.compose.project'] === project
      && labels?.['org.opengym.python-foundation'] === 'synthetic';
    let id = item.Id;
    if (type === 'container') {
      valid &&= ['foundation-db', 'foundation-test', 'foundation-contracts'].includes(service)
        && new RegExp(`^/${project}-${service}-(?:[1-9][0-9]*|run-[a-f0-9]{12})$`).test(item.Name);
    } else if (type === 'volume') {
      valid &&= service === 'foundation-db' && item.Name === `${project}_postgres-data`
        && labels['com.docker.compose.volume'] === 'postgres-data';
      id = item.Name;
    } else if (type === 'network') {
      valid &&= service === 'private' && item.Name === `${project}_private`
        && labels['com.docker.compose.network'] === 'private';
    } else {
      id = `${project}-${service}:local`;
      valid &&= ['foundation-test', 'foundation-contracts'].includes(service)
        && item.RepoTags?.length === 1 && item.RepoTags[0] === id;
    }
    if (!valid) throw new Error('Refusing unverified Python Foundation resource; nothing removed');
    targets.push({ type, id });
  }
  // Validate the complete set before the first removal; never down, prune or remove-orphans.
  for (const { type, id } of targets) await docker([type, 'rm', ...(type === 'container' ? ['--force'] : []), id]);
  console.log('Python Foundation cleanup complete');
}

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
  const project = `opengym-python-foundation-test-${randomBytes(8).toString('hex')}`;
  console.log(`Python Foundation project: ${project}`);
  if ((await resources(project)).length) throw new Error('Refusing an existing Python Foundation project');
  let interrupted = false;
  const stop = () => { interrupted = true; activeChild?.kill('SIGTERM'); };
  const step = async args => {
    if (interrupted) throw new Error('Python Foundation interrupted');
    await docker([...compose(project), ...args], true);
    if (interrupted) throw new Error('Python Foundation interrupted');
  };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  try {
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
  } finally {
    try { await cleanup(project); }
    finally {
      process.off('SIGINT', stop);
      process.off('SIGTERM', stop);
    }
  }
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
