import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

test('host backup publishes a verified encrypted recovery bundle', () => backupProof('bundle'));
