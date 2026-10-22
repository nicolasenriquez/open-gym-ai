# PostgreSQL Foundation — isolated toolchain, environment, pool and migrations

Isolated dependency resolution for `add-postgres-foundation`. This package is **not**
imported by `api/server.js`, installed by `api/Dockerfile`, or part of the normal
API dependency tree. Both dependencies are here because the approved architecture
requires `pg` and `node-pg-migrate`; no ORM or license-scanner dependency is added.
Future Foundation code belongs in this isolated package unless a later approved
slice establishes another boundary.

Tasks **1.1–1.3** are delivered here. The environment runner starts only synthetic
PostgreSQL and verifies connectivity/version, not domain persistence. The legacy
API also passes its existing HTTP/JSON smoke without PostgreSQL. Tasks 2.1–2.3 add
pool/transaction tests, implementation and the verified synthetic checkpoint.
Tasks 3.1–3.3 deliver the isolated migrator and its synthetic verification checkpoint.
Tasks 4.1–4.3 deliver synthetic RLS and its isolation verification checkpoint.
Tasks 5.1–5.3 deliver fail-first tests, synthetic recovery implementation and its
timed verification checkpoint. CI remains pending. No real instance configuration or data is
mounted. G1 operational and all production gates remain unproven.

## Run the isolated environment (task 1.2)

From the repository root, with Docker Engine Linux and Compose v2+ available:

```bash
node api/foundation/environment.mjs run environment
```

The host Node only orchestrates Docker; the image runs **Node 22.23.2 as UID 1000**.
The first build downloads the already locked dependencies with verified TLS and
`npm ci --ignore-scripts --engine-strict`, then reruns `check:toolchain`. There is
no host installation. The runner is read-only with a temporary `/tmp`, no Linux
capabilities and no privilege escalation. The default group is `environment`;
`pool`, `migrations` and `isolation` run their implemented behavioral tests;
`recovery` runs the implemented encrypted backup/copy/restore tests. Unimplemented
groups (including `all`) fail explicitly rather than pretend that later database
proofs ran.

The CLI supplies one absolute Compose file and the explicit empty env file,
strips inherited `COMPOSE_*` overrides, and generates a new project name
`opengym-foundation-test-<16 random hex digits>`. Each project has its own private
**internal** network and named PostgreSQL volume; neither service publishes ports.
There are no bind mounts, Docker socket mounts, real `.env` files, inherited
instance credentials, API/web services, or external volumes/networks in the stack.
Only `api/foundation/` is the build context; its `.dockerignore` allows source,
manifests and version metadata, not evidence, local dependencies or env files.
The committed credentials are deliberately public synthetic fixtures. The
bootstrap identity is for this disposable environment only; restricted roles
belong to slice 3, not this readiness check.

After health readiness, the test container checks its fixed database target,
connects with explicit `pg.Client` options, queries the database name and server
version, closes the client and exits. Connection/query timeouts are 5 seconds.
This does **not** implement the transaction/pool API from slice 2. The normal API
health contract is unchanged.

A `finally` block cleans up after success or failure. Cleanup first inspects the
**whole** target set: exact project label, synthetic marker, allowed service
labels and exact volume/network/image-tag names. Any unexpected resource aborts
before deletion. It then removes only those inspected container IDs (without
`--volumes`), the named volume/network and this run's image tag. No `down
--remove-orphans`, prune, broad name-prefix deletion or unrelated resource removal
is used. Base images and Docker build cache remain cached. The CLI refuses
non-test project names before accessing Docker. Labels/names are accidental-target
guards, not protection against a malicious Docker administrator who can forge
labels. Use a trusted Docker context; the tool does not change it.

`SIGINT`/`SIGTERM` during a Docker command trigger the normal failure/cleanup path.
After a hard kill, lost daemon or interrupted cleanup, use the **exact** project
name printed before resource creation:

```bash
node api/foundation/environment.mjs cleanup opengym-foundation-test-<16-hex-from-run>
```

The placeholder above must be replaced, not pasted literally. Cleanup never
accepts a database URL or an arbitrary Compose project. Do not run it concurrently
with an active run of that same project. Missing Docker/DB, unhealthy startup,
runner errors and cleanup failures return nonzero. A failed cleanup requires
operator attention; it is not reported as a successful run.

### Configuration and focused regressions

```bash
# Effective config as JSON (contains only the public synthetic credentials):
node api/foundation/environment.mjs config
# Equivalent quiet static check, never starts the normal stack:
docker compose --env-file api/foundation/empty.env -f compose.foundation.yml \
  -p opengym-foundation-test config --quiet
# CLI/config/cleanup/integrated environment tests, using real Docker resources:
node --test api/foundation/environment.test.mjs \
  api/foundation/configuration.test.mjs api/foundation/environment-docker.test.mjs
