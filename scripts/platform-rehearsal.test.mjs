import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

test('monthly rehearsal measures the full declared incident and never credits an unreviewed restore', { timeout: 540_000 }, () => backupProof('restore', true, true));
