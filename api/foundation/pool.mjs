import pg from 'pg';

function safeError(error) {
  return new Error(/timeout|timed out/i.test(error?.message ?? '')
    ? 'Database timeout' : 'Database operation failed');
}

async function query(client, text, values) {
  try { return await client.query(text, values); }
  catch (error) { throw safeError(error); }
}

export function createDatabase(options = {}) {
  const limits = { max: 4, connectionTimeoutMillis: 5_000, idleTimeoutMillis: 10_000,
    statement_timeout: 5_000, query_timeout: 6_000, lock_timeout: 2_000 };
  const allowed = ['host', 'port', 'database', 'user', 'password', 'ssl', ...Object.keys(limits)];
  const ssl = options.ssl ?? true;
  if (Object.keys(options).some(key => !allowed.includes(key))
    || process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0'
    || ![true, false].includes(ssl) && (typeof ssl !== 'object' || ssl === null
      || Object.keys(ssl).some(key => !['ca', 'cert', 'key', 'rejectUnauthorized'].includes(key))
      || ssl.rejectUnauthorized === false)) {
    throw new Error('Invalid database configuration');
  }
  for (const key of Object.keys(limits)) {
    limits[key] = options[key] ?? limits[key];
    if (!Number.isSafeInteger(limits[key]) || limits[key] <= 0 || limits[key] > 2_147_483_647) {
      throw new Error('Invalid database configuration');
    }
  }
  const pool = new pg.Pool({ ...options, ...limits,
    ssl: typeof ssl === 'object' ? { ...ssl, rejectUnauthorized: true } : ssl });
  // pg evicts idle broken clients; consume its event without logging raw diagnostics.
  pool.on('error', () => {});
  return {
    query: (text, values) => query(pool, text, values),
    async transaction(work) {
      let client;
      try { client = await pool.connect(); }
      catch (error) { throw safeError(error); }
      let discard = false;
      let active = true;
      const onError = () => { discard = true; };
      client.on('error', onError);
      try {
        await client.query('BEGIN');
        const result = await work({ async query(text, values) {
          if (!active) throw new Error('Database transaction ended');
          return query(client, text, values);
        } });
        active = false;
        if ((await client.query('COMMIT')).command !== 'COMMIT') {
          throw new Error('Database transaction aborted');
        }
        return result;
      } catch (error) {
        active = false;
        try { await client.query('ROLLBACK'); }
        catch { discard = true; }
        throw safeError(error);
      } finally {
        client.release(discard);
        client.removeListener('error', onError);
      }
    },
    async close() {
      try { await pool.end(); }
      catch (error) { throw safeError(error); }
    },
  };
}
