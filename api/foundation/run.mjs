import { readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';

const versions = JSON.parse(readFileSync(new URL('./versions.json', import.meta.url)));
const [group = 'environment', ...extra] = process.argv.slice(2);
try {
  if (!['environment', 'pool'].includes(group) || extra.length) throw new Error('Foundation slice not implemented');
  if (process.env.PGHOST !== 'foundation-db' || process.env.PGPORT !== '5432'
    || process.env.PGDATABASE !== 'foundation_test' || process.env.PGUSER !== 'foundation_bootstrap'
    || process.env.PGPASSWORD !== 'synthetic-foundation-only') {
    throw new Error('Refusing non-test database target');
  }
  if (process.versions.node !== versions.node || process.getuid?.() === 0) {
    throw new Error('Foundation requires pinned Node and a non-root runner');
  }
  const { default: pg } = await import('pg');
  const client = new pg.Client({ host: 'foundation-db', port: 5432, database: 'foundation_test',
    user: 'foundation_bootstrap', password: process.env.PGPASSWORD, ssl: false,
    connectionTimeoutMillis: 5_000, query_timeout: 5_000, statement_timeout: 5_000 });
  try {
    await client.connect();
    const { rows: [row] } = await client.query('SELECT current_database() AS db, current_setting(\'server_version\') AS version');
    if (row.db !== 'foundation_test' || row.version.split(' ')[0] !== versions.postgres) {
      throw new Error('Unexpected synthetic database version');
    }
    console.log(`Foundation environment ready: Node ${versions.node}; PostgreSQL ${versions.postgres}`);
  } finally {
    await client.end();
  }
  if (group === 'pool') {
    const child = spawn(process.execPath, ['--test', '--test-concurrency=1', 'pool.test.mjs'], { stdio: 'inherit' });
    process.exitCode = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', code => resolve(code ?? 1));
    });
  }
} catch (error) {
  const safeMessages = ['Foundation slice not implemented', 'Refusing non-test database target',
    'Foundation requires pinned Node and a non-root runner'];
  console.error(safeMessages.includes(error.message) ? error.message : 'Foundation environment check failed');
  process.exitCode = 1;
}