```

The config regression runs from a temporary directory containing a hostile
**synthetic** `.env`, with conflicting inherited Compose/instance variables; it
checks the effective config rather than reading real instance files. Cleanup
regressions preserve an unrelated sentinel volume and refuse mixed ownership
without partially deleting the validated resources. Test teardown deletes only
its own exact IDs/names. Missing Docker fails these tests; there are no skips.

The two no-Docker guard regressions also run in the pinned Node 22 container;
[`evidence/environment-node22.txt`](evidence/environment-node22.txt) preserves that
proof. Host Docker orchestration tests use host Node 24.14.0, not claimed as Node
22 runtime validation. [`evidence/environment-green.txt`](evidence/environment-green.txt)
records all focused regressions, and [`evidence/environment-run.txt`](evidence/environment-run.txt)
records the real Node 22/PostgreSQL 18.6 run and cleanup. Fail-first artifacts are
`environment-red.txt`, `configuration-red.txt`, `cleanup-red.txt`,
`runner-target-red.txt` and `run-red.txt` under `evidence/`: each failed on a
behavioral assertion against a loadable initial CLI/runner, not an import or
missing-Docker error. The mixed-ownership and image-tag assertions additionally
characterize the implemented safety boundary. The environment CLI and effective
Compose config seams were explicitly approved for task 1.2.

## Shared prerequisite verification (task 1.3)

Config and target guards reuse the focused regressions above, not duplicate tests.
[`evidence/prerequisite-checks.txt`](evidence/prerequisite-checks.txt) records 3
passing CLI/config tests and the quiet Compose validation;
[`evidence/prerequisite-node22.txt`](evidence/prerequisite-node22.txt) records both
guard tests passing in the pinned Node 22 image with networking disabled.

The existing legacy smoke runs unchanged at the approved HTTP/consumer seam:
health (200 writable, 503 read-only and recovery), JSON durability, unreadable-file
recovery, revisions, write lineage and reset stamps. Reproduce from the repository
root in Bash, using **already installed** `api/node_modules` and the cached pinned
image (missing prerequisites fail; this command installs nothing):

```bash
api_source="$(cd api && (pwd -W 2>/dev/null || pwd))"
node_image="$(node -p 'require("./api/foundation/versions.json").nodeImage')"
MSYS_NO_PATHCONV=1 docker run --rm --pull never --network none --read-only \
  --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp --mount "type=bind,source=$api_source,target=/source,readonly" \
  --workdir /tmp --env PGHOST=127.0.0.1 --env PGPORT=1 "$node_image" sh -ec '
    work=$(mktemp -d)
    cd "$work"
    cp /source/*.js /source/package*.json .
    cp -R /source/node_modules /source/coach /source/test .
    node --input-type=module <<NODE
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
assert.equal(process.versions.node, "22.23.2");
assert.equal(process.getuid(), 1000);
assert.ok(!existsSync("foundation"));
assert.throws(() => createRequire(import.meta.url).resolve("pg"), { code: "MODULE_NOT_FOUND" });
console.log("Node 22.23.2; UID 1000; network=none; tmpfs runtime/data; Foundation and pg absent");
NODE
    node --test test/durable.test.js test/server-db-unreadable.test.js \
      test/server-data-rev.test.js test/server-data-wid.test.js \
      test/server-data-reset.test.js test/server-health-writable.test.js
  '
```

Only API code/dependencies are read from the host; no real `.env`, data directory,
coach credentials or media is loaded. Tests create synthetic accounts, keys and
JSON under tmpfs; loopback HTTP is reachable only inside the container, with no
published ports or reachable PostgreSQL. `--rm` discards the container and tmpfs.
No Foundation source or `pg` package is present in the staged runtime. This checks
source compatibility with the existing local dependency snapshot, **not** a fresh
API dependency installation or the normal Alpine image build (task 6.2).

Result: **15 passed, 0 failed, 0 skipped**, including the POSIX checks, in
[`evidence/legacy-smoke.txt`](evidence/legacy-smoke.txt). No runtime behavior or
existing test was changed, so this is passing characterization, not a fabricated
TDD RED. The initial direct Windows-bind run failed 7/14 tests on 20-second boot
timeouts (`legacy-smoke-bind-failed.txt`); health alone failed too
(`legacy-smoke-probe.txt`). Changing only execution storage to tmpfs made that
same health test pass in 0.3 s (`legacy-smoke-probe-tmpfs.txt`) and the original
full smoke pass in about 6 s. The reproduction above avoids that bind-import
bottleneck without changing timeouts or relaxing assertions. These diagnostic
failures remain recorded; they are not a PostgreSQL regression or TDD proof.

| Slice | Reproducible entry/status |
| --- | --- |
| 1: environment | `node api/foundation/environment.mjs run environment`; config/guard and no-DB smoke commands above |
| 2: pool | `node api/foundation/environment.mjs run pool`: 2.1–2.3 complete, synthetic checkpoint PASS |
| 3: migrations | `node api/foundation/environment.mjs run migrations`: 3.1–3.3 complete, synthetic checkpoint PASS |
| 4: isolation | `node api/foundation/environment.mjs run isolation`: 4.1–4.3 complete, synthetic checkpoint PASS |
| 5: recovery | `node api/foundation/environment.mjs run recovery`: 5.1–5.3 complete, 12/12 PASS; synthetic timed checkpoint verified |
| 6: complete CI run | Pending tasks 6.1–6.3; no runnable proof yet |

The `environment`, `pool`, `migrations`, `isolation` and `recovery` groups are passing. Other groups still fail explicitly; commands for later
slices will be documented when delivered, not advertised as working.
The shared prerequisite checkpoint is verified; this does not complete Foundation
or establish operational G1.

## Pool and transaction fail-first contract (task 2.1)

```bash
node api/foundation/environment.mjs run pool
```

This command now exits **0** after task 2.2. The existing guarded runner
validates the target, Node 22.23.2/non-root runtime and PostgreSQL 18.6 before
launching `pool.test.mjs` through node:test. The existing cleanup runs even when
tests fail; no extra Compose topology or dependency is introduced. Existing
`environment` behavior is unchanged.

The public seam is `createDatabase(options)` returning `query(text, values)`,
`transaction(work)` and `close()`. The transaction callback receives only a query
interface. The original task 2.1 baseline only leased/released a pg client; task
2.2 now implements transaction control and safe errors. This module remains
isolated from the normal API and its image; no existing data uses PostgreSQL.

Six tests use real SQL through this public interface with a one-connection pool:
write then throw leaves no persisted row; local context across commit and failure;
saturation with bounded acquisition and capacity recovery; connection termination
followed by recovery; and explicit close rejecting subsequent work. Assertions
ensure the callback reached its intended failure, so a setup/assertion failure
cannot masquerade as successful rollback. Only the test's own backend is
terminated; the table fixture lives in the disposable database. No migration or
RLS policy is introduced.

Historical task 2.1 result: **4 behavioral failures, 2 passes, 0 skipped/cancelled**.
The expected REDs show a persisted `must-roll-back` row, missing transaction-local
context on both paths, and failure of the next operation after termination.
Saturation/capacity recovery and explicit close already pass via pg. Import,
syntax, runtime prerequisites and database connectivity succeeded. The child
exited and owned resources were cleaned; this is not a missing-method or missing
database RED. Full output: [`evidence/pool-red.txt`](evidence/pool-red.txt).

The six existing CLI/configuration/cleanup/environment regressions still pass:
[`evidence/pool-harness-regressions.txt`](evidence/pool-harness-regressions.txt).
That evidence records the tests-only boundary of task 2.1. No full legacy suite,
TLS handshake/privilege/RLS proof, CI integration or operational G1 was claimed. Self-review at the approved public
seam found no blocker for retaining this isolated RED contract; normal API
callers/manifests/Dockerfile and repository rules are unchanged.

## Pool implementation (task 2.2)

`createDatabase(options)` accepts explicit `host`, `port`, `database`, `user`,
`password`, `ssl` and the six limits below. Unknown options, including
`connectionString`, are rejected: DSN SSL parameters must not replace verified
TLS settings. TLS defaults to enabled with certificate verification; the private
synthetic network explicitly uses `ssl: false`. TLS objects accept only `ca`,
`cert`, `key` and `rejectUnauthorized`; verification is forced on. Custom identity
callbacks, `rejectUnauthorized: false` and `NODE_TLS_REJECT_UNAUTHORIZED=0` fail
before a connection is opened. No provider TLS handshake is claimed.

| Limit | Default |
| --- | --- |
| max | 4 connections |
| connectionTimeoutMillis | 5,000 ms |
| idleTimeoutMillis | 10,000 ms |
| statement_timeout | 5,000 ms |
| query_timeout | 6,000 ms |
| lock_timeout | 2,000 ms |

Overrides must be positive safe integers within signed 32-bit range. These are
synthetic defaults, not production sizing. Transactions lease one client and run
BEGIN/work/COMMIT or ROLLBACK; failed rollback or a connection error discards the
client. A COMMIT response reporting ROLLBACK rejects. Callback handles expire when
work ends. Trusted work must await its queries and install owner context with
`set_config('app.owner_id', value, true)` inside the transaction; do not issue
session-scoped context or transaction control through this interface. RLS and
trusted owner derivation remain slice 4 work. `close()` drains active work then
ends the pool; SQL timeouts do not impose a deadline on arbitrary JavaScript work.

Query, acquisition, callback and close errors expose a fresh generic Error without
driver fields, raw message or cause. Timeouts retain only a safe timeout label.
Idle connection errors are consumed without logging raw diagnostics; pg removes
those clients. The wrapper does not log credentials, SQL or payloads.

Implementation checks: **12/12 PASS**, no skips/cancellations, pinned non-root
Node 22.23.2/PostgreSQL 18.6, exit 0 and cleanup complete in
[`evidence/pool-2.2-green.txt`](evidence/pool-2.2-green.txt). Coverage includes the
original six cases, configuration/TLS guards, sanitized errors, aborted commit,
expired callback handles, default server limits, statement cancellation and client
timeout recovery. **6/6 harness regressions PASS** in
[`evidence/pool-2.2-regressions.txt`](evidence/pool-2.2-regressions.txt).

The current-tree baseline was rerun (`pool-2.2-baseline.txt`, 4 intended failures).
Incremental `pool-2.2-*-red.txt` evidence records behavioral failures before fixes
for configuration, diagnostics, aborted commit and expired handles; each following
GREEN includes relevant existing tests. The intermediate `pool-2.2-transactions.txt`
failure exposed the leased connection error event and was resolved before advancing.
Timeout checks additionally characterize the configured pg behavior through the
same approved seam. No dependency was added or installed on the host.

Routine ponytail-review of the exact 2.2 delta, callers and OpenSpec contract found
no remaining blocker for this isolated implementation. The following task 2.3
checkpoint verifies the current tree separately. Full suites, CI integration,
privileges/RLS/restore and operational G1 remain pending.

## Pool verification checkpoint (task 2.3)

Reran `node api/foundation/environment.mjs run pool` without changing runtime,
tests, dependencies or the existing harness. This is verification of the delivered
implementation, not a new behavior requiring an artificial RED. The pinned,
non-root Node 22.23.2/PostgreSQL 18.6 run passed **12/12**, with no skipped or
cancelled tests. The test process returned naturally after pool closure; the
orchestrator returned **0 in 13,985 ms**, including Compose/build and cleanup.
Full combined stdout/stderr: [`evidence/pool-2.3-run.txt`](evidence/pool-2.3-run.txt).

The existing behavioral assertions verify acquisition saturation below 2 seconds,
statement cancellation below 2 seconds, and client timeout/recovery below 1 second;
the configured test timeouts are 300, 50 and 50 ms respectively. Recovery and
same-connection/context assertions also passed. The captured output was scanned
for PostgreSQL DSNs and synthetic password/private-payload markers: no matches.
Positive scanner controls were checked without printing their contents. This
audits runner/test diagnostics, not PostgreSQL server logs or historical RED logs.

Independent read-only Docker queries found zero containers, volumes, networks or
images labeled with this run's exact project after cleanup. The audit records
source SHA-256 values, process result, bounds, coverage and limits:
[`evidence/pool-2.3-audit.txt`](evidence/pool-2.3-audit.txt).

Requirement mapping: **Failure and reuse** is covered by rollback/write and
same-client local context commit/abort tests; **Pool saturation and shutdown** by
bounded acquisition/capacity recovery, explicit close and natural process exit;
**Connection loss and safe diagnostics** by backend termination/replacement,
sanitized error inspection, TLS configuration guards and the captured-log audit.
Routine ponytail-review inspected the pool, tests, runner, cleanup and their
callers against these scenarios; no blocking finding remains for the synthetic
slice. No normal API caller imports this package. No additional harness regression
run was needed: this task changes only documentation/evidence and reruns the
existing 12 pool checks; the six harness regressions passed in 2.2.

**Slice 2 is verified for local synthetic use.** Provider TLS/pooler, production
sizing, roles/RLS, migration/restore, full legacy suites and operational G1 remain
unverified. SQL timeouts do not bound arbitrary JavaScript callbacks. This does
not complete Foundation or authorize task 3.1, commit, synchronization or archive.

## Migration process fail-first contract (task 3.1)

```bash
node api/foundation/environment.mjs run migrations
```

The following records the **historical 3.1 RED baseline**, replaced by 3.2 below.
At that checkpoint `migrate.mjs` was connectivity-only: it validated the
synthetic target, connects and closes, and emits `baseline-connected`. It creates
no roles, schema, history or locks and does not invoke node-pg-migrate. Its exit 0
only means that this baseline connected, never that migrations were applied.
The existing guarded harness validates pinned Node/PostgreSQL and cleans up even
after the expected test failure. Normal API startup does not import this command.

The approved public seam is a separate Node CLI process with these synthetic
arguments (not a production migration interface):

- `node migrate.mjs bootstrap`: provision the disposable migrator/runtime roles;
  the 3.1 baseline made no changes.
- `node migrate.mjs up <directory> <schema> [count]`: apply fixture migrations
  from `/tmp/foundation-migrations-*`, in an isolated `foundation_probe_<16 hex>`
  schema; optional positive count applies a real prefix. Target remains the fixed
  `foundation_test` database. Expected history table: `pgmigrations` in that schema.

Four node:test cases use real PostgreSQL and child processes, not mocks:

| Case | Contract retained for implementation | Observed 3.1 RED |
| --- | --- | --- |
| Empty history / prior prefix | Apply two CJS fixtures from an empty scope; separately apply one then the rest, rerun, compare exact history and actual columns | Prefix history remains empty |
| Runtime DDL | Bootstrap `foundation_runtime` with synthetic login, no superuser/BYPASSRLS; connect as runtime and require SQLSTATE 42501 for CREATE/ALTER/DROP | Restricted runtime role is absent; DDL branch not reached |
| Two processes | After the first owns an advisory lock, a second fails explicitly (exit 1), first finishes and rerun leaves one history entry and row | First exits without the lock-acquired fixture signal |
| Interruption | SIGTERM only the signaled first process; require no partial table/history or residual lock, then successful rerun | First exits without that signal; interruption branch not reached |

Fixtures are generated under tmpfs, syntax-checked, and kept outside functional
migrations. The controlled fixture uses node-pg-migrate 9.0.0's public `pgm.db`
interface to verify a granted advisory lock on its own backend before emitting
`migration-locked` over Node IPC. The parent independently checks `pg_locks` before
starting the competitor or sending SIGTERM. Release is an IPC message, never a
sleep. Only the fixture uses `FOUNDATION_MIGRATION_HOLD`; the production runner
needs no test pause hook. The future runner must wrap this work transactionally
with locking enabled; fake history or disabled locks cannot satisfy the contract.
Child lifetimes are bounded to 8 seconds (timeout is a failure); teardown stops
only this test's children before dropping its generated schemas and temp paths.

Observed on pinned non-root Node 22.23.2/PostgreSQL 18.6: **4 intended behavioral
failures, 0 passes/skips/cancellations**, exit 1, cleanup complete. Missing
role/history/signal are asserted explicitly; there is no missing module, SQL
setup error or fabricated acquired-lock signal. This is RED evidence, **not**
successful DDL denial, serialization, interruption or recovery evidence; those
branches await 3.2–3.3. Full output:
[`evidence/migrations-3.1-red.txt`](evidence/migrations-3.1-red.txt).

Focused regressions: **12/12 pool PASS** in
[`evidence/migrations-3.1-pool-regressions.txt`](evidence/migrations-3.1-pool-regressions.txt);
**7/7 harness PASS**, including rejection of external targets/invalid migration
arguments before connecting, in
[`evidence/migrations-3.1-harness-regressions.txt`](evidence/migrations-3.1-harness-regressions.txt).
Host orchestration uses Node 24; the migration and pool behavioral runs use the
pinned container runtime. No new dependency or host install was introduced.
Routine ponytail-review found no blocking issue for retaining this isolated RED
contract. Full suites, actual migration/role implementation, privilege matrix,
RLS/restore/CI and operational G1 were not tested by that RED checkpoint.

## Migration implementation (task 3.2)

`node api/foundation/environment.mjs run migrations` now exits **0**. The separate
CLI keeps the fixed synthetic target guard; it is never imported by normal API
startup. No dependency or host installation was added. Inside the disposable runner:

- `node migrate.mjs bootstrap` provisions the two login roles transactionally.
  Its own transaction lock serializes setup; repeated bootstrap is safe in this
  fresh synthetic environment. Public database/schema privileges are revoked.
- `node migrate.mjs up` uses **foundation_migrator**, never the bootstrap login,
  to apply committed `migrations/001-foundation.cjs`. There is one infrastructure
  history, `foundation.pgmigrations`. The migrator owns the schema/history;
  **foundation_runtime** has CONNECT and schema USAGE, without CREATE or history
  write privileges. Both roles lack superuser, BYPASSRLS, role/database creation
  and replication. No elevating memberships are provisioned.
- `node migrate.mjs up <directory> <schema> [count]` retains the approved fixture
  seam. Each generated scope has its own test history, never mixed with the
  infrastructure history. Paths must be canonical direct `/tmp/foundation-migrations-*`
  directories; schema names and positive safe-integer counts are validated before
  connecting. Fixtures stay in tmpfs, outside committed migrations.

The committed migration only revokes public schema access and grants runtime
USAGE. The runner creates the schema/history; no Recovery, identity or Training
table is introduced. The forward-only infrastructure migration has no down path:
recreate this disposable environment instead. Applied files must remain immutable;
no checksum enforcement is claimed. The Docker allowlist explicitly copies this
migration directory into the isolated image, outside the normal API image.

Pinned node-pg-migrate 9.0.0 uses its session advisory lock in **fail** mode,
ordering checks and a single transaction for all pending migrations. There is no
fake-history, down or no-lock CLI option. Every invocation closes its dedicated
connection in `finally`; connection/query/statement/lock limits are finite.
Diagnostics expose only safe events/counts or generic failures, suppressing the
driver's raw SQL/errors. Credentials are public synthetic constants, not a
production secret-management scheme. These log checks do not audit PostgreSQL logs.

Evidence: [`migrations-3.2-red.txt`](evidence/migrations-3.2-red.txt) repeats the four
original behavioral failures before implementation;
[`migrations-3.2-fixtures-green.txt`](evidence/migrations-3.2-fixtures-green.txt)
records their first GREEN. The infrastructure-only migration then had its own
[`RED`](evidence/migrations-3.2-infrastructure-red.txt) before implementation.
[`migrations-3.2-green.txt`](evidence/migrations-3.2-green.txt) records **5/5 PASS**,
no skips/cancellations, on non-root Node 22.23.2/PostgreSQL 18.6, exit 0 and cleanup.
The existing concurrency and SIGTERM branches now execute and pass; this is
implementation evidence, not completion of the broader 3.3 checkpoint.

Focused regressions: [pool 12/12 PASS](evidence/migrations-3.2-pool-regressions.txt)
and [harness 7/7 PASS](evidence/migrations-3.2-harness-regressions.txt). The harness
also checks traversal, unsafe counts and extra bootstrap arguments before connecting.
[Evidence audit](evidence/migrations-3.2-audit.txt) records source hashes, safe
captured diagnostics and independent resource cleanup queries. Routine
ponytail-review of CLI, callers, role setup, migration/fixture separation and
Docker packaging found no blocker for this synthetic implementation.

At the 3.2 checkpoint, dedicated SQL failure, connection termination and complete
role/privilege verification remained pending; their results follow below.

## Migration verification checkpoint (task 3.3)

Reran `node api/foundation/environment.mjs run migrations` on the current tree:
**7/7 PASS**, no skips/cancellations, Node 22.23.2/non-root and PostgreSQL 18.6,
test duration about 3.2 seconds, natural runner exit 0 and cleanup complete.
This task extends the existing process/SQL verification seam. No migrator, bootstrap,
committed migration, dependency, Docker configuration or normal API code changed;
passing characterization is used instead of manufacturing a RED for existing behavior.

| Requirement scenario | Observed proof |
| --- | --- |
| Empty database / previous test schema | Infrastructure-only history and ownership; empty fixture scope and real prefix converge, reruns do not replay |
| Runtime privilege separation | Both login roles have restricted attributes and no memberships; runtime owns no database/schema/relation. With fixture USAGE and DML grants, INSERT/SELECT succeed; 14 DDL/TRUNCATE/elevation/history-write attempts fail with SQLSTATE 42501 |
| Concurrent runners | Parent verifies the signaled backend is this disposable migrator and holds an advisory lock; competitor exits 1, first completes once; rerun leaves one entry and row |
| Transactional SQL failure | Real unique_violation (23505) after pending ALTER/CREATE/write rolls back all pending work; applied prefix/data survive, session/lock disappear. Remove only the conflicting input row, rerun the same files, then rerun again: exact history/data, no fake history |
| Process interruption | SIGTERM only the signaled child; no partial table/history, session or advisory lock remains; rerun succeeds |
| Connection termination | Terminate only the verified synthetic backend, waiting for server termination; no partial table/history or lock, child exits 1 without timeout kill, rerun succeeds |

The connection test releases the fixture's JavaScript IPC gate after terminating
its database session. It does not claim that SQL timeouts cancel arbitrary JavaScript.
Lock readiness/release use IPC and PostgreSQL observations, without arbitrary sleeps.
All child stdout/stderr is checked for synthetic credentials/DSNs; expected failures
also check generic diagnostics. Teardown stops this test's children and drops its
own fixture schema/temp directory even if a diagnostic assertion rejects.

Progressive evidence: [privilege matrix, 5/5](evidence/migrations-3.3-privileges.txt),
[SQL failure added, 6/6](evidence/migrations-3.3-sql-failure.txt),
[final checkpoint, 7/7](evidence/migrations-3.3-run.txt),
[source/log/cleanup audit](evidence/migrations-3.3-audit.txt).
The audit independently checks that this run's containers (including stopped ones),
volumes, networks and runner image are gone. Routine ponytail-review found no
blocking finding for the synthetic two-process workload and mapped every migration
scenario to these checks. No other task was advanced.

The 3.2 pool/harness regressions remain historical evidence, not rerun results for
3.3: their implementation/configuration is unchanged. Full suites/build/locales,
RLS, restore and CI remain in later tasks. PostgreSQL server logs, provider TLS,
production recovery and operational G1 remain unverified. Slice 3 is verified only
for the isolated synthetic environment; Foundation is not complete.

## Isolation fail-first contract (task 4.1)

```bash
node api/foundation/environment.mjs run isolation
```

The following records the **historical 4.1 RED baseline**, replaced by 4.2 below.
At that checkpoint the group exited 1; its fixture baseline created only
a generated `foundation_isolation_<16 hex>` schema, a small `owner_probe` table,
two synthetic owners and runtime CRUD grants. **No RLS policy is implemented**:
that belongs to 4.2. `isolation-fixture.mjs` keeps this setup outside committed
migrations and validates schema names before interpolating SQL. The existing
Docker allowlist copies both new `.mjs` files; no dependency/topology change.

The approved seam is real fixture SQL through `createDatabase().transaction()`.
A/B are the two synthetic **data owners**, not separate application database
logins: both requests use the actual restricted `foundation_runtime` login and
`app.owner_id` transaction-local context set by trusted test work. This follows
the shared runtime/pool design and makes same-connection reuse observable.
`foundation_migrator` owns the fixture; bootstrap only provisions the existing
roles. Every test verifies the runtime login/target, non-owner table identity and
absence of superuser/BYPASSRLS before testing access. No mocks or user data.

| Test cases | Expected future behavior | Observed RED baseline |
| --- | --- | --- |
| A/B/missing-context reads (3) | Unfiltered SELECT returns only the current owner's rows, or none without context | Both owners are visible |
| A/B/missing-context UPDATE/DELETE (3) | Unauthorized target affects zero rows | Each operation affects one foreign row |
| Foreign-owner/missing-context INSERT (2) | Reject insertion claiming owner B | Insert succeeds; expected rejection is absent |
| Reuse after commit/rollback/SQL error (3) | Same PID serves A, B, then no context; no A access leaks, context-free read returns none | Context/PID/persistence checks pass first, then visibility assertion exposes foreign rows |

The reuse cases exercise a real authorized A write, assert commit persistence or
rollback absence, and verify local context clears before B and context-free work.
The pool is capped at **1**, with a finite idle timeout and explicit closure.
Assertions about visibility stay outside the transaction callback so pool error
sanitization cannot disguise an assertion failure as the intended RED. Tests drop
only their own schema after closing the runtime pool; outer cleanup still runs
on the expected nonzero exit.

Evidence: [first A-read RED](evidence/isolation-4.1-first-red.txt),
[11 intended behavioral failures](evidence/isolation-4.1-red.txt),
[harness regressions 7/7 PASS](evidence/isolation-4.1-harness-regressions.txt),
[source/log/cleanup audit](evidence/isolation-4.1-audit.txt).
Observed runtime: pinned non-root Node 22.23.2/PostgreSQL 18.6; **0 passes, 11
failures, 0 skips/cancellations**, exit 1, cleanup complete. No missing module,
syntax, role, table or connection error is counted as a RED.

Routine ponytail-review mapped both owner-isolation scenarios to these tests and
found no blocker for retaining the isolated RED baseline. This does **not** prove
RLS effective or finish the full CRUD/privilege matrix. Policies USING/WITH CHECK,
the restricted Training-only role and TRUNCATE/elevation checks remain in 4.2–4.3.
Pool, bootstrap, committed migrations and normal API are unchanged; their earlier
checks are historical, not rerun here. Full suites, restore, CI and operational G1
remained pending at the 4.1 checkpoint. Current implementation follows below.

## Synthetic RLS implementation (task 4.2)

`node api/foundation/environment.mjs run isolation` now exits **0**, with **13/13
PASS**, no skips/cancellations, pinned non-root Node 22.23.2/PostgreSQL 18.6 and
cleanup complete. The previous eleven tests are unchanged apart from including
the new synthetic credential in the bootstrap diagnostic scanner.

`isolation-fixture.mjs` enables and forces RLS on the generated table after seeding.
A policy scoped to `foundation_runtime` uses the same owner comparison in both
`USING` and `WITH CHECK`: `owner_id = nullif(current_setting('app.owner_id', true), '')`.
Missing/empty context cannot match a row. Trusted transaction work still installs
context locally through the existing pool; the fixtures are not application
authentication or production Recovery policies. Runtime receives schema USAGE
and table SELECT/INSERT/UPDATE/DELETE only, with no TRUNCATE, ownership or role
membership. No new committed domain migration or normal API integration.

The disposable bootstrap additionally provisions **foundation_training** with a
public synthetic password, CONNECT only, no CREATE/TEMP, no superuser/BYPASSRLS,
role/database creation, replication, inheritance or memberships. It receives no
fixture schema/table grants. This represents a restricted consumer, not an
implementation of Training persistence. Its real login can execute SELECT 42;
fixture CRUD fails with SQLSTATE **42501** even with a known owner context, and
SET ROLE to runtime/migrator/bootstrap is denied.

A focused runtime check first updates its own row successfully, then rejects
owner reassignment, TRUNCATE, SET LOCAL ROLE to migrator/bootstrap, enabling
BYPASSRLS and granting migrator membership. Both owners' data remain intact.
These existing privilege boundaries use passing characterization; no artificial
RED is claimed for permissions already denied in 3.2–3.3.

Evidence: [original 11 RED repeated](evidence/isolation-4.2-red.txt),
[RLS GREEN, 11/11](evidence/isolation-4.2-rls-green.txt),
[Training provisioning RED](evidence/isolation-4.2-training-red.txt),
[Training GREEN, 12/12](evidence/isolation-4.2-training-green.txt),
[final 13/13](evidence/isolation-4.2-green.txt),
[migration regressions 7/7 PASS](evidence/isolation-4.2-migration-regressions.txt),
[source/log/cleanup audit](evidence/isolation-4.2-audit.txt).
The Training RED is an absent-role behavioral assertion before login; it does not
pretend a connection failure proves isolation. Only after provisioning do its
actual login/ACL branches pass. The migration scanner now also covers the new
synthetic password marker. No dependency or host installation was added.

Routine ponytail-review found no blocker for this isolated implementation. At the
4.2 checkpoint the dedicated CRUD/owner/context/privilege and cleanup verification
remained pending; its results follow below. Pool/harness evidence from earlier tasks
was not rerun or presented as fresh; the changed bootstrap's migration regressions
were rerun. Full suites, restore, CI and operational G1 remain pending.

## Owner isolation verification checkpoint (task 4.3)

`node api/foundation/environment.mjs run isolation` passed **20/20**, with no
skips/cancellations, Node 22.23.2/non-root and PostgreSQL 18.6, in about 1.4 seconds
of test execution. The test process exited naturally with status 0; cleanup completed.
Only verification and documentation changed. The pool, RLS fixture, bootstrap,
dependencies and normal application remain as delivered in 4.2. These tests
characterize existing behavior; no artificial RED or new runtime feature is claimed.

| Scenario | Current proof |
| --- | --- |
| Authorized CRUD | A and B each INSERT, read without an application owner filter, UPDATE, reread committed values, DELETE and verify the remaining seed row; same runtime PID and cleared local context |
| Cross-owner / no context | A/B see only their rows; foreign UPDATE/DELETE affect zero rows. Missing and explicitly empty context expose none, modify none and cannot INSERT |
| Owner forgery | A→B and B→A INSERT/reassignment are rejected; existing ownership/data survive |
| Connection reuse | Pool max 1; A commit, explicit rollback and SQL error preserve expected data semantics; the same PID subsequently serves B and no context without A access |
| Runtime privileges | Real runtime login, migrator-owned schema/table, no superuser/BYPASSRLS/create-role/create-db/replication/inheritance/memberships; CONNECT and schema USAGE, table CRUD only among tested privileges; CREATE/TEMP, schema CREATE, TRUNCATE/TRIGGER/REFERENCES absent; DDL/elevation attempts rejected |
| Training-only | Real login and SELECT 42 succeed, but known-owner fixture CRUD and role elevation fail with 42501; no fixture grants or elevating memberships |
| Fixture retirement | All 20 teardowns close the pool, DROP only their generated schema, query its absence and verify the runtime PID has disappeared before closing the migrator connection |

Each teardown emits `Fixture cleanup PASS: schema absent; runtime connection closed`
only after its SQL assertions. The final audit also independently checks no owned
Docker container (including stopped), volume, network or runner image remains.
The effective context is set only by trusted test work inside transactions; this
is not proof of HTTP authentication or production Recovery policy correctness.

Evidence: [complete run](evidence/isolation-4.3-run.txt) and
[source/log/cleanup audit](evidence/isolation-4.3-audit.txt). Routine ponytail-review
mapped all three owner-isolation scenarios to this matrix and found no blocking
finding for the sequential synthetic workload. Source hashes confirm the 4.2
implementation is unchanged; its migration regression is historical, not rerun here.

**Slice 4 is verified for isolated synthetic use.** No other task was advanced.
Full legacy suites/build/locales, encrypted recovery, CI and operational G1 remain
pending. No real accounts, Training/Recovery schema, provider TLS, off-host backup,
production RPO/RTO, commit, synchronization or archive is included.

## Recovery fail-first contract (task 5.1)

```bash
node api/foundation/environment.mjs run recovery
```

The following records the **historical 5.1 RED baseline**, replaced by 5.2 below.
At that checkpoint the group intentionally exited 1. `recovery.mjs` was a loadable connectivity-only
baseline: it validates the fixed synthetic host/database/environment and argument
shapes, connects to `foundation_test`, emits `recovery-baseline-connected` and
closes. Exit 0 from that baseline never means a backup, transfer or restore happened.
It reads/writes no artifact, runs no dump/restore and modifies no database. In
particular, its permissive destination-name syntax is not a restore safety guard;
the generated-target allowlist must be implemented before any restore in 5.2.

The agreed CLI seam is concretized as follows, **inside the isolated runner only**:

- `node recovery.mjs backup <bundle-dir> <key-file> <40-hex-application-revision>`
- `node recovery.mjs copy <bundle-dir> <transfer-dir>`
- `node recovery.mjs restore <transfer-dir> <key-file> <foundation_restore_16hex>`

Paths belong to one test's `/tmp/foundation-recovery-*` directory: `backup/`,
`transfer/`, and separate `keys/key.bin` or `keys/wrong.bin`. The key is 32 random
bytes, mode 0600, never an argument value or part of the transferred bundle.
The backup/transfer bundle contains exactly `backup.enc` and `manifest.json`.
The AES-256-GCM binary contract is **12-byte nonce, 16-byte tag, ciphertext**;
the raw UTF-8 manifest bytes are authenticated additional data. The manifest
records formatVersion 1, applicationRevision, schemaVersion (history names),
databaseVersion, pg_dump/pg_restore versions, sourceDatabase, owners, role names,
cipher and dumpSha256. Tests declare a synthetic revision explicitly; it is not
presented as the checkout's Git HEAD. Real callers must supply their actual revision.

Tests reuse the real bootstrap/migration history and owner RLS fixture. Each
creates only its own `foundation_restore_<16 hex>` database on the disposable
cluster; it is distinct from the source, with cluster-shared roles already
provisioned. Teardown closes clients, verifies generated target name/ownership,
drops only that target and fixture schema, queries their absence, and removes
its own tmpfs files. No actual instance or external destination is reachable.

| Case | Retained contract | Observed RED |
| --- | --- | --- |
| Backup/copy/restore | Authenticated custom dump (PGDMP), manifest/hash/modes, transfer without key, semantic A/B data/history/ownership/policies/grants/database privileges, real runtime RLS after restore and unchanged source | Encrypted artifact absent |
| Copy | Independent control bundle is copied byte-for-byte, exactly two files and no key | Transferred artifact absent |
| Wrong key | Reject authentication with `Recovery verification failed`; empty target and source unchanged | Baseline exits 0 instead of rejecting |
| Corruption | Reject modified ciphertext before applying content; target and source unchanged | Baseline exits 0 instead of rejecting |
| Unsafe destination | Refuse `foundation_test` with `Refusing non-test restore target` before modification | Baseline exits 0 instead of refusing |

Negative/copy cases use an independently sealed AES-GCM **authentication control**
containing a synthetic payload, not valid pg_dump output. Its decryption is checked
before tampering. This avoids missing-file or missing-backup setup failures; it
does not prove real backup/restore. The main test retains those future branches,
but currently stops at the missing encrypted artifact. No successful cryptographic
rejection, actual transfer, dump, restore, role reprovisioning or restore duration
is claimed. PostgreSQL 18 client tools are in the pinned PostgreSQL image; making
them available to the recovery runner is still 5.2 work, not a RED prerequisite.

Evidence: [first behavioral RED](evidence/recovery-5.1-first-red.txt),
[five intended RED failures](evidence/recovery-5.1-red.txt),
[harness 8/8 PASS](evidence/recovery-5.1-harness-regressions.txt),
[source/log/cleanup audit](evidence/recovery-5.1-audit.txt). Runs use non-root
Node 22.23.2/PostgreSQL 18.6, no skips/cancellations, expected exit 1 and cleanup.
The harness additionally rejects external hosts/unsafe artifact paths before driver
loading. Routine ponytail-review found no blocker for the RED-only scope. No
dependencies were added; normal API, pool, roles and committed migrations are
unchanged. 5.2–5.3/full suites/CI and operational G1 remain pending. A directory
transfer on this host is not off-host backup, PITR or production RPO/RTO proof.

## Synthetic recovery implementation (task 5.2)

Run `node api/foundation/environment.mjs run recovery` from the repository root.
The same approved CLI and binary bundle contract above are now implemented.
The runner combines the already pinned PostgreSQL 18.6 image (including its client
tools and libraries) with the pinned Node 22.23.2 binary/npm and locked dependency
stage. It runs as UID 1000 with read-only root, private tmpfs and internal network.
No new package, host installation, normal API image or dependency lock changes.

Backup uses a read-only repeatable-read transaction, exports its PostgreSQL
snapshot and supplies it to `pg_dump --format=custom --snapshot=...`. History and
synthetic owner metadata come from that same snapshot. Bootstrap captures both
owners despite RLS; it is never the application identity. The manifest records
the caller-supplied revision (a declared synthetic value in tests), history,
server/client versions, owners, roles, cipher and SHA-256 of the custom archive.
AES-256-GCM authenticates the raw manifest as well as the archive. Only ciphertext
and manifest are written; the random 32-byte key stays in a separate keys directory.

Paths must be canonical, owned by the runner and private (no group/world bits);
files must be regular and have one link. Empty destinations and exclusive writes
prevent overwrite. Copy transfers exactly the encrypted artifact and manifest,
never the key, to a different private directory. No filesystem or network URL is
accepted. CLI/driver and libpq endpoints are fixed to the synthetic service;
libpq gets a fresh allowlisted environment, finite timeouts, no service/DSN/options
overrides and no password prompt. Subprocess stderr and SQL are never printed.

Restore verifies GCM, authenticated metadata/hash and `pg_restore --list` before
connecting to the destination. It accepts only `foundation_restore_<16 hex>`,
owned by bootstrap, with untouched initial database ACLs and no user schemas,
relations, routines or types. A session
advisory lock serializes cooperating restores. `pg_restore --single-transaction
--exit-on-error` preserves owners, grants and RLS; neither `--create` nor `--clean`
is used. Database ACLs are set explicitly for the chosen target: public revoked,
migrator CONNECT/CREATE, runtime and Training CONNECT only. They are set after the
archive restore; an ACL failure returns failure and requires discarding this
synthetic target. No failed target is promoted or used by the app.

The existing bootstrap explicitly provisions migrator/runtime/Training; recovery
verifies all three restricted login attributes and absence of memberships before
dump/restore. Roles are global and shared by the two databases in this test cluster;
the archive does **not** back up global roles or passwords. Provisioning a clean
second cluster is not demonstrated. Dumps are buffered in memory with 32 MiB tool
output and 20-second subprocess limits: this is a small synthetic rehearsal, not
production backup tooling. Partial file writes are not presented as completed
bundles and must be discarded with the owned test directory.

Observed: **12/12 PASS**, no skips/cancellations, Node 22.23.2/non-root,
PostgreSQL/client tools 18.6 and cleanup complete. The original five RED cases now
pass, including real restored A/B data, history, owner, policy expressions, grants,
runtime A/B/missing-context reads, denied TRUNCATE and unchanged source. Additional
checks reject altered manifest, a target containing only a routine (observed
behavioral RED then GREEN), public/symlinked keys, transfer overwrite, authenticated
invalid archive, a target owned by another role and preexisting excess database
grants (observed behavioral RED then GREEN). Original 5.1 evidence remains
historical; no claim about its unexecuted branches is rewritten.

Evidence: [baseline 5 RED repeated](evidence/recovery-5.2-baseline-red.txt),
[initial 5 GREEN](evidence/recovery-5.2-initial-green.txt),
[nonempty target RED](evidence/recovery-5.2-target-red.txt),
[boundary checks 11 GREEN](evidence/recovery-5.2-boundary-green.txt),
[excess destination privileges RED](evidence/recovery-5.2-acl-red.txt),
[final 12 GREEN](evidence/recovery-5.2-green.txt),
[pool 12/12](evidence/recovery-5.2-pool-regressions.txt),
[migrations 7/7](evidence/recovery-5.2-migrations-regressions.txt),
[isolation 20/20](evidence/recovery-5.2-isolation-regressions.txt),
[harness 8/8](evidence/recovery-5.2-harness-regressions.txt),
[source/log/cleanup audit and review](evidence/recovery-5.2-audit.txt).
Those focused regressions were repeated because every group uses the changed
runner image. No normal API/frontend/MCP suite, build or CI integration was run.
At the 5.2 checkpoint, **5.3 remained pending** for dedicated complete/timed
verification; its current results follow below. Directory transfer on the
same host/restore in the same cluster proves no off-host backup, PITR, production
RPO/RTO, provider compatibility or operational G1. No commit/sync/archive.

Implementation references: [PostgreSQL 18 pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)
(consistent snapshot/custom archive/global-role limits) and
[PostgreSQL 18 pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)
(transactional restore and the source-name behavior of `--create`, deliberately omitted).

## Recovery verification checkpoint (task 5.3)

Reran `node api/foundation/environment.mjs run recovery` on pinned non-root
Node 22.23.2/PostgreSQL 18.6/client tools 18.6: **12/12 PASS**, no skips or
cancellations, natural exit 0 and cleanup complete. Only verification and docs
changed; the recovery CLI, Docker image definition, dependency lock, bootstrap,
pool, committed migration and RLS fixture are unchanged. This is positive
characterization of existing behavior, not a new feature requiring artificial RED.

The main test now compares schema/table ownership, RLS enabled/forced flags,
policy roles/permissiveness/command/USING/WITH CHECK, history, A/B data, grants
and database privileges. Literal source expectations prevent two equally wrong
snapshots from passing. After restore, real runtime A/B logins through the shared
runtime identity read only their own rows, perform own UPDATE/INSERT/DELETE,
cannot modify/delete the other owner, and cannot insert a foreign owner or write
without context. TRUNCATE fails. A real Training login still cannot read the
fixture even with known owner context. Verification writes roll back; both the
restored target and untouched source then match the original semantic snapshot.

One sample, **two owner rows**, custom archive **7,125 bytes**, ciphertext bundle
file **7,153 bytes** (manifest separate):

| Measurement | Observed ms |
| --- | ---: |
| Backup CLI | 104.069 |
| Copy CLI | 23.489 |
| Restore CLI | 74.436 |
| Semantic/runtime verification | 20.532 |
| Restore through verification completion | 94.969 |
| Backup through final verification, including intervening artifact checks | 227.922 |

Monotonic `performance.now()` wraps real CLI processes, including process startup.
Restore includes authentication/archive validation, pg_restore and database ACLs.
Fixture preparation, Docker build/startup and cleanup are excluded. These numbers
describe a tiny same-host tmpfs transfer and two databases sharing one disposable
cluster, not production RPO/RTO or a performance benchmark. Roles were provisioned
by the existing explicit bootstrap and are shared, not archived/reprovisioned in
a second cluster. No real-instance data, external provider or off-host durability
is exercised.

Each of the **12** teardowns confirms its generated database/schema and tmpfs
artifacts/key are absent after closing clients. Independent Docker queries confirm
zero owned containers (including stopped), volume, network and runner image for
both 5.3 runs. Wrong key, ciphertext/manifest corruption, invalid archive and unsafe
destination tests still pass without changing source or rejected target state.

Evidence: [complete timed run](evidence/recovery-5.3-run.txt),
[source/log/cleanup audit and review](evidence/recovery-5.3-audit.txt),
[initial verification assertion failure](evidence/recovery-5.3-verification-failure.txt).
The first run failed in fixture verification because the driver returned SQL
`name[]` as text; selecting role names as `text` produces a parsed `text[]`.
That failed setup is preserved and receives no recovery/timing credit; it is not
a behavioral RED. The corrected run passed all checks. No blocking review finding
remains for this synthetic checkpoint.

**Slice 5 is verified for isolated synthetic use.** Pool/migration/RLS/harness
regressions from 5.2 remain historical (12/7/20/8 PASS), not rerun because runtime
and configuration did not change. Tasks 6.1–6.3, full legacy suites/build/locales,
CI and operational G1 remain pending. Existing buffering and post-archive database
ACL failure/discard limits from 5.2 still apply. No commit/sync/archive/deploy.

## Pins and evidence

[`versions.json`](versions.json) is the image/tool version source for subsequent
Foundation slices. Image references contain an exact release tag **and** immutable
multi-platform index digest; validation so far covers **linux/amd64 only**.

| Tool | Selected stable release | Observed check |
| --- | --- | --- |
| Node | 22.23.2, Debian bookworm-slim | `node --version`: v22.23.2 |
| npm | 10.9.8 (bundled in pinned Node image) | `npm --version`: 10.9.8 |
| pg | 8.23.1, MIT | installed version and ESM `Pool` export |
| node-pg-migrate | 9.0.0, MIT | installed version and ESM `runner` export |
| PostgreSQL | 18.6, Debian trixie | `postgres --version`: 18.6 |
| PostgreSQL client tools | 18.6, same image | `pg_dump`, `pg_restore`, `psql` version checks |

Registry metadata and image manifests were checked on 2026-10-21. Reproduction
host: Windows/Git Bash, Node 24.14.0 (orchestration only), Docker Engine 29.4.0
Linux, Compose v5.1.1 (task 1.1 did not start services). The exact pinned Node image,
not the host Node, performed dependency resolution and verification.

[`package-lock.json`](package-lock.json) v3 fixes all **36 installed packages**
with HTTPS registry URLs and SHA-512 integrity metadata. It also contains the full
transitive license/engine inventory. [`evidence/toolchain.txt`](evidence/toolchain.txt)
records a fresh `npm ci`, the inventory checked against installed package metadata,
ESM exports, dependency tree, lock SHA-256 and `npm audit` result (zero reported
vulnerabilities at execution time; not a permanent security guarantee).
[`evidence/checker-negative.txt`](evidence/checker-negative.txt) records a separate
scratch-copy check: after `npm ci`, changing only the lock's
`packages['node_modules/pg'].version` to `8.23.0` makes `npm run check:toolchain`
fail with `AssertionError: node_modules/pg`, as intended. The source lock is never
modified by this negative check.

Declared licenses are MIT, ISC and BlueOak-1.0.0. These are permissive licenses;
retain their notices on redistribution. This is an inventory of package metadata,
not a legal review or an inventory of all OS/npm-bundled image packages. No package
has missing license metadata. Some packages do not declare engines; the inventory
states that explicitly rather than inventing a supported range. `npm ci
--engine-strict` accepts all declared ranges on this exact Node/npm pair, including
transitive yargs' `^22.12.0` branch.

`npm ls --all` succeeds. Its two absent **optional peers** are intentional:
`@types/pg` (not needed by this JavaScript ESM package) and `pg-native` (the selected
client is pure JavaScript). No native addon, lifecycle install script, or optional
peer is required by this proof. `node-pg-migrate --version` prints `unknown` for
this published candidate; use installed package/lock metadata, not that output,
to identify 9.0.0. Its database behavior is not established by importing `runner`.

## Reproduce dependency verification

From the repository root in Bash (Linux or Git Bash with Docker Desktop):

```bash
source_dir="$(cd api/foundation && (pwd -W 2>/dev/null || pwd))"
node_image="$(node -p 'require("./api/foundation/versions.json").nodeImage')"
MSYS_NO_PATHCONV=1 docker run --rm --user 1000:1000 \
  --mount "type=bind,source=$source_dir,target=/source,readonly" \
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

Network access is needed only for registry downloads/audit, with standard CA/TLS
validation (`strict-ssl=true`). Do not disable certificate validation to work
around a host CA problem. The checker intentionally requires invocation via npm
so it can verify the npm version as well. Installation and npm cache live only in
the disposable container; the sole source mount is this directory, read-only.
No host `node_modules`, `.env`, `data/`, coach credentials or media are read.
The original lock was generated with the same image and `npm install
--package-lock-only --ignore-scripts --engine-strict --no-audit --no-fund` before
`npm ci`. Reproduction must use the existing lock, not resolve it again.

The initial scratch attempt used a Docker-created root-owned workdir and failed
before copying/installing anything as UID 1000. The successful command above uses
`mktemp -d` as that user instead. This is an environment correction, not a
behavioral TDD RED. This slice adds configuration and a consistency checker, not
application runtime behavior; its proof is successful resolution/consistency and
loadable exports rather than a manufactured runtime failure.

## Reproduce image/tool version checks (no database startup)

```bash
postgres_image="$(node -p 'require("./api/foundation/versions.json").postgresImage')"
docker buildx imagetools inspect "$node_image"
docker buildx imagetools inspect "$postgres_image"
docker pull "$postgres_image"
docker run --rm --network none --read-only --user postgres --entrypoint sh \
  "$postgres_image" -ec '
    postgres --version
    pg_dump --version
    pg_restore --version
    psql --version
  '
```

[`evidence/images.txt`](evidence/images.txt) records the pulled index digests,
local platform and binary versions. Overriding the PostgreSQL entrypoint prevents
initialization; no server or public port is started. `--rm` removes containers
and any anonymous image-declared volume created for these runs. Pulled images
remain cached; do not prune unrelated Docker resources.

## Review and limits

Requirement coverage for this task: stable, exact candidate/lock/engine evidence
supports **Controlled migration history and privilege separation**; image pins
prepare **Isolated synthetic environment**. Neither requirement is fully delivered
until their remaining scenarios are verified. Task 1.2 adds guarded synthetic
startup/connectivity and bounded cleanup evidence. Task 1.3 adds no-PostgreSQL
legacy API compatibility and repeats config/target checks. No migration,
locking, TLS handshake, privilege, RLS or backup/restore proof is claimed by tasks
1.1–1.3. Pool implementation evidence and its remaining checkpoint are above.

Routine `ponytail-review` self-review inspected this directory, including every new
file, Compose definition, CLI/runner/tests and task Notes against the
proposal/design/spec/tasks. Expected usage is disposable local/CI runs, not
application traffic. Review identified per-project runner image tags accumulating;
cleanup now validates and untags only its own image, with the integrated
regression checking that it is gone. No unresolved blocking findings remain.
Task 1.3 review reuses those public seams and existing tests; the exact delta is
this documentation, task Notes and new sanitized evidence, with no runtime change
or new dependencies. The Windows-bind timeout was resolved in the verification
invocation by staging into tmpfs; the original test selection then passed. No
blocking findings remain for the shared prerequisite checkpoint. Normal API
manifest, lockfile, Dockerfile, tests and startup remain unchanged. No full
API/frontend/MCP suite, frontend build, locale check, browser test or API image
build was run for 1.3; those broader checks remain in slice 6.
OpenSpec strict validation, evidence consistency and trailing-whitespace checks
passed. This is prerequisite readiness only, not integrated-change readiness.
