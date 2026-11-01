import { spawn, spawnSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import { closeSync, existsSync, fsyncSync, lstatSync, mkdirSync, openSync, readFileSync, readdirSync, realpathSync, renameSync, rmdirSync, unlinkSync, writeFileSync } from 'node:fs';
import { hostname } from 'node:os';
import { setTimeout as sleep } from 'node:timers/promises';
import { isAbsolute, join, resolve } from 'node:path';

// Never inherit implicit Compose selection or a personal .env.
const environment = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.toUpperCase().startsWith('COMPOSE_')));
environment.COMPOSE_DISABLE_ENV_FILE = 'true';

function docker(args, cwd, timeout = 15_000, proof) {
  return new Promise((accept, reject) => {
    if (proof) {
      proof.journal.client = 'pending';
      journalWrite(proof.root, proof.journal);
    }
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
    try {
      if (proof) {
        const start = processStart(child.pid);
        proof.journal.client = start === null ? null : { host: hostname(), pid: child.pid, start };
        journalWrite(proof.root, proof.journal);
      }
    } catch (error) { child.kill(); reject(error); }
  });
}

const canonical = value => process.platform === 'win32' ? resolve(value).toLowerCase() : resolve(value);

function safePath(path, directory = false) {
  const info = lstatSync(path);
  if (info.isSymbolicLink() || (directory ? !info.isDirectory() : !info.isFile() || info.nlink !== 1)
    || canonical(realpathSync(path)) !== canonical(path)) throw new Error('MAINTENANCE_PATH_UNSAFE');
}

function fileProof(path) {
  safePath(path);
  const before = lstatSync(path, { bigint: true });
  if (before.size > 16n * 1024n * 1024n) throw new Error('MAINTENANCE_CONFIG_TOO_LARGE');
  const sha256 = createHash('sha256').update(readFileSync(path)).digest('hex');
  const after = lstatSync(path, { bigint: true });
  const identity = info => [info.dev, info.ino, info.size, info.mtimeNs, info.ctimeNs].join(':');
  if (identity(before) !== identity(after)) throw new Error('MAINTENANCE_FILE_CHANGED');
  return { sha256, identity: identity(after) };
}

// Docker paths are daemon paths, not necessarily host paths on Docker Desktop.
const mountPath = path => {
  const normalized = path.replaceAll('\\', '/').replace(/\/$/, '');
  return process.platform === 'win32'
    ? normalized.replace(/^\/(?:run\/desktop\/mnt\/host|host_mnt)\/([a-z])\//i, '$1:/').toLowerCase()
    : normalized;
};
const overlaps = (a, b) => a === b || a.startsWith(`${b}/`) || b.startsWith(`${a}/`);

function privateJson(path) {
  safePath(path);
  if (lstatSync(path).size > 65536) throw new Error('MAINTENANCE_PROOF_INVALID');
  return JSON.parse(readFileSync(path, 'utf8'));
}

// PID plus OS start identity: reuse/reboot never identifies an old controller.
function processStart(pid) {
  if (!Number.isSafeInteger(pid) || pid < 1) throw new Error('MAINTENANCE_PROCESS_INVALID');
  if (process.platform === 'win32') {
    const result = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      "$ErrorActionPreference='Stop'; $p=Get-Process -Id $env:OPENGYM_PROCESS_ID -ErrorAction SilentlyContinue; "
      + "if($null -eq $p){'absent'}else{$p.StartTime.ToUniversalTime().Ticks.ToString()}"],
    { env: { ...environment, OPENGYM_PROCESS_ID: String(pid) }, encoding: 'utf8', windowsHide: true, timeout: 5000 });
    if (result.status !== 0) throw new Error('MAINTENANCE_PROCESS_UNPROVEN');
    const token = result.stdout.trim();
    if (token === 'absent') return null;
    if (!/^\d+$/.test(token)) throw new Error('MAINTENANCE_PROCESS_UNPROVEN');
    return token;
  }
  if (process.platform !== 'linux') throw new Error('MAINTENANCE_HOST_UNSUPPORTED');
  try {
    const value = readFileSync(`/proc/${pid}/stat`, 'utf8');
    return `${readFileSync('/proc/sys/kernel/random/boot_id', 'utf8').trim()}:${value.slice(value.lastIndexOf(')') + 2).split(' ')[19]}`;
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw new Error('MAINTENANCE_PROCESS_UNPROVEN');
  }
}

