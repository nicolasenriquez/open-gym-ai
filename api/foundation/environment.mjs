import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const [action, project, ...extra] = process.argv.slice(2);
const composeFile = fileURLToPath(new URL('../../compose.foundation.yml', import.meta.url));
const emptyEnv = fileURLToPath(new URL('./empty.env', import.meta.url));
const dockerEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith('COMPOSE_')));

let activeChild;
function docker(args, live = false) {
  return new Promise((resolve, reject) => {
    const child = spawn('docker', args, { env: dockerEnv, timeout: 180_000 });
    activeChild = child;
    let output = '';
    child.stdout.on('data', data => { output += data; if (live) process.stdout.write(data); });
    child.stderr.on('data', data => { if (live) process.stderr.write(data); });
    child.on('error', () => reject(new Error('Docker unavailable')));
    child.on('close', code => {
      activeChild = undefined;
      if (code === 0) resolve(output);
      else reject(new Error(`Docker ${args[0]} failed`));
    });
  });
}

async function cleanup(project) {
  const resources = [];
  for (const type of ['container', 'volume', 'network', 'image']) {
    const args = [type, 'ls', '--quiet', '--filter', `label=com.docker.compose.project=${project}`];
    if (type === 'container') args.push('--all');
    const ids = (await docker(args)).trim().split(/\s+/).filter(Boolean);
    if (!ids.length) continue;
    const inspected = JSON.parse(await docker([type, 'inspect', ...ids]));
    for (const item of inspected) {
      const labels = ['container', 'image'].includes(type) ? item.Config.Labels : item.Labels;
      const imageTag = `${project}-foundation-test:latest`;
      const expectedName = type === 'volume' ? `${project}_postgres-data` : `${project}_private`;
      if (labels?.['com.docker.compose.project'] !== project || labels?.['org.opengym.foundation'] !== 'synthetic'
        || (['volume', 'network'].includes(type) && item.Name !== expectedName)
        || (type === 'container' && !['foundation-db', 'foundation-test'].includes(labels['com.docker.compose.service']))
        || (type === 'image' && (labels['com.docker.compose.service'] !== 'foundation-test' || !item.RepoTags?.includes(imageTag)))) {
        throw new Error('Refusing unverified Foundation resource; nothing removed');
      }
      resources.push({ type, id: type === 'volume' ? item.Name : type === 'image' ? imageTag : item.Id });
    }
  }
  // Validate the entire target set before the first deletion; never prune or remove volumes via a container.
  for (const { type, id } of resources) {
    await docker([type, 'rm', ...(type === 'container' ? ['--force'] : []), id]);
  }
  console.log('Foundation cleanup complete');
}

async function run(group = 'environment') {
  if (!['environment', 'pool', 'migrations', 'isolation', 'recovery', 'all'].includes(group)) throw new Error('Foundation slice not implemented');
  const runProject = `opengym-foundation-test-${randomBytes(8).toString('hex')}`;
  const compose = ['compose', '--env-file', emptyEnv, '-f', composeFile, '-p', runProject];
  for (const type of ['container', 'volume', 'network', 'image']) {
    const args = [type, 'ls', '--quiet', '--filter', `label=com.docker.compose.project=${runProject}`];
    if (type === 'container') args.push('--all');
    if ((await docker(args)).trim()) throw new Error('Refusing an existing Foundation project');
  }
  console.log(`Foundation project: ${runProject}`);
  const stop = () => activeChild?.kill('SIGTERM');
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  try {
    await docker([...compose, 'config', '--quiet']);
    await docker([...compose, 'build', 'foundation-test'], true);
    await docker([...compose, 'up', '--detach', '--wait', '--wait-timeout', '60', 'foundation-db'], true);
    await docker([...compose, 'run', '--rm', '--no-deps', 'foundation-test', group], true);
  } finally {
    process.off('SIGINT', stop);
    process.off('SIGTERM', stop);
    await cleanup(runProject);
  }
}

try {
  if (extra.length) throw new Error('Unexpected Foundation arguments');
  if (action === 'run') {
    await run(project);
  } else if (action === 'config' && !project) {
    console.log(await docker(['compose', '--env-file', emptyEnv, '-f', composeFile,
      '-p', 'opengym-foundation-test', 'config', '--format', 'json']));
  } else if (action !== 'cleanup' || !/^opengym-foundation-test-[a-f0-9]{16}$/.test(project ?? '')) {
    throw new Error('Refusing non-test target');
  } else {
    await cleanup(project);
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
