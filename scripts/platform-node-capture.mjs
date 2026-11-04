// Copy phase only. The caller owns admission, writer inventory, stop and recovery.
import { constants, closeSync, fstatSync, fsyncSync, lstatSync, mkdirSync, openSync,
  readSync, readdirSync, realpathSync, renameSync, writeSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, isAbsolute, join, resolve, sep } from 'node:path';

// Best effort only: Windows and some filesystems refuse directory fsync.
function syncDir(path) {
  let fd;
  try { fd = openSync(path, 'r'); fsyncSync(fd); }
  catch { /* Unsupported directory fsync. */ }
  finally { if (fd !== undefined) { try { closeSync(fd); } catch { /* Closed. */ } } }
}

const reject = () => { throw new Error('NODE_CAPTURE_REJECTED'); };
const canonical = path => process.platform === 'win32' ? resolve(path).toLowerCase() : resolve(path);
const overlaps = (a, b) => a === b || a.startsWith(b + sep) || b.startsWith(a + sep);
const identity = info => [info.dev, info.ino, info.size, info.mtimeNs, info.ctimeNs].join(':');

function directory(path) {
  if (!isAbsolute(path) || lstatSync(path).isSymbolicLink() || !lstatSync(path).isDirectory()
    || canonical(realpathSync(path)) !== canonical(path)) reject();
}

function inventory(sources) {
  const files = [], directories = [];
  let bytes = 0;
  function walk(path, name, depth) {
    if (depth > 32 || files.length + directories.length >= 10_000) reject();
    const info = lstatSync(path, { bigint: true });
    if (info.isSymbolicLink()) reject();
    if (info.isDirectory()) {
      directories.push(name);
      for (const entry of readdirSync(path).sort()) walk(join(path, entry), `${name}/${entry}`, depth + 1);
    } else {
      if (!info.isFile() || info.nlink !== 1n) reject();
      bytes += Number(info.size);
      if (bytes > 4 * 1024 ** 3) reject();
      const fd = openSync(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
      try {
        if (identity(fstatSync(fd, { bigint: true })) !== identity(info)) reject();
        const hash = createHash('sha256'), buffer = Buffer.alloc(64 * 1024);
        let count, size = 0;
        while ((count = readSync(fd, buffer, 0, buffer.length, null))) {
          size += count;
          if (size > Number(info.size)) reject();
          hash.update(buffer.subarray(0, count));
        }
        if (size !== Number(info.size) || identity(fstatSync(fd, { bigint: true })) !== identity(info)) reject();
        files.push({ path: name, size, sha256: hash.digest('hex'), identity: identity(info) });
      } finally { closeSync(fd); }
    }
  }
  for (const source of sources) { directory(source.path); walk(source.path, source.name, 0); }
  return { files, directories };
}

export function validateCapturePaths({ sources, destination }) {
  if (!Array.isArray(sources) || sources.length < 2 || sources.length > 16) reject();
  const names = new Set();
  for (const source of sources) {
    if (!/^[a-z][a-z0-9_-]{0,31}$/.test(source.name) || names.has(source.name)) reject();
    names.add(source.name);
    directory(source.path);
  }
  if (!names.has('data') || !names.has('configuration') || !isAbsolute(destination)) reject();
  directory(dirname(destination));
  const paths = [...sources.map(source => canonical(source.path)), canonical(destination)];
  if (paths.some((path, i) => paths.slice(i + 1).some(other => overlaps(path, other)))) reject();
  try { lstatSync(destination); } catch (error) { if (error.code === 'ENOENT') return; throw error; }
  reject();
}

export async function captureStoppedNode({ sources, destination, writersStopped, sourceCutoffAt }) {
  try {
    if (!Array.isArray(sources) || sources.length < 2 || sources.length > 16 || typeof writersStopped !== 'function') reject();
    if (typeof sourceCutoffAt !== 'string' || !Number.isFinite(Date.parse(sourceCutoffAt))
      || new Date(sourceCutoffAt).toISOString() !== sourceCutoffAt || Date.parse(sourceCutoffAt) > Date.now()) reject();
    validateCapturePaths({ sources, destination });
    if (await writersStopped() !== true) reject();
    const writersStoppedAt = new Date().toISOString();
    const before = inventory(sources);
    if (!['data/db.json', 'data/secret'].every(name => before.files.some(file => file.path === name))
      || !before.files.some(file => file.path.startsWith('configuration/'))) reject();
    mkdirSync(destination, { mode: 0o700 }); // Exclusive: never reuse a previous or partial destination.
    for (const name of before.directories) mkdirSync(join(destination, name), { mode: 0o700 });
    for (const file of before.files) {
      if (await writersStopped() !== true) reject();
      const source = sources.find(entry => file.path.startsWith(entry.name + '/'));
      const target = join(destination, file.path);
      const input = openSync(join(source.path, file.path.slice(source.name.length + 1)),
        constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
      try {
        if (identity(fstatSync(input, { bigint: true })) !== file.identity) reject();
        const output = openSync(target, 'wx', 0o600);
        try {
          const buffer = Buffer.alloc(64 * 1024);
          let count, size = 0;
          while ((count = readSync(input, buffer, 0, buffer.length, null))) {
            size += count;
            if (size > file.size) reject();
            for (let offset = 0; offset < count;) {
              const written = writeSync(output, buffer, offset, count - offset);
              if (!written) reject();
              offset += written;
            }
          }
          if (size !== file.size || identity(fstatSync(input, { bigint: true })) !== file.identity) reject();
          fsyncSync(output);
        } finally { closeSync(output); }
      } finally { closeSync(input); }
    }
    if (await writersStopped() !== true) reject();
    if (JSON.stringify(inventory(sources)) !== JSON.stringify(before)) reject();
    const copied = inventory(sources.map(source => ({ name: source.name, path: join(destination, source.name) })));
    const content = value => ({ directories: value.directories,
      files: value.files.map(({ path, size, sha256 }) => ({ path, size, sha256 })) });
    if (JSON.stringify(content(copied)) !== JSON.stringify(content(before))) reject();
    if (await writersStopped() !== true) reject();
    const receipt = { version: 1, sourceType: 'node_json', sourceCutoffAt, writersStoppedAt, capturedAt: new Date().toISOString(),
      ...content(before), operationalAcceptance: false, importAuthorized: false };
    const temporary = join(destination, 'capture.json.tmp');
    const fd = openSync(temporary, 'wx', 0o600);
    try { writeFileSync(fd, JSON.stringify(receipt)); fsyncSync(fd); } finally { closeSync(fd); }
    for (const name of [...before.directories].reverse()) syncDir(join(destination, name));
    renameSync(temporary, join(destination, 'capture.json'));
    syncDir(destination);
    syncDir(dirname(destination));
    return receipt;
  } catch { reject(); }
}
