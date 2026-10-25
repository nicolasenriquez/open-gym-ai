import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import pg from 'pg';
import { runner } from 'node-pg-migrate';

const readJson = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const versions = readJson('./versions.json');
const manifest = readJson('./package.json');
const inventory = readJson('./dependency-licenses.json');
const lock = readFileSync(new URL('./pnpm-lock.yaml', import.meta.url));
assert.equal(process.versions.node, versions.node);
assert.equal(manifest.engines.node, versions.node);
assert.equal(manifest.engines.pnpm, versions.pnpm);
assert.equal(process.env.npm_config_user_agent?.split(' ')[0], `pnpm/${versions.pnpm}`);
assert.equal(createHash('sha256').update(lock).digest('hex'), inventory.lockSha256);
assert.equal(typeof pg.Pool, 'function');
assert.equal(typeof runner, 'function');

// Preserve the reviewed version/license/engine inventory across the manager migration.
const observed = new Map();
const store = new URL('./node_modules/.pnpm/', import.meta.url);
for (const folder of readdirSync(store)) {
  const modules = new URL(`./${folder}/node_modules/`, store);
  if (!existsSync(modules)) continue;
  for (const entry of readdirSync(modules)) {
    const names = entry.startsWith('@')
      ? readdirSync(new URL(`./${entry}/`, modules)).map(name => `${entry}/${name}`)
      : [entry];
    for (const name of names) {
      const path = new URL(`./${name}/package.json`, modules);
      if (!existsSync(path)) continue;
      const installed = JSON.parse(readFileSync(path, 'utf8'));
      observed.set(`${installed.name}@${installed.version}`, installed);
    }
  }
}
const expected = new Map(inventory.packages.map(item => [`${item.name}@${item.version}`, item]));
assert.deepEqual([...observed.keys()].sort(), [...expected.keys()].sort());
console.log(`Node ${process.versions.node}; pnpm ${versions.pnpm}; ${process.platform}/${process.arch}`);
console.log(`Lock SHA-256: ${inventory.lockSha256}`);
for (const [key, entry] of expected) {
  const installed = observed.get(key);
  assert.equal(installed.license, entry.license, key);
  assert.deepEqual(installed.engines, entry.engines, key);
  assert.match(entry.version, /^\d+\.\d+\.\d+$/, key);
  assert.match(entry.integrity, /^sha512-/, key);
  assert.ok(entry.license, key);
  if (manifest.dependencies[entry.name]) assert.equal(entry.version, manifest.dependencies[entry.name]);
  console.log(`${key}\t${entry.license}\t${entry.engines?.node ?? '(not declared)'}`);
}
console.log('PASS: pinned runtime, frozen-lock hash, installed metadata, licenses and ESM exports.');