const controller = () => ({ host: hostname(), pid: process.pid, start: processStart(process.pid) });
function alive(owner) {
  if (!owner || owner.host !== hostname() || typeof owner.start !== 'string' || !owner.start) {
    throw new Error('MAINTENANCE_PROCESS_UNPROVEN');
  }
  return processStart(owner.pid) === owner.start;
}

function claimRecovery(lock, operation) {
  let leaf = lock;
  // Immutable successors give concurrent recoverers an atomic mkdir winner;
  // an interrupted recovery can itself be recovered without deleting a live lock.
  for (let depth = 0; depth < 64; depth++) {
    safePath(leaf, true);
    const owner = privateJson(join(leaf, 'controller.json'));
    if (owner.operation !== operation) throw new Error('MAINTENANCE_OPERATION_MISMATCH');
    if (alive(owner)) throw new Error('MAINTENANCE_CONTROLLER_ACTIVE');
    const next = join(leaf, 'recovery');
    if (existsSync(next)) { leaf = next; continue; }
    try { mkdirSync(next, { mode: 0o700 }); }
    catch { throw new Error('MAINTENANCE_LOCKED'); }
    journalWrite(next, { ...controller(), operation }, 'controller.json');
    return;
  }
  throw new Error('MAINTENANCE_RECOVERY_LIMIT');
}

function unlock(lock) {
  safePath(lock, true);
  const entries = readdirSync(lock);
  if (entries.some(name => !['controller.json', 'recovery'].includes(name))) throw new Error('MAINTENANCE_LOCK_INVALID');
  if (existsSync(join(lock, 'recovery'))) unlock(join(lock, 'recovery'));
  safePath(join(lock, 'controller.json'));
  unlinkSync(join(lock, 'controller.json'));
  rmdirSync(lock);
}

function journalWrite(root, journal, name = 'journal.json') {
  const temporary = join(root, `${journal.operation}.${randomBytes(8).toString('hex')}.tmp`);
  const fd = openSync(temporary, 'wx', 0o600);
  try { writeFileSync(fd, JSON.stringify(journal)); fsyncSync(fd); }
  finally { closeSync(fd); }
  renameSync(temporary, join(root, name));
  if (process.platform !== 'win32') {
    const directory = openSync(root, 'r');
    try { fsyncSync(directory); } finally { closeSync(directory); }
  }
}

function admission(config, journal, allowed) {
  const root = join(config.state_root, 'gate');
  safePath(root, true);
  const previous = privateJson(join(root, 'admission.json'));
  if (previous.instance_id !== config.instance_id || typeof previous.allowed !== 'boolean'
    || !/^[a-f0-9]{32}$/.test(previous.operation)) throw new Error('MAINTENANCE_GATE_INVALID');
  journalWrite(root, { instance_id: config.instance_id, operation: journal.operation, allowed }, 'admission.json');
}

function writerGate(config, item) {
  if (!item.Config.Env.includes(`PLATFORM_INSTANCE_ID=${config.instance_id}`)
    || !item.Config.Env.includes('PLATFORM_MAINTENANCE_GATE_DIR=/run/maintenance-gate')
    || !item.Mounts.some(mount => mount.Type === 'bind' && !mount.RW && mount.Destination === '/run/maintenance-gate'
      && mountPath(mount.Source) === mountPath(join(config.state_root, 'gate')))) throw new Error('MAINTENANCE_GATE_REQUIRED');
}

