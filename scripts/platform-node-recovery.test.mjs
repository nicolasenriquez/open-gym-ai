import test from 'node:test';
import { backupProof } from './platform-backup-proof.mjs';

test('Node capture -> PostgreSQL import -> verified encrypted backup -> quarantined isolated restore',
  { timeout: 540_000 }, () => backupProof('node-chain'));
