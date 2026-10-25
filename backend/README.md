# Python Foundation — isolated synthetic tooling

This package exercises the Python platform with disposable synthetic data.
The normal application still runs Node/JSON; this is not a production API,
a migration of user data, or an operational backup service.

## Start here

Run all commands from the repository root with Node 22+ and trusted Docker
Engine Linux / Compose. Python, uv and PostgreSQL are supplied by pinned images;
no host Python installation is needed. Builds may require network access.

```sh
node scripts/python-foundation.mjs config
node scripts/python-foundation.mjs run environment
```

The harness ignores instance dotenv files and inherited Compose overrides. It
uses its own project, internal network, volume and private tmpfs, with UID/GID
1000, a read-only root, dropped capabilities and no published ports or host binds.
Never substitute the instance Compose file, credentials or data directory.

## Verification groups

```sh
node scripts/python-foundation.mjs run contracts
node scripts/python-foundation.mjs run pool
node scripts/python-foundation.mjs run migrations
node scripts/python-foundation.mjs run isolation
node scripts/python-foundation.mjs run recovery
```

| Group | What it checks |
| --- | --- |
| `environment` | Pinned toolchain, disposable DB, factory health/lifespan and Uvicorn process lifecycle; ordinary Node health without PostgreSQL. |
| `contracts` | Existing Node/client/MCP behavior with independent synthetic fixtures. Does not start Python or PostgreSQL. |
| `pool` | Bounded Database transactions, cancellation, connection reuse, unknown commit outcomes and safe diagnostics. |
| `migrations` | Controlled Alembic CLI, serialized history, interruptions and restricted roles. |
| `isolation` | Real runtime/Training permissions, owner RLS and reuse after transaction outcomes. |
| `recovery` | Synthetic encrypted backup/copy/restore, restricted-owner reads, history/ownership/grants/RLS equivalence, timings and unsafe bundle/path/target rejection. Not an operational recovery command. |
| `all` | Not implemented; fails explicitly. |

Required prerequisites, test failures and cleanup failures return nonzero.
The runner bounds pytest to 60 seconds and scans captured diagnostics before
replaying them. A passing group proves only its synthetic scope, not platform
parity, HTTP authorization or operational acceptance.

The [OpenSpec tasks](../openspec/changes/add-python-platform-foundation/tasks.md)
own delivery state and concise execution evidence. Tests are executable proof;
Git and PRs preserve implementation history. Keep session records out of this guide.

## Synthetic recovery contract

Only the disposable cluster is accepted. `run recovery` creates and removes all
fixtures; do not supply instance databases or artifacts. Inside that container,
the process interface is:

```text
python -m opengym_platform.recovery backup <bundle> <key> <revision>
python -m opengym_platform.recovery copy <bundle> <destination-file>
python -m opengym_platform.recovery restore <bundle> <key> <target-db>
```

The separate key is 32 random bytes, mode 0600. Artifacts must be regular,
single-link private files below owned mode-0700 directories on `/tmp` tmpfs;
traversal, symlinks, public permissions and overwrites are rejected. The single
bundle contains a four-byte big-endian manifest length, JSON manifest, 12-byte
nonce and AES-256-GCM ciphertext/tag. The manifest is authenticated as AAD and
records application revision, Alembic history, DB/tool versions, required roles,
SHA-256 and synthetic scope. Copy transfers only the bundle, never the key.
Plaintext dump/spools remain only in process memory or private unnamed tmpfs files.

Backup exports one repeatable-read snapshot for manifest history and custom-format
`pg_dump`. The pinned PostgreSQL 18.6 image supplies tools and their matching
loader/library closure under `/opt/pg-tools`, separate from the Bookworm Python
runtime; no apt packages or lock changes are needed. Artifacts/tool output are
capped at 32 MiB, subprocesses at 30 s, SQL/connect/close at finite limits. This
small-fixture implementation buffers dumps in memory; it is not a streaming service.