async function restartWriters(config, journal, run, inspect, track) {
  journal.phase = 'restarting';
  journalWrite(config.state_root, journal);
  admission(config, journal, true);
  try {
    for (const service of journal.previously_running) {
      const writer = journal.writers.find(writer => writer.service === service);
      await docker(['start', writer.id], config.project_directory, 15_000, track);
      const deadline = performance.now() + 30_000;
      while (true) {
        const item = await inspect(writer.id);
        if (!item.State.Running || item.State.Restarting || item.Image !== writer.image) throw new Error('MAINTENANCE_RESTART_FAILED');
        if (service !== 'api') break;
        try {
          await docker(['exec', writer.id, 'python', '-c',
            "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:3000/api/v1/health/ready',timeout=1).status==200"],
          config.project_directory, 3000);
          break;
        } catch {
          if (performance.now() > deadline) throw new Error('MAINTENANCE_RESTART_FAILED');
          await sleep(100);
        }
      }
    }
  } catch (error) {
    try { admission(config, journal, false); }
    finally { await run(['stop', '--timeout', '30', ...config.writers], 40_000, track); }
    throw error;
  }
}

async function recover(config, operation, run, inspect, lock) {
  const journal = privateJson(join(config.state_root, 'journal.json'));
  const identity = privateJson(join(config.state_root, 'owner.json'));
  if (identity.instance_id !== config.instance_id || identity.project !== config.project
    || journal.instance_id !== config.instance_id || journal.project !== config.project
    || journal.operation !== operation || journal.version !== 1 || journal.verified !== false
    || !['scheduled', 'startup', 'pre-migration'].includes(journal.reason)
    || !['stopping', 'stopped', 'capturing', 'checking', 'restarting', 'recovering', 'migration_held',
      'captured_unverified', 'recovered_unverified'].includes(journal.phase)
    || !Array.isArray(journal.writers) || journal.writers.length !== config.writers.length
    || !Array.isArray(journal.previously_running)
    || new Set(journal.previously_running).size !== journal.previously_running.length
    || journal.previously_running.some(service => !config.writers.includes(service))
    || new Set(journal.writers.map(writer => writer.service)).size !== config.writers.length
    || journal.writers.some(writer => !config.writers.includes(writer.service) || !/^[a-f0-9]{64}$/.test(writer.id)
      || !/^sha256:[a-f0-9]{64}$/.test(writer.image))
    || journal.capture_container !== `${config.project}-ops-run-${operation.slice(0, 12)}`
    || !Array.isArray(journal.check_containers) || journal.check_containers.length > 64
    || journal.check_containers.some(name => !new RegExp(`^${config.project}-ops-run-[a-f0-9]{12}$`).test(name)
      || name === journal.capture_container)) throw new Error('MAINTENANCE_PROOF_INVALID');
  claimRecovery(lock, operation);
  admission(config, journal, false);
  const track = { root: config.state_root, journal };
  const model = JSON.parse(await run(['--profile', 'tools', 'config', '--format', 'json']));
  const ids = (await docker(['ps', '-aq', '--no-trunc', '--filter', `label=com.docker.compose.project=${config.project}`], config.project_directory))
    .trim().split(/\s+/).filter(Boolean);
  const containers = await Promise.all(ids.map(inspect));
  const db = containers.find(item => item.Id === journal.database?.id && item.Image === journal.database.image);
  if (!db?.State.Running || db.State.Health?.Status !== 'healthy'
    || db.Config.Labels['com.docker.compose.service'] !== 'db'
    || db.Config.Labels['org.opengym.maintenance.instance'] !== config.instance_id
    || canonical(db.Config.Labels['org.opengym.maintenance.state'] ?? '') !== canonical(config.state_root)
    || Object.keys(db.HostConfig.PortBindings ?? {}).length
    || (await inspect(model.services.ops.image)).Id !== journal.ops_image) throw new Error('MAINTENANCE_STATE_OWNERSHIP');
  for (const writer of journal.writers) {
    const item = containers.find(item => item.Id === writer.id);
    const selected = model.services[writer.service];
    if (!item || item.Image !== writer.image || item.Config.Labels['com.docker.compose.service'] !== writer.service
      || (await inspect(selected.image)).Id !== writer.image
      || (selected.command && JSON.stringify(selected.command) !== JSON.stringify(item.Config.Cmd))
      || Object.entries(selected.environment ?? {}).some(([key, value]) => !item.Config.Env.includes(`${key}=${value}`))) {
      throw new Error('MAINTENANCE_WRITER_CHANGED');
    }
    writerGate(config, item);
  }
  if (containers.some(item => config.writers.includes(item.Config.Labels['com.docker.compose.service'])
    && !journal.writers.some(writer => writer.id === item.Id))) throw new Error('MAINTENANCE_MULTIPLE_WRITERS');
  const names = [journal.capture_container, ...journal.check_containers];
  if (journal.phase === 'capturing' && !containers.some(item => item.Name === `/${journal.capture_container}`)) {
    throw new Error('MAINTENANCE_CAPTURE_UNCERTAIN');
  }
  for (const item of containers) {
    const service = item.Config.Labels['com.docker.compose.service'];
    if (names.includes(item.Name.slice(1))) {
      if (service !== 'ops' || item.Image !== journal.ops_image || item.HostConfig.RestartPolicy.Name !== 'no') {
        throw new Error('MAINTENANCE_CAPTURE_OWNERSHIP');
      }
      if (item.State.Running) await docker(['stop', '--time', '5', item.Id], config.project_directory, 15_000);
      if ((await inspect(item.Id)).State.Running) throw new Error('MAINTENANCE_CAPTURE_NOT_STOPPED');
    } else if (item.State.Running && !['db', 'web', 'diagnostics', ...config.writers].includes(service)) {
      throw new Error('MAINTENANCE_UNKNOWN_WRITER');
    }
  }
  if (!Object.hasOwn(journal, 'client')) throw new Error('MAINTENANCE_PROCESS_UNPROVEN');
  for (let attempt = 0; journal.client && alive(journal.client); attempt++) {
    if (attempt === 50) throw new Error('MAINTENANCE_CLIENT_ACTIVE');
    await sleep(100);
  }
  journal.phase = 'recovering';
  journalWrite(config.state_root, journal);
  await run(['stop', '--timeout', '30', ...config.writers], 40_000, track);
  for (const writer of journal.writers) {
    if ((await inspect(writer.id)).State.Running) throw new Error('MAINTENANCE_WRITER_CHANGED');
  }
  for (const network of Object.keys(db.NetworkSettings.Networks)) {
    const meta = JSON.parse(await docker(['network', 'inspect', network], config.project_directory))[0];
    if (Object.keys(meta.Containers ?? {}).some(id => !ids.includes(id))) throw new Error('MAINTENANCE_EXTERNAL_WRITER');
  }
  const running = (await docker(['ps', '-q', '--no-trunc'], config.project_directory)).trim().split(/\s+/).filter(Boolean);
  const protectedSources = [config.state_root, ...(journal.capture_sources ?? []).map(source => source.origin),
    ...containers.filter(item => journal.writers.some(writer => writer.id === item.Id)).flatMap(item =>
      item.Mounts.filter(mount => mount.Destination !== '/run/diagnostics').map(mount => mount.Source))];
  for (const id of running) {
    if (id === db.Id) continue;
    const item = await inspect(id);
    if (item.Mounts.some(mount => mount.RW && protectedSources.some(source =>
      overlaps(mountPath(mount.Source), mountPath(source)) || (mount.Type === 'volume' && mount.Name === source)))) {
      throw new Error('MAINTENANCE_EXTERNAL_FILE_WRITER');
    }
  }
  journal.phase = 'checking';
  const checker = `${config.project}-ops-run-${randomBytes(6).toString('hex')}`;
  journal.check_containers.push(checker);
  journalWrite(config.state_root, journal);
  const output = await run(['run', '--no-deps', '--name', checker, 'ops', '-m', 'opengym_platform.operations',
    'capture-sql', '--config', '/run/operator/config.json', '--check-only'], 15_000, track);
  const check = await inspect(checker);
  if (check.State.Running || check.State.ExitCode !== 0 || JSON.parse(output.trim()).code !== 'BACKUP_SCHEMA_COMPATIBLE') {
    throw new Error('MAINTENANCE_SCHEMA_INCOMPATIBLE');
  }
  if (journal.reason === 'pre-migration') {
    journal.phase = 'migration_held';
    journalWrite(config.state_root, journal);
    throw new Error('MAINTENANCE_MIGRATION_HELD');
  }
  await restartWriters(config, journal, run, inspect, track);
  journal.phase = 'recovered_unverified';
  journalWrite(config.state_root, journal);
  unlock(lock);
  console.log(JSON.stringify({ code: 'MAINTENANCE_RECOVERED', operation, verified: false }));
}

