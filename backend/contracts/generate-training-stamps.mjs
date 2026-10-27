// Freeze the existing Node behavioral cases before comparing the Python port.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { stampPut } from '../../api/sync-stamps.js';

const source = fs.readFileSync(new URL('../../api/test/sync-stamps.test.js', import.meta.url), 'utf8');
const vectors = [];
let scenario;
function capture(current, next, options) {
  const input = structuredClone({ current, next, options });
  const report = {};
  stampPut(current, next, { ...options, report });
  vectors.push({ scenario, ...input, expected: structuredClone(next), corrected: report.changed === true });
}
const cases = source.replace(/^import .*;\r?\n/gm, '')
  .replace(/^const API = .*;\r?\n/m, '');
vm.runInThisContext('(function(crypto, assert, test, stampPut) {' + cases + '\n})')(crypto, assert,

  function test(name, fn) {
    if (fn.constructor.name === 'AsyncFunction') return; // HTTP cases use the real Python/PG suite.
    scenario = name;
    fn();
  },
  capture);
assert.ok(vectors.length >= 30);
for (const value of [null, false, 0, '😃 café', { 2: 'two', 10: 'ten', a: 1 }, [0, 1e-6, 1e-7, 1e21]]) {
  scenario = `prior hashes preserve JSON type and UTF-16: ${JSON.stringify(value)}`;
  capture({ setting: value, workouts: [] }, { setting: 'new', workouts: [] }, { overRead: true, now: 1800000000000 });
}
scenario = 'absent plan-day value differs from null';
capture({ exNotes: { x: null }, workouts: [] }, { exNotes: {}, workouts: [] }, { overRead: true, now: 1800000000000 });
capture({ exNotes: {}, workouts: [] }, { exNotes: { x: null }, workouts: [] }, { overRead: true, now: 1800000000000 });
scenario = 'legacy numeric stamp strings retain Number semantics';
capture({ edited: { setting: '0x10' }, deleted: { favEx: { gone: '0b10000' } } },
  { setting: 3, edited: { setting: 2 }, deleted: { favEx: { gone: 4 } } }, { stamped: true, now: 1800000000000 });
fs.writeFileSync(new URL('./training-stamps.v1.json', import.meta.url), JSON.stringify({
  sourceSha256: crypto.createHash('sha256').update(fs.readFileSync(new URL('../../api/sync-stamps.js', import.meta.url))).digest('hex'),
  vectors,
}, null, 2) + '\n');
console.log(`${vectors.length} independent Node stamp vectors`);
