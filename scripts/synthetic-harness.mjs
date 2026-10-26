import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';

// Shared mechanics only; each caller supplies its own fixed synthetic namespace/config.
export function syntheticHarness({ root, composeFile, emptyEnv, namespace, label, name, services, images, database,
  networkNames = ['private'], volumeName = 'postgres-data' }) {
  const dockerEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith('COMPOSE_')));
  dockerEnv.COMPOSE_DISABLE_ENV_FILE = 'true';
  const compose = project => ['compose', '--project-directory', root, '--env-file', emptyEnv, '-f', composeFile, '-p', project];
  let activeChild;

  const docker = (args, live = false) => execute('docker', args, live);

  function execute(program, args, live = false) {
    return new Promise((resolve, reject) => {
      // An unref'ed deadline also lets a missing executable exit immediately.
      const child = spawn(program, args, { cwd: root, env: dockerEnv, signal: AbortSignal.timeout(300_000), stdio: ['ignore', 'pipe', 'pipe'] });
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
      child.on('error', () => reject(new Error(program === 'docker' ? 'Docker unavailable' : `${name} harness unavailable`)));
      child.on('close', code => {
        activeChild = undefined;
        if (code === 0 && !overflow) resolve(Buffer.concat(chunks).toString('utf8'));
        else reject(new Error(program === 'docker' ? `Docker ${args[0]} failed` : `${name} proof failed; run the mapped command directly`));
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
        && labels?.[label] === 'synthetic';
      let id = item.Id;
      if (type === 'container') {
        valid &&= services.includes(service)
          && new RegExp(`^/${project}-${service}-(?:[1-9][0-9]*|run-[a-f0-9]{12})$`).test(item.Name);
      } else if (type === 'volume') {
        valid &&= service === database && item.Name === `${project}_${volumeName}`
          && labels['com.docker.compose.volume'] === 'postgres-data';
        id = item.Name;
      } else if (type === 'network') {
        valid &&= networkNames.includes(service) && item.Name === `${project}_${service}`
          && labels['com.docker.compose.network'] === service;
      } else {
        id = `${project}-${service}:local`;
        valid &&= images.includes(service)
          && item.RepoTags?.length === 1 && item.RepoTags[0] === id;
      }
      if (!valid) throw new Error(`Refusing unverified ${name} resource; nothing removed`);
      targets.push({ type, id });
    }
    // Validate the complete set before the first removal; never down, prune or remove-orphans.
    for (const { type, id } of targets) await docker([type, 'rm', ...(type === 'container' ? ['--force'] : []), id]);
    console.log(`${name} cleanup complete`);
  }

  async function runProject(work) {
    const project = `${namespace}-${randomBytes(8).toString('hex')}`;
    console.log(`${name} project: ${project}`);
    if ((await resources(project)).length) throw new Error(`Refusing an existing ${name} project`);
    let interrupted = false;
    const stop = () => { interrupted = true; activeChild?.kill('SIGTERM'); };
    const step = async args => {
      if (interrupted) throw new Error(`${name} interrupted`);
      await docker([...compose(project), ...args], true);
      if (interrupted) throw new Error(`${name} interrupted`);
    };
    process.on('SIGINT', stop);
    process.on('SIGTERM', stop);
    try {
      await work(step, project);
    } finally {
      try { await cleanup(project); }
      finally {
        process.off('SIGINT', stop);
        process.off('SIGTERM', stop);
      }
    }
  }
  return { docker, compose, execute, cleanup, runProject };
}
