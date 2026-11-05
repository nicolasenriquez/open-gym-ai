import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

test('forward repair preserves acknowledged writes on the surviving destination', { timeout: 540_000 }, () => backupProof('repair'));
test('missing acknowledged write keeps maintenance and surviving bytes', { timeout: 300_000 }, () => backupProof('repair-missing'));
test('incompatible immutable release keeps maintenance and surviving bytes', { timeout: 300_000 }, () => backupProof('repair-incompatible'));
test('same write ID with different content cannot certify preservation', { timeout: 300_000 }, () => backupProof('repair-content'));
test('media with different bytes cannot certify preservation', { timeout: 300_000 }, () => backupProof('repair-media'));
