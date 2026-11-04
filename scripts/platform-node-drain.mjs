import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { resolve, sep } from 'node:path';
import { captureStoppedNode, validateCapturePaths } from './platform-node-capture.mjs';

const execute = promisify(execFile);
const reject = () => { throw new Error('NODE_DRAIN_CAPTURE_REJECTED'); };
const canonical = p => process.platform === 'win32' ? resolve(p).toLowerCase() : resolve(p);
const overlaps = (a, b) => a === b || a.startsWith(b + sep) || b.startsWith(a + sep);
async function docker(args) {
  const result = await execute('docker', args, { windowsHide: true, timeout: 10_000, maxBuffer: 1024 * 1024 });
  return result.stdout;
}

// Keep Docker transport injectable so isolated verification can scope discovery.
export function createDockerNodeControl(runDocker = docker) {
  return {
    async inspect(id) {
      const [c] = JSON.parse(await runDocker(['inspect', '--type', 'container', id]));
      return { id: c.Id, image: c.Image, startedAt: c.State.StartedAt, running: c.State.Running,
        pid: c.State.Pid, exitCode: c.State.ExitCode, project: c.Config.Labels?.['com.docker.compose.project'],
        dataRoot: c.Mounts.find(m => m.Destination === '/data' && m.RW)?.Source };
    },
    async signal(id) { await runDocker(['kill', '--signal', 'SIGTERM', id]); },
    async proof(id, since) {
      const output = await runDocker(['logs', '--since', since, '--tail', '100', id]);
      const lines = output.split(/\r?\n/).filter(line => line.startsWith('NODE_DRAINED '));
      if (lines.length !== 1) reject();
      return JSON.parse(lines[0].slice('NODE_DRAINED '.length));
    },
    async noOtherContainers(sources, id) {
      const ids = (await runDocker(['ps', '--quiet', '--no-trunc'])).trim().split(/\s+/).filter(v => v && v !== id);
      if (!ids.length) return true;
      const containers = JSON.parse(await runDocker(['inspect', '--type', 'container', ...ids]));
      return containers.every(c => !c.State.Running || c.Mounts.every(m => !m.RW || m.Type === 'tmpfs'
        || !sources.some(s => overlaps(canonical(s.path), canonical(m.Source)))));
    },
  };
}

export const dockerNodeControl = createDockerNodeControl();

export async function drainAndCaptureNode({ api, sources, destination, externalWritersStopped,
  timeoutMs = 35_000 }, control = dockerNodeControl) {
  try {
    // Validate paths/identity and custody before the first state-changing call.
    validateCapturePaths({ sources, destination });
    if (!/^[a-f0-9]{64}$/.test(api?.id) || !/^sha256:[a-f0-9]{64}$/.test(api.image)
      || typeof api.project !== 'string' || !api.project.trim() || !Number.isFinite(Date.parse(api.startedAt))
      || typeof externalWritersStopped !== 'function' || !Number.isSafeInteger(timeoutMs)
      || timeoutMs < 50 || timeoutMs > 30 * 60000) reject();
    const bound = c => ['id', 'image', 'startedAt', 'project'].every(k => c[k] === api[k])
      && canonical(c.dataRoot) === canonical(sources.find(s => s.name === 'data').path);
    const custody = async () => await externalWritersStopped() === true
      && await control.noOtherContainers(sources, api.id) === true;
    const initial = await control.inspect(api.id);
    if (!bound(initial) || initial.running !== true || !Number.isSafeInteger(initial.pid) || initial.pid <= 0 || !await custody()) reject();
    const requestedAt = new Date().toISOString(), deadline = Date.now() + timeoutMs;
    await control.signal(api.id);
    let state;
    do {
      state = await control.inspect(api.id);
      if (!bound(state) || !await custody() || Date.now() > deadline) reject();
      if (!state.running) break;
      if (Date.now() >= deadline) reject();
      await new Promise(resolve => setTimeout(resolve, 50));
    } while (true);
    if (state.exitCode !== 0 || state.pid !== 0) reject();
    const proof = await control.proof(api.id, requestedAt);
    if (proof?.version !== 1 || !Number.isSafeInteger(proof.pid) || proof.pid <= 0
      || typeof proof.finishedAt !== 'string' || new Date(proof.finishedAt).toISOString() !== proof.finishedAt
      || Date.parse(proof.finishedAt) < Date.parse(requestedAt) || Date.parse(proof.finishedAt) > Date.now()) reject();
    const writersStopped = async () => {
      const c = await control.inspect(api.id);
      return bound(c) && c.running === false && c.pid === 0 && c.exitCode === 0 && await custody() && Date.now() <= deadline;
    };
    if (!await writersStopped()) reject();
    const receipt = await captureStoppedNode({ sources, destination,
      sourceCutoffAt: proof.finishedAt, writersStopped });
    return { receipt, drain: proof, cutoverAuthorized: false, realGateCompleted: false };
  } catch { reject(); }
}
