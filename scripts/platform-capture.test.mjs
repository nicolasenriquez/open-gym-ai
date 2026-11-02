import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

test('server health probes allow capture while application clients with the same name remain blocked', { timeout: 180_000 }, () => backupProof('health-probe'));
test('unrelated containers may disappear during inspection but an uninspectable live container blocks capture', { timeout: 240_000 }, () => backupProof('transient-container'));