export async function operate(command, options) {
  const recovering = command === 'maintenance-recover';
  if (options.length !== 4 || options[0] !== '--config' || (recovering
    ? options[2] !== '--operation' || !/^[a-f0-9]{32}$/.test(options[3])
    : command !== 'backup' || options[2] !== '--reason' || !['scheduled', 'startup', 'pre-migration'].includes(options[3]))) {
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
  const run = (args, timeout, proof) => docker([...prefix, ...args], config.project_directory, timeout, proof);
  const inspect = async id => JSON.parse(await docker(['inspect', id], config.project_directory))[0];
  const lock = join(config.state_root, 'exclusive');
  if (recovering) return recover(config, options[3], run, inspect, lock);
  try { mkdirSync(lock, { mode: 0o700 }); }
  catch { throw new Error('MAINTENANCE_LOCKED'); }
  let safeToUnlock = true;
  const operation = randomBytes(16).toString('hex');
  journalWrite(lock, { ...controller(), operation }, 'controller.json');
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
        || !['captured_unverified', 'recovered_unverified'].includes(previous.phase)) throw new Error('MAINTENANCE_UNRESOLVED_JOURNAL');
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
        writerGate(config, item);
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
    const api = containers.filter(item => item.Config.Labels['com.docker.compose.service'] === 'api');
    if (api.length !== 1) throw new Error('MAINTENANCE_MULTIPLE_WRITERS');
    const actualEnvironment = Object.fromEntries(api[0].Config.Env.map(value => {
      const split = value.indexOf('=');
      return [value.slice(0, split), value.slice(split + 1)];
    }));
    if (Object.entries(model.services.api.environment ?? {}).some(([key, value]) => actualEnvironment[key] !== String(value))
      || (model.services.api.command && JSON.stringify(model.services.api.command) !== JSON.stringify(api[0].Config.Cmd))) {
      throw new Error('MAINTENANCE_RUNTIME_CONFIG_MISMATCH');
    }
    for (const key of ['PLATFORM_DB_PASSWORD_FILE', 'PLATFORM_SESSION_SECRET_FILE', 'PLATFORM_COACH_SECRET_FILE']) {
      const path = actualEnvironment[key];
      if (path && (!/^\/run\/secrets\/[A-Za-z0-9_-]+$/.test(path)
        || !api[0].Mounts.some(mount => mount.Destination === path))) throw new Error('MAINTENANCE_SECRET_MOUNT_INVALID');
    }
    const dataDirectory = actualEnvironment.DATA_DIR ?? '/data';
    const dataMount = api[0].Mounts.find(mount => mount.Destination === dataDirectory);
    if (!dataMount || !['bind', 'volume'].includes(dataMount.Type)
      || api[0].Mounts.some(mount => mount.Destination.startsWith(`${dataDirectory}/`))) {
      throw new Error('MAINTENANCE_DATA_MOUNT_REQUIRED');
    }
    const selectedData = model.services.api.volumes?.find(item => item.target === dataDirectory);
    if (!selectedData || selectedData.type !== dataMount.Type) throw new Error('MAINTENANCE_DATA_OWNERSHIP');
    if (dataMount.Type === 'volume') {
      const volume = JSON.parse(await docker(['volume', 'inspect', dataMount.Name], config.project_directory))[0];
      if (model.volumes?.[selectedData.source]?.name !== dataMount.Name
        || volume.Labels?.['com.docker.compose.project'] !== config.project
        || volume.Labels?.['com.docker.compose.volume'] !== selectedData.source) throw new Error('MAINTENANCE_DATA_OWNERSHIP');
    } else {
      safePath(selectedData.source, true);
      if (mountPath(selectedData.source) !== mountPath(dataMount.Source)) throw new Error('MAINTENANCE_DATA_OWNERSHIP');
    }
    const selection = join(config.state_root, `${operation}.selection.json`);
    writeFileSync(selection, JSON.stringify({ compose: model, api: { image: api[0].Image, config: api[0].Config },
      database_image: db[0].Image }), { flag: 'wx', mode: 0o600 });
    const files = [options[1], config.env_file, ...config.compose_files, selection,
      ...Object.values(model.configs ?? {}).map(item => item.file),
      ...Object.values(model.secrets ?? {}).map(item => item.file),
      ...Object.values(model.services).flatMap(service => (service.volumes ?? [])
        .filter(item => item.type === 'bind' && /^\/run\/(secrets|operator)\//.test(item.target)).map(item => item.source))];
    if (files.some(path => typeof path !== 'string' || !isAbsolute(path))) throw new Error('MAINTENANCE_FILE_SOURCE_REQUIRED');
    const sourceFiles = [...new Set(files)];
    const fingerprints = sourceFiles.map(fileProof);
    const sources = [{ source: dataMount.Type === 'volume' ? dataMount.Name : dataMount.Source,
      target: 'data' }];
    // Include actual runtime secret mounts as well as the selected Compose inputs.
    for (const mount of api[0].Mounts.filter(item => item.Destination.startsWith('/run/secrets/'))) {
      const name = mount.Destination.slice('/run/secrets/'.length);
      if (mount.Type !== 'bind' || !/^[a-zA-Z0-9_-]+$/.test(name)) throw new Error('MAINTENANCE_SECRET_MOUNT_INVALID');
      const reference = model.services.api.secrets?.find(item => (item.target ?? item.source) === name);
      const selectedFile = reference ? model.secrets?.[reference.source]?.file
        : model.services.api.volumes?.find(item => item.target === mount.Destination)?.source;
      const index = sourceFiles.indexOf(selectedFile);
      if (index < 0) throw new Error('MAINTENANCE_SECRET_MOUNT_INVALID');
      sources.push({ source: mount.Source, target: `runtime-secrets/${name}`, sha256: fingerprints[index].sha256 });
    }
    sourceFiles.forEach((source, index) => sources.push({ source, target: `configuration/${index}`,
      sha256: fingerprints[index].sha256 }));
    if (sources.some(item => /[:,\n\r]/.test(item.source.replace(/^[a-zA-Z]:/, '')))) throw new Error('MAINTENANCE_MOUNT_PATH_INVALID');
    if (dataMount.Type === 'bind' && overlaps(mountPath(dataMount.Source), mountPath(config.state_root))) {
      throw new Error('MAINTENANCE_PATH_OVERLAP');
    }
    journal.capture_sources = sources.map((item, index) => ({ path: `/run/capture/${index}`,
      target: item.target, origin: item.source, ...(item.sha256 ? { sha256: item.sha256 } : {}) }));
    const volumeArgs = sources.flatMap((item, index) => ['--volume', `${item.source}:/run/capture/${index}:ro`]);
    const protectedMounts = [dataMount, ...containers.flatMap(item => item.Mounts.filter(mount =>
      mount.Destination.startsWith('/run/secrets/') || mount.Destination.startsWith('/run/operator/'))),
    ...sourceFiles.map(Source => ({ Type: 'bind', Source })), { Type: 'bind', Source: config.state_root }];
    const checkExternalWriters = async () => {
      const running = (await docker(['ps', '-q', '--no-trunc'], config.project_directory)).trim().split(/\s+/).filter(Boolean);
      for (const id of running) {
        if (journal.writers.some(writer => writer.id === id) || id === db[0].Id) continue;
        const item = await inspect(id);
        if (item.Mounts.some(mount => mount.RW && protectedMounts.some(protectedMount =>
          (mount.Type === 'volume' && protectedMount.Type === 'volume' && mount.Name === protectedMount.Name)
          || overlaps(mountPath(mount.Source), mountPath(protectedMount.Source))))) {
          throw new Error('MAINTENANCE_EXTERNAL_FILE_WRITER');
        }
      }
    };
    await checkExternalWriters();
    journal.database = { id: db[0].Id, image: db[0].Image };
    journal.ops_image = (await inspect(model.services.ops.image)).Id;
    journal.check_containers = [];
    const track = { root: config.state_root, journal };
    journal.capture_container = `${config.project}-ops-run-${operation.slice(0, 12)}`;
    journal.phase = 'stopping';
    journalWrite(config.state_root, journal);
    safeToUnlock = false;
    admission(config, journal, false);
    const paused = performance.now();
    journal.pause_started_at = new Date().toISOString();
    journal.capture_budget_ms = 120_000;
    journalWrite(config.state_root, journal);
    await run(['stop', '--timeout', '30', ...config.writers], 40_000, track);
    for (const writer of journal.writers) {
      const item = await inspect(writer.id);
      if (item.State.Running || item.State.OOMKilled
        || (journal.previously_running.includes(writer.service) && item.State.ExitCode !== 0)) {
        throw new Error('MAINTENANCE_UNCLEAN_SHUTDOWN');
      }
    }
    await checkExternalWriters();
    journal.phase = 'stopped';
    journalWrite(config.state_root, journal);
    // Keep the named container for independent exit verification; never --rm a
    // capture process before proving it has stopped.
    journal.phase = 'capturing';
    journalWrite(config.state_root, journal);
    const output = await run(['run', '--no-deps', '--name', journal.capture_container, ...volumeArgs, 'ops',
      '-m', 'opengym_platform.operations', 'capture-sql', '--config', '/run/operator/config.json'], 130_000, track);
    const capture = await inspect(journal.capture_container);
    journal.capture_image = capture.Image;
    if (capture.State.Running || capture.State.ExitCode !== 0) throw new Error('MAINTENANCE_CAPTURE_NOT_STOPPED');
    const result = JSON.parse(output.trim());
    if (result.code !== 'BACKUP_SET_CAPTURED' || result.operation !== operation) throw new Error('MAINTENANCE_CAPTURE_INVALID');
    await checkExternalWriters();
    for (let index = 0; index < sourceFiles.length; index++) {
      if (JSON.stringify(fileProof(sourceFiles[index])) !== JSON.stringify(fingerprints[index])) {
        throw new Error('MAINTENANCE_FILE_CHANGED');
      }
    }
    journal.phase = 'checking';
    journalWrite(config.state_root, journal);
    const checker = `${config.project}-ops-run-${randomBytes(6).toString('hex')}`;
    journal.check_containers.push(checker);
    journalWrite(config.state_root, journal);
    await run(['run', '--no-deps', '--name', checker, 'ops', '-m', 'opengym_platform.operations', 'capture-sql',
      '--config', '/run/operator/config.json', '--check-only'], 15_000, track);
    for (const writer of journal.writers) {
      const item = await inspect(writer.id);
      if (item.State.Running || item.Image !== writer.image) throw new Error('MAINTENANCE_WRITER_CHANGED');
    }
    // Pre-migration must never reopen traffic between capture and future DDL.
    if (journal.reason === 'pre-migration') throw new Error('MAINTENANCE_MIGRATION_NOT_IMPLEMENTED');
    // start, not up: never recreate an image or launch dependencies here.
    await restartWriters(config, journal, run, inspect, track);
    journal.pause_ms = Math.round(performance.now() - paused);
    journal.snapshot_at = result.snapshot_at;
    journal.capture_ms = result.capture_ms;
    journal.phase = 'captured_unverified';
    journalWrite(config.state_root, journal);
    writeFileSync(join(config.state_root, operation, 'host-journal.json'), JSON.stringify(journal), { flag: 'wx', mode: 0o600 });
    safeToUnlock = true;
    console.log(JSON.stringify({ code: 'BACKUP_CAPTURED_UNVERIFIED', operation, pause_ms: journal.pause_ms, verified: false }));
    process.exitCode = 1;
  } finally {
    // Interrupted/uncertain shutdown, capture or restart remains explicitly locked.
    // Only an explicit owned recovery can take over an interrupted operation.
    if (safeToUnlock) unlock(lock);
  }
}
