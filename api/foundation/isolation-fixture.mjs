// Synthetic fixtures only: these policies do not define the Recovery domain schema.
export async function prepareIsolationFixture(client, schema) {
  if (!/^foundation_isolation_[a-f0-9]{16}$/.test(schema)) throw new Error('Invalid isolation fixture schema');
  await client.query(`CREATE SCHEMA "${schema}";
    CREATE TABLE "${schema}".owner_probe (id integer PRIMARY KEY, owner_id text NOT NULL, note text NOT NULL);
    GRANT USAGE ON SCHEMA "${schema}" TO foundation_runtime;
    GRANT SELECT, INSERT, UPDATE, DELETE ON "${schema}".owner_probe TO foundation_runtime;`);
  await client.query(`INSERT INTO "${schema}".owner_probe VALUES (1, $1, 'initial-a'), (2, $2, 'initial-b')`, ['owner-a', 'owner-b']);
  await client.query(`ALTER TABLE "${schema}".owner_probe ENABLE ROW LEVEL SECURITY;
    ALTER TABLE "${schema}".owner_probe FORCE ROW LEVEL SECURITY;
    CREATE POLICY owner_isolation ON "${schema}".owner_probe FOR ALL TO foundation_runtime
      USING (owner_id = nullif(current_setting('app.owner_id', true), ''))
      WITH CHECK (owner_id = nullif(current_setting('app.owner_id', true), ''));`);
}