Restore authenticates before any DB connection. It accepts only
`python_foundation_restore_<16 hex>`, owned by the synthetic bootstrap, marked
`opengym-python-foundation-recovery-v1`, with pristine DB ACLs and no user objects.
Tests alone provision that destination and the explicit restricted roles. Restore
uses a session lock and `pg_restore --single-transaction --exit-on-error`, preserves
schema ownership/grants/RLS, checks restored history and sets explicit DB grants.
A touched destination failing restore/verification returns
`FOUNDATION_RECOVERY_TARGET_UNUSABLE`, is marked unusable and denies new connections;
remove it through fixture cleanup, never retry it. Other failures return the safe
`FOUNDATION_RECOVERY_REJECTED` code without raw diagnostics.

This is same-cluster, database-only synthetic recovery: no off-host durability,
cluster loss, media/auth completeness, PITR, RPO/RTO, scheduling or production
Recovery acceptance. The positive case checks catalog metadata independently as
runtime in the restored DB, compares it to the source and checks source metadata
again afterwards. Runtime and Training logins also exercise actual denials.

`FOUNDATION_RECOVERY_TIMING` reports each CLI process's elapsed seconds, including
its connection/tool/encryption/verification work but excluding external fixture
setup and teardown. `case_seconds` includes migration, seeding and assertions
inside the positive test, not pytest fixture setup/teardown. Pytest duration covers
the full group and fixtures; host command wall time also includes build/startup
and Docker cleanup. All are observations, not performance guarantees; current
execution evidence is tracked in OpenSpec tasks.

## Cleanup

Each run prints an exact project `opengym-python-foundation-test-<16 hex>`.
Normal completion and failures clean up owned resources. After a hard kill,
use the printed project as the sole argument:

```sh
node scripts/python-foundation.mjs cleanup <exact-printed-project>
```

Cleanup validates the complete resource set's labels, services, names and tags
before removal. It refuses foreign or shared resources. Never use a broad prune,
remove-orphans or instance teardown to clean a test. Base images and build caches
may remain.

## Code and contracts

- `src/opengym_platform/core/`: per-instance asyncpg pool and transaction handles.
  Protected SQL uses `Database.transaction(owner_id)` with transaction-local
  context. Expired handles reject use; unresolved commit outcomes are explicit
  and must not be retried automatically.
- `src/opengym_platform/health/` and `app.py`: internal live/ready probes and
  factory/lifespan composition. Startup does not run migrations or fall back to JSON.
- `src/opengym_platform/migrate.py` and `migrations/`: separate migration process
  and infrastructure history. Bootstrap is restricted to this disposable cluster.
- `tests/`: synthetic fixtures and behavior checks; fixture RLS is outside the
  migration history and is not a production Recovery policy.
- [CONTRACTS.md](CONTRACTS.md): current Node compatibility reference and port handoff.
- [Platform architecture](../docs/open-gym-evolution.architecture.md): target
  mechanisms and acceptance; the normal stack remains authoritative until cutover.

## Toolchain and checks

[versions.json](versions.json) owns image/tool versions and immutable references;
[pyproject.toml](pyproject.toml) and [uv.lock](uv.lock) own Python dependencies.
[dependency-licenses.json](dependency-licenses.json) records their license inventory.
Builds verify the lock rather than resolving new dependencies. Evidence currently
covers Linux/amd64; other platforms and providers need their own verification.

```sh
node --test scripts/python-foundation.test.mjs backend/contracts-compare.test.mjs api/foundation/environment.test.mjs api/foundation/configuration.test.mjs
```

These host regressions exercise the harness, ownership guards, failure propagation
and cleanup. Full API/frontend/MCP suites and their build/locale checks are listed
in [CONTRIBUTING.md](../CONTRIBUTING.md) and existing CI. Synthetic Foundation results
do not replace those checks or the later recovery/CI/operational gates.
