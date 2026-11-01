import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

test('restore loads only a new quarantined isolated target', () => backupProof('restore'));
