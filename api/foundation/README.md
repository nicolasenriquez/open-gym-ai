# PostgreSQL Foundation — synthetic verification tooling

Isolated package for `add-postgres-foundation`. It is **not** imported by
`api/server.js`, installed by `api/Dockerfile`, or authoritative for existing data.
No ORM or new production persistence is introduced.

All 18 synthetic tasks are complete. Results, fail-first history, failures,
versions/licenses and restore measurements are consolidated in
[archived design — evidence](../../openspec/changes/archive/2026-10-22-add-postgres-foundation/design.md#evidencia-consolidada-de-entrega);
[task traceability](../../openspec/changes/archive/2026-10-22-add-postgres-foundation/tasks.md).
The current contract is [postgres-foundation](../../openspec/specs/postgres-foundation/spec.md).
Raw execution logs were intentionally removed after consolidation. This is a
summary of observed runs, not retained stdout/stderr or fresh runtime proof.
**G1 operational and G0/G2–G5 remain unproven.** No authority cutover is authorized.

## Run local / CI

From the repository root, with trusted Docker Engine Linux and Compose v2+:

```bash
node api/foundation/environment.mjs config
node api/foundation/environment.mjs run all
node --test api/foundation/environment.test.mjs api/foundation/configuration.test.mjs api/foundation/environment-docker.test.mjs
```

Focused groups: `environment`, `pool`, `migrations`, `isolation`, `recovery`:

```bash
node api/foundation/environment.mjs run pool
```

Host Node only orchestrates Docker. The image runs pinned **Node 22.23.2 as UID
1000**, PostgreSQL/tools **18.6**; exact digests in `versions.json`. First build
uses verified TLS and `npm ci --ignore-scripts --engine-strict`, followed by
`check:toolchain`. No host installation. Missing Docker/BD, unknown groups,
unhealthy startup, failed tests or cleanup return nonzero, never skip silently.

`all` runs environment guards, pool, migrations, isolation and recovery
sequentially and stops on failure. Recorded result: **55/55 PASS** (4/12/7/20/12),
zero skips. Harness recorded **9/9 PASS**, including explicit failure without BD.
`.github/workflows/test.yml` uses the same entry on Ubuntu. Filters cover
`api/**`, Compose, this OpenSpec change and workflow; no `continue-on-error`.
Remote Actions execution and branch protection were not verified/changed.

## Isolation and cleanup

The CLI supplies an absolute Compose file/empty env file, strips inherited
`COMPOSE_*` overrides, and generates `opengym-foundation-test-<16 hex>`.
Each run owns an internal network, volume and runner image tag. No public ports,
instance `.env`, bind mounts, Docker socket, data/, coach credentials, personal
media or normal API/web services. Credentials are public synthetic fixtures.
Runner root is read-only, /tmp temporary, capabilities dropped, no privilege
escalation. Docker build context explicitly allows only tooling/manifests and
migrations; verification scripts are not included in the runner image.

Cleanup runs on success/failure, inspecting the entire target set for exact
project/marker/service ownership and names before deleting only those IDs/names.
No prune, broad prefixes, `--remove-orphans`, or unrelated resource removal.
Base images/build cache remain. Ownership labels prevent mistakes, not malicious
Docker administrators. Do not change Docker context during a run.

After hard kill/daemon loss, use the **exact project printed by that run**:

```bash
node api/foundation/environment.mjs cleanup opengym-foundation-test-<16-hex-from-run>
```

Replace the placeholder. Never clean an active run. Failed cleanup requires
operator attention. Guard tests reject non-test names/mixed ownership before
modification and preserve an unrelated sentinel volume.

Quiet static config check (does not start services):

```bash
docker compose --env-file api/foundation/empty.env -f compose.foundation.yml \
  -p opengym-foundation-test config --quiet
```

## Public seams and safety limits

### Pool

`createDatabase(options)` exposes `query(text, values)`, `transaction(work)` and
`close()`. Callback receives only query. Same leased client handles BEGIN/work/
COMMIT or ROLLBACK; failed rollback/broken connections are discarded. Aborted
COMMIT rejects; handles expire after callback. Await every query. Trusted work
installs `set_config('app.owner_id', value, true)` inside the transaction; no
session-scoped context or transaction control through this interface.

Accepted connection fields: host, port, database, user, password, ssl. Unknown
options/DSNs rejected to prevent TLS overrides. TLS defaults to verified; private
synthetic network explicitly uses false. Only ca/cert/key/rejectUnauthorized TLS
fields accepted; insecure TLS/custom identity callbacks/global TLS bypass fail.

| Limit | Default |
| --- | ---: |
| max | 4 |
| connectionTimeoutMillis | 5000 ms |
| idleTimeoutMillis | 10000 ms |
| statement_timeout | 5000 ms |
| query_timeout | 6000 ms |
| lock_timeout | 2000 ms |

Overrides are positive safe integers within signed 32-bit range, not production
sizing. close drains work; SQL timeouts do not bound arbitrary JavaScript.
Errors are generic without driver fields/cause/SQL/payload. Captured diagnostic
checks do not audit PostgreSQL server logs. No provider TLS handshake claimed.

### Migration process (inside disposable runner only)

```bash
node migrate.mjs bootstrap
node migrate.mjs up
node migrate.mjs up <directory> <schema> [count]
```

Bootstrap provisions restricted migrator/runtime/Training logins transactionally
with its own lock; public database/schema access revoked. Up connects as migrator
and applies only infrastructure `migrations/001-foundation.cjs`, history
`foundation.pgmigrations`. No identity/Training/Recovery tables. Runtime is not
owner/superuser/BYPASSRLS and has no elevating memberships or DDL/TRUNCATE grants.

Fixture paths must be canonical `/tmp/foundation-migrations-*`, schema
`foundation_probe_<16 hex>`, count positive safe integer. Fixtures/history are
separate from committed infrastructure. node-pg-migrate uses session advisory
lock in fail mode, checkOrder and singleTransaction; finally closes connection.
No fake/down/no-lock exposed. Applied migrations stay immutable; no checksum
enforcement claimed. Recreate disposable environment instead of rollback.
Concurrency/readiness/interruption tests use IPC plus pg_locks, not sleeps.

### RLS fixture

A/B are synthetic data owners sharing a real restricted runtime login, pool max
1. Migrator-owned `foundation_isolation_<16 hex>` fixture enables/forces RLS;
USING/WITH CHECK compare owner_id to
`nullif(current_setting('app.owner_id', true), '')`. Missing/empty context denies.
Runtime gets USAGE/CRUD, Training CONNECT only and no fixture grants. Fixtures
are retired after tests. This does not validate HTTP auth or Recovery policies.

### Encrypted recovery (inside disposable runner only)

```bash
node recovery.mjs backup <bundle-dir> <key-file> <40-hex-revision>
node recovery.mjs copy <bundle-dir> <transfer-dir>
node recovery.mjs restore <transfer-dir> <key-file> <foundation_restore_16hex>
```

Paths are canonical/private/owned under `/tmp/foundation-recovery-*`; regular
single-link files, exclusive writes and empty destinations. Separate key is 32
random bytes, mode 0600. Bundle contains only backup.enc/manifest.json: AES-256-GCM
12-byte nonce/16-byte tag/ciphertext, raw manifest as AAD. Manifest records revision,
history, server/tools, source, owners/roles, cipher and dump SHA-256. Tests use a
declared synthetic revision, not Git HEAD.

Repeatable-read read-only snapshot exported to custom pg_dump and metadata.
Copy excludes key/plaintext. Restore authenticates/hash-checks/lists archive
before connecting; generated distinct target must be bootstrap-owned and empty,
including routines/types/ACLs. Advisory lock serializes cooperators;
pg_restore single-transaction/exit-on-error preserves ownership/grants/RLS,
without create/clean. Database ACL applied afterward: failure means discard target.
libpq gets fixed target/allowlisted environment, no DSN/services/external outputs.

Global roles explicitly provisioned by bootstrap are shared across source/target
in one cluster, not backed up or reprovisioned in a clean cluster. Tool buffers
32 MiB/timeouts 20 s suit small fixtures only. Recorded two-row restore CLI
74.436 ms, with verification 94.969 ms, complete flow 227.922 ms, excluding
setup/build/teardown. **Not off-host/PITR/production RPO/RTO proof.**

## Legacy compatibility — recorded results

API **601**, frontend **5069**, MCP **95** tests passed, together with build,
locales/source strings, fatigue probes, loadable API/MCP and generated assets/docs
checks. Build warnings for chunks/mixed imports remain.

The normal API image passed HTTP health/config, JSON VAPID and graceful termination
checks on Linux UID 1000/Node 22.23.2 with no network/database, read-only root and
disposable data. Foundation, pg, AI runtime and npm were absent.

The one-off suite wrapper and image smoke script were removed by user request.
These are historical results, not a retained automated image-smoke check. Existing
suite/build commands remain in CI and design / Verification Commands; repeating
the exact image assertions requires recreating that check.

## Reproduce toolchain verification

`package-lock.json` v3 fixes 36 packages and license/engine metadata; direct pg
8.23.1/node-pg-migrate 9.0.0 MIT. All declared licenses MIT/ISC/BlueOak-1.0.0;
retain notices. No legal/OS package audit claimed. Optional @types/pg/pg-native
absent by design. npm audit reported zero vulnerabilities at execution time only.

```bash
foundation_source="$(cd api/foundation && (pwd -W 2>/dev/null || pwd))"
node_image="$(node -p 'require("./api/foundation/versions.json").nodeImage')"
MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 \
  --mount "type=bind,source=$foundation_source,target=/source,readonly" \
  --workdir /tmp "$node_image" sh -ec '
    work=$(mktemp -d)
    cd "$work"
    cp /source/package*.json /source/versions.json /source/check-toolchain.mjs .
    node --version
    npm --version
    npm config get strict-ssl
    npm ci --ignore-scripts --engine-strict --no-audit --no-fund
    npm run check:toolchain
    npm ls --all
    npm audit --json
  '
```

Use existing lock, never re-resolve for reproduction or disable TLS. Checker must
run via npm to verify npm version. node-pg-migrate CLI reports unknown version;
use installed/locked metadata. Pull/cache/version inspection is not DB proof.

No real-instance configuration or data was modified. Provider/TLS/pooler sizing,
representative recovery and production gates require separate authorization and
proof. See consolidated OpenSpec evidence for known failures and exact scope.
