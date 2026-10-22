import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import pg from 'pg';
import { runner } from 'node-pg-migrate';

const readJson = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const versions = readJson('./versions.json');
const manifest = readJson('./package.json');
const lock = readJson('./package-lock.json');
assert.equal(process.versions.node, versions.node);
assert.equal(manifest.engines.node, versions.node);
assert.equal(manifest.engines.npm, versions.npm);
assert.equal(process.env.npm_config_user_agent?.split(' ')[0], `npm/${versions.npm}`);
assert.equal(lock.lockfileVersion, 3);
assert.deepEqual(lock.packages[''].dependencies, manifest.dependencies);
assert.deepEqual(lock.packages[''].engines, manifest.engines);
assert.equal(typeof pg.Pool, 'function');
assert.equal(typeof runner, 'function');

console.log(`Node ${process.versions.node}; npm ${versions.npm}; ${process.platform}/${process.arch}`);
console.log(`Lock SHA-256: ${createHash('sha256').update(readFileSync(new URL('./package-lock.json', import.meta.url))).digest('hex')}`);
console.log('Package\tVersion\tLicense (metadata)\tNode engine (metadata)');
for (const [path, entry] of Object.entries(lock.packages)) {
  if (!path) continue;
  const installed = readJson(`./${path}/package.json`);
  assert.equal(installed.version, entry.version, path);
  assert.equal(installed.license, entry.license, path);
  assert.deepEqual(installed.engines, entry.engines, path);
  assert.match(entry.version, /^\d+\.\d+\.\d+$/, path);
  assert.match(entry.resolved, /^https:\/\/registry\.npmjs\.org\//, path);
  assert.match(entry.integrity, /^sha512-/, path);
  assert.ok(entry.license, path);
  const name = path.split('node_modules/').at(-1);
  if (manifest.dependencies[name]) assert.equal(entry.version, manifest.dependencies[name], name);
  console.log(`${name}\t${entry.version}\t${entry.license}\t${entry.engines?.node ?? '(not declared)'}`);
}
console.log('PASS: pinned runtime, lock/installed metadata, stable versions, integrity metadata and ESM exports.');
console.log('Engine range compatibility is checked by npm ci --engine-strict, not by this script.');
