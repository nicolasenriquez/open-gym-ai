// One process owns HTTP, scheduled writers and detached asynchronous work.
const timers = new Set(), pending = new Set();
let closing = false, failed = false;
export const isDraining = () => closing;

export function track(promise) {
  pending.add(promise);
  promise.then(() => pending.delete(promise), () => { failed = true; pending.delete(promise); });
  return promise;
}

export function interval(fn, ms) {
  if (closing) return null;
  const timer = setInterval(() => { if (!closing) fn(); }, ms);
  timers.add(timer);
  return timer;
}

export function later(fn, ms) {
  if (closing) return null;
  const timer = setTimeout(() => { timers.delete(timer); if (!closing) fn(); }, ms);
  timers.add(timer);
  return timer;
}

export function cancelTimer(timer) {
  timers.delete(timer);
  clearTimeout(timer);
}

export async function drain(server, timeoutMs) {
  if (closing) return;
  closing = true;
  for (const timer of timers) { clearTimeout(timer); clearInterval(timer); }
  timers.clear();
  const deadline = setTimeout(() => { console.error('NODE_DRAIN_FAILED'); process.exit(1); }, timeoutMs);
  try {
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
    // Completed handlers/jobs can start detached push work or the next queued job.
    while (pending.size) await Promise.allSettled([...pending]);
    if (failed) throw new Error('Unsettled work');
    const proof = 'NODE_DRAINED ' + JSON.stringify({ version: 1, pid: process.pid, finishedAt: new Date().toISOString() }) + '\n';
    process.stdout.write(proof, () => { clearTimeout(deadline); process.exit(0); });
  } catch {
    console.error('NODE_DRAIN_FAILED');
    process.exit(1);
  }
}
