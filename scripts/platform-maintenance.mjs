import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { closeSync, existsSync, fsyncSync, lstatSync, mkdirSync, openSync, readFileSync, realpathSync, renameSync, rmdirSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

// Never inherit implicit Compose selection or a personal .env.
const environment = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith('COMPOSE_')));
environment.COMPOSE_DISABLE_ENV_FILE = 'true';

function docker(args, cwd, timeout = 15_000) {
  return new Promise((accept, reject) => {
    const child = spawn('docker', args, { cwd, env: environment, shell: false, windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'], signal: AbortSignal.timeout(timeout) });
    const chunks = [];
    let size = 0;
    child.stdout.on('data', data => {
      size += data.length;
      if (size > 4 * 1024 * 1024) child.kill();
      else chunks.push(data);
    });
    // Docker diagnostics can contain private paths or provider data.
    child.stderr.resume();
    child.on('error', () => reject(new Error('MAINTENANCE_DOCKER_UNAVAILABLE_OR_TIMEOUT')));
    child.on('close', code => code === 0 && size <= 4 * 1024 * 1024
      ? accept(Buffer.concat(chunks).toString('utf8')) : reject(new Error('MAINTENANCE_DOCKER_FAILED')));
  });
}

const canonical = value => process.platform === 'win32' ? resolve(value).toLowerCase() : resolve(value);

function safePath(path, directory = false) {
  const info = lstatSync(path);
  if (info.isSymbolicLink() || (directory ? !info.isDirectory() : !info.isFile() || info.nlink !== 1)
    || canonical(realpathSync(path)) !== canonical(path)) throw new Error('MAINTENANCE_PATH_UNSAFE');
}

function journalWrite(root, journal) {
  const temporary = join(root, `${journal.operation}.tmp`);
  const fd = openSync(temporary, 'wx', 0o600);
  try { writeFileSync(fd, JSON.stringify(journal)); fsyncSync(fd); }
  finally { closeSync(fd); }
  renameSync(temporary, join(root, 'journal.json'));
  if (process.platform !== 'win32') {
    const directory = openSync(root, 'r');
    try { fsyncSync(directory); } finally { closeSync(directory); }
  }
}

export async function operate(command, options) {
  if (command !== 'backup' || options.length !== 4 || options[0] !== '--config'
    || options[2] !== '--reason' || !['scheduled', 'startup', 'pre-migration'].includes(options[3])) {
    process.exitCode = 2;
    throw new Error('MAINTENANCE_ARGUMENTS_INVALID');
  }
  let config;
  try {
    if (!isAbsolute(options[1])) throw new Error();
    config = JSON.parse(readFileSync(options[1], 'utf8'));
    const keys = ['instance_id', 'project', 'project_directory', 'compose_files', 'env_file', 'state_root', 'writers'];
    if (!config || Object.keys(config).length !== keys.length || keys.some(key => !Object.hasOwn(config, key))
      || !/^[a-z][a-z0-9-]{1,63}$/.test(config.instance_id)
      || !/^[a-z][a-z0-9-]{1,63}$/.test(config.project)
      || !['project_directory', 'env_file', 'state_root'].every(key => typeof config[key] === 'string' && isAbsolute(config[key]))
      || !Array.isArray(config.compose_files) || !config.compose_files.length
      || !config.compose_files.every(path => typeof path === 'string' && isAbsolute(path))
      || !Array.isArray(config.writers) || !config.writers.includes('api')
      || config.writers.some(service => !/^[a-z][a-z0-9-]{0,63}$/.test(service))
      || new Set(config.writers).size !== config.writers.length) throw new Error();
  } catch {
    process.exitCode = 2;
    throw new Error('MAINTENANCE_CONFIG_INVALID');
  }
  for (const path of [config.project_directory, config.state_root]) safePath(path, true);
  for (const path of [options[1], config.env_file, ...config.compose_files]) safePath(path);
  if (process.platform === 'win32') {
    // chmod does not restrict NTFS access. Check the inherited ACL too; never
    // silently rewrite an operator's permissions or echo their private path.
    const acl = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      "$ErrorActionPreference='Stop'; $a=Get-Acl -LiteralPath $env:OPENGYM_PRIVATE_STATE; "
      + "$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
      + "$allowed=@($u,'S-1-5-18','S-1-5-32-544'); "
      + "if($a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $u){exit 1}; "
      + "foreach($r in $a.Access){if($r.AccessControlType -eq 'Allow' -and "
      + "$r.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -notin $allowed){exit 1}}"],
    { env: { ...environment, OPENGYM_PRIVATE_STATE: config.state_root }, stdio: 'ignore', timeout: 5000, windowsHide: true });
    if (acl.status !== 0) throw new Error('MAINTENANCE_STATE_NOT_PRIVATE');
  } else if (lstatSync(config.state_root).mode & 0o077) {
    throw new Error('MAINTENANCE_STATE_NOT_PRIVATE');
  }
  const prefix = ['compose', '--project-directory', config.project_directory, '--env-file', config.env_file,
    '-p', config.project, ...config.compose_files.flatMap(path => ['-f', path])];
  const run = (args, timeout) => docker([...prefix, ...args], config.project_directory, timeout);
  const inspect = async id => JSON.parse(await docker(['inspect', id], config.project_directory))[0];
  const lock = join(config.state_root, 'exclusive');
  try { mkdirSync(lock, { mode: 0o700 }); }
  catch { throw new Error('MAINTENANCE_LOCKED'); }
  let safeToUnlock = true;
  const operation = randomBytes(16).toString('hex');
  const journal = { version: 1, instance_id: config.instance_id, project: config.project, operation,
    reason: options[3], phase: 'preflight', previously_running: [], verified: false };
  try {
    const owner = join(config.state_root, 'owner.json');
    const identity = JSON.stringify({ instance_id: config.instance_id, project: config.project });
    if (existsSync(owner)) {
      safePath(owner);
      if (readFileSync(owner, 'utf8') !== identity) throw new Error('MAINTENANCE_OWNER_MISMATCH');
    } else writeFileSync(owner, identity, { flag: 'wx', mode: 0o600 });
    const prior = join(config.state_root, 'journal.json');
    if (existsSync(prior)) {
      safePath(prior);
      const previous = JSON.parse(readFileSync(prior, 'utf8'));
      if (previous.instance_id !== config.instance_id || previous.project !== config.project
        || previous.phase !== 'captured_unverified') throw new Error('MAINTENANCE_UNRESOLVED_JOURNAL');
    }
    const model = JSON.parse(await run(['--profile', 'tools', 'config', '--format', 'json']));
    if (!model.services?.db || !model.services?.ops || !model.services?.api
      || config.writers.some(name => !model.services[name] || ['db', 'ops', 'migrate', 'bootstrap', 'diagnostics', 'web'].includes(name))) {
      throw new Error('MAINTENANCE_WRITER_INVENTORY_INVALID');
    }
    const ids = (await docker(['ps', '-aq', '--no-trunc', '--filter', `label=com.docker.compose.project=${config.project}`], config.project_directory))
      .trim().split(/\s+/).filter(Boolean);
    const containers = await Promise.all(ids.map(inspect));
    const db = containers.filter(item => item.Config.Labels['com.docker.compose.service'] === 'db' && item.State.Running);
    if (db.length !== 1 || db[0].State.Health?.Status !== 'healthy') throw new Error('MAINTENANCE_DATABASE_UNAVAILABLE');
    const ownership = db[0].Config.Labels;
    const registeredState = ownership['org.opengym.maintenance.state'];
    if (ownership['org.opengym.maintenance.instance'] !== config.instance_id
      || typeof registeredState !== 'string' || !isAbsolute(registeredState)
      || canonical(registeredState) !== canonical(config.state_root)) throw new Error('MAINTENANCE_STATE_OWNERSHIP');
    if (Object.keys(db[0].HostConfig.PortBindings ?? {}).length) throw new Error('MAINTENANCE_DATABASE_EXPOSED');
    const knownReaders = ['db', 'web', 'diagnostics'];
    for (const item of containers) {
      const service = item.Config.Labels['com.docker.compose.service'];
      if (item.State.Running && ![...knownReaders, ...config.writers].includes(service)) throw new Error('MAINTENANCE_UNKNOWN_WRITER');
      if (config.writers.includes(service)) {
        const selected = await inspect(model.services[service].image);
        if (selected.Id !== item.Image) throw new Error('MAINTENANCE_WRITER_IMAGE_MISMATCH');
        if (item.State.Running) journal.previously_running.push(service);
      }
    }
    if (new Set(journal.previously_running).size !== journal.previously_running.length) throw new Error('MAINTENANCE_MULTIPLE_WRITERS');
    // Unknown database-network peers cannot silently become uncoordinated writers.
    for (const network of Object.keys(db[0].NetworkSettings.Networks)) {
      const meta = JSON.parse(await docker(['network', 'inspect', network], config.project_directory))[0];
      if (Object.keys(meta.Containers ?? {}).some(id => !ids.includes(id))) throw new Error('MAINTENANCE_EXTERNAL_WRITER');
    }
    journal.writers = containers.filter(item => config.writers.includes(item.Config.Labels['com.docker.compose.service']))
      .map(item => ({ service: item.Config.Labels['com.docker.compose.service'], id: item.Id, image: item.Image }));
    journal.capture_container = `${config.project}-ops-run-${operation.slice(0, 12)}`;
    journal.phase = 'stopping';
    journalWrite(config.state_root, journal);
    safeToUnlock = false;
    const paused = performance.now();
    await run(['stop', '--timeout', '30', ...config.writers], 40_000);
    for (const writer of journal.writers) {
      const item = await inspect(writer.id);
      if (item.State.Running || item.State.OOMKilled
        || (journal.previously_running.includes(writer.service) && item.State.ExitCode !== 0)) {
        throw new Error('MAINTENANCE_UNCLEAN_SHUTDOWN');
      }
    }
    journal.phase = 'stopped';
    journalWrite(config.state_root, journal);
    // Keep the named container for independent exit verification; never --rm a
    // capture process before proving it has stopped.
    journal.phase = 'capturing';
    journalWrite(config.state_root, journal);
    const output = await run(['run', '--no-deps', '--name', journal.capture_container, 'ops',
      '-m', 'opengym_platform.operations', 'capture-sql', '--config', '/run/operator/config.json'], 130_000);
    const capture = await inspect(journal.capture_container);
    if (capture.State.Running || capture.State.ExitCode !== 0) throw new Error('MAINTENANCE_CAPTURE_NOT_STOPPED');
    const result = JSON.parse(output.trim());
    if (result.code !== 'BACKUP_SQL_CAPTURED' || result.operation !== operation) throw new Error('MAINTENANCE_CAPTURE_INVALID');
    journal.phase = 'checking';
    journalWrite(config.state_root, journal);
    await run(['run', '--rm', '--no-deps', 'ops', '-m', 'opengym_platform.operations', 'capture-sql',
      '--config', '/run/operator/config.json', '--check-only']);
    for (const writer of journal.writers) {
      const item = await inspect(writer.id);
      if (item.State.Running || item.Image !== writer.image) throw new Error('MAINTENANCE_WRITER_CHANGED');
    }
    // Pre-migration must never reopen traffic between capture and future DDL.
    if (journal.reason === 'pre-migration') throw new Error('MAINTENANCE_MIGRATION_NOT_IMPLEMENTED');
    // start, not up: never recreate an image or launch dependencies here.
    if (journal.previously_running.length) await run(['start', ...journal.previously_running]);
    journal.pause_ms = Math.round(performance.now() - paused);
    journal.snapshot_at = result.snapshot_at;
    journal.phase = 'captured_unverified';
    journalWrite(config.state_root, journal);
    writeFileSync(join(config.state_root, operation, 'host-journal.json'), JSON.stringify(journal), { flag: 'wx', mode: 0o600 });
    safeToUnlock = true;
    console.log(JSON.stringify({ code: 'BACKUP_CAPTURED_UNVERIFIED', operation, pause_ms: journal.pause_ms, verified: false }));
    process.exitCode = 1;
  } finally {
    // Interrupted/uncertain shutdown, capture or restart remains explicitly locked.
    // No PID/TTL-based automatic release; recovery is a separate authorized slice.
    if (safeToUnlock) rmdirSync(lock);
  }
}
