import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

test('local recovery delivers only a new verified access without restoring doubtful credentials', () => backupProof('restore', true));
