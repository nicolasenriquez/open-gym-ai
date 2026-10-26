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
node scripts/python-foundation.mjs run all
```

The harness ignores instance dotenv files and inherited Compose overrides. It
uses its own project, internal network, volume and private tmpfs, with UID/GID
1000, a read-only root, dropped capabilities and no published ports or host binds.
Never substitute the instance Compose file, credentials or data directory.

## Verification groups

### Incremental platform verification

The platform port reuses Foundation's Docker execution and ownership checks through
`scripts/synthetic-harness.mjs`, with a separate `opengym-platform-test-<hex16>`
namespace and `org.opengym.platform=synthetic` labels. From the repository root:

```sh
node scripts/platform-baseline.mjs
node scripts/platform.mjs verify harness --case ownership
node scripts/platform.mjs verify contracts --case baseline
node scripts/platform.mjs verify schema --case history_lock
node scripts/platform.mjs verify images --case isolation
node scripts/platform.mjs verify lifecycle --case readiness
```

Omitting `--case` runs every delivered case in the selected suite.
`backend/platform-suites.json` maps each case to its requirement, setup, command,
proof and checkpoint. Unknown or undelivered suites/cases return 2; failed proofs,
missing prerequisites or cleanup return 1. No skips count as success.
`config` displays the isolated configuration; `cleanup opengym-platform-test-<hex16>`
accepts only a verified synthetic project's exact resources after interruption.
It rejects Foundation projects, foreign labels and shared images before removal.

The initial contract target reuses `Dockerfile.contracts` and its pinned Node/pnpm
toolchain, private network and tmpfs. The schema case builds `platform-test` from
`backend/Dockerfile` and starts a private disposable PostgreSQL (`platform-db`);
nothing binds host sources, datasets or ports. The lifecycle case exercises the
platform bootstrap HTTP factory; authenticated/business routes and a browser image
remain undelivered. Node is a test dependency here, not a Python runtime dependency.
These checks establish only the Node/client reference and verifier safety, never
Python parity or operational gates.

The schema case runs `tests/platform/test_schema.py` inside that image. It proves
role bootstrap, the `p000_bootstrap` privilege baseline, one Alembic history under
the shared migrator lock, genuine previous revisions, interrupted or failed
revisions that never advance head, and a runtime login that can read history but
cannot run DDL or assume owner/migrator roles. No business table is created; the
next revision belongs to the identity slice. `python -m
opengym_platform.platform_migrate bootstrap|up` accepts only the synthetic
`opengym_platform_test` target without `--deployment`. The explicit deployment
mode below uses separate file-backed credentials.

The lifecycle case starts real Uvicorn on container loopback with the restricted
runtime role. `/health/live` reports process liveness; `/health/ready` requires the
single known `p000_bootstrap` head, an accessible primary and read-write transaction
mode. Missing/unknown history, lost DB access and read-only mode return 503 without
migrating or repairing history. Connection recovery needs no process restart;
shutdown closes the bounded Foundation pool. Deployment settings have their own
file-secret loader; Foundation's synthetic destination guards are unchanged.

`/api/health` preserves the empty-instance JSON shape and no-store header, returning
503 when readiness fails. This bootstrap has no identities: its zero users applies
only to p000; Identity must supply the real count when its schema lands. The probe
checks connection/schema/write mode, not a business write or disk-full durability.
`/api/config` exposes compatible public flags, language and media limits, with no
coach disclosure or session interpretation yet. CORS/preflight and unknown-route
responses retain the public Node contract. `/docs` and `/openapi.json` stay absent;
nginx forwards only `/api`, keeping the `/health` probes internal. This is bootstrap
HTTP compatibility, not identity/media functionality or operational acceptance.

### Platform images and Compose

`backend/Dockerfile` supplies `dev`, `test`, `runtime`, `migrate` and `ops` targets
from the same Python/uv/PostgreSQL pins and `uv.lock`. Its default remains the
Foundation verifier. Runtime contains production dependencies, shared core and the bootstrap factory:
no tests, uv/pip, Node, SDK/CLI launcher or PostgreSQL tools. The migrator adds its
controlled Alembic chain; ops adds the matching `pg_dump`/`pg_restore` tools. No
container installs packages at startup. The ops default prints the tool version;
backup/restore orchestration is still pending.

Use `compose.platform.yml` with exactly one of `compose.platform.dev.yml` or
`compose.platform.ops.yml`, always with an explicit absolute `--env-file`. Do not
combine these files with the Node instance or Foundation. Dev mounts only backend
sources read-only for reload, with dependencies in the image. Ops has no source
binds/build and selects tested local image IDs (`sha256:<hex64>`), with no pull.
Build the existing frontend separately with `web/Dockerfile` when a web image is
needed; the image/network check substitutes a Python network probe for web and
does not certify a frontend build or browser flow.

Both combinations expose only `127.0.0.1:8080` (web port 80); API 3000 and DB 5432
stay private. Web is on `app`, DB on internal `database`, API on both. Dev/ops use
different database and volume names even when the same project name is supplied.
Keep their secrets in different private directories as well.

The env file contains references and non-secret configuration: `PLATFORM_SECRETS_DIR` (absolute directory)
and, for ops, `PLATFORM_WEB_DIGEST`, `PLATFORM_RUNTIME_DIGEST`,
`PLATFORM_MIGRATE_DIGEST`, `PLATFORM_OPS_DIGEST` (the hex suffix of each tested local
image's `.Id`, not a tag or a registry manifest digest). Dev can use
`PLATFORM_WEB_IMAGE` to identify its existing web image; API/tool image tags come
from the dev overlay. Inspect images with `docker image inspect <owned-tag>`.
Public API settings use the existing `INVITE_ONLY`, `ALLOW_GUEST`, `PASSWORD_LOGIN`,
`DEFAULT_LANG`, `MEDIA_UPLOADS`, `MEDIA_QUOTA_MB`, `MEDIA_IMAGE_MAX_MB`,
`MEDIA_GIF_MAX_MB`, `MEDIA_VIDEO_MAX_MB` and `MEDIA_VIDEO_MAX_SEC` names/defaults.
These advertise configuration; their business routes arrive in their owning slices.
Uvicorn access logging is disabled to avoid logging request URLs; structured
operational diagnostics remain a later slice.

Provide three distinct secret files named `bootstrap_password`,
`migrator_password`, `runtime_password`, each with at least 32 characters and at
most 4096 UTF-8 bytes, no CR/NUL
or embedded newline. Prefer no trailing newline; terminal LF is supported. On
Windows, generate without a BOM/CRLF (for example with `File.WriteAllText` and
`UTF8Encoding(false)`). Protect the host directory with filesystem permissions/ACLs;
on Linux ensure UID 1000 can read each mounted file. Compose file-backed secrets
do not reliably apply `uid`/`gid`/`mode` overrides. API mounts only its password;
migrate only its own; bootstrap explicitly mounts all three; ops mounts none yet.
Secret contents never belong in env files, image args, Git or evidence.

Inspect a dev configuration from the root (substitute the env path; use the ops
overlay for the equivalent operation):

```sh
docker compose --env-file <absolute-dev.env> -f compose.platform.yml -f compose.platform.dev.yml --profile '*' config
docker compose --env-file <absolute-dev.env> -f compose.platform.yml -f compose.platform.dev.yml build api migrate ops
```

Only on an explicitly authorized new disposable target: `up -d --wait db`,
`run --rm bootstrap`, then `run --rm migrate`. The latter invokes
`python -m opengym_platform.platform_migrate --deployment up`. Bootstrap initializes
missing roles without rotating existing credentials; up uses only the migrator
credential and the existing history lock. API never performs either operation.
Use `stop` to preserve data; no global prune/volume cleanup is part of this workflow.
After migration on that disposable target, `up -d api` starts the bootstrap factory
`opengym_platform.application:create_app`. Dev uses reload; ops uses one worker.
The images case starts both resolved combinations and checks HTTP from inside API;
web remains a network probe. It does not certify nginx/UI, an operational service
or a recovery gate. The normal Node instance remains authoritative.

`contracts/port-baseline.v1.json` freezes the independent fixture/test expectations,
OpenAPI, source revision and Foundation handoff revision. The route/error view is
the frozen OpenAPI; capability/consumer/store relationships are in
[CONTRACTS.md](CONTRACTS.md). The checker tolerates checkout CRLF/LF only. There is
no regeneration mode: a divergence requires explicit contract review, never an
expectation update merely to make the port pass.

### Foundation commands

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
| `contracts` | Existing Node/client behavior with independent synthetic fixtures. Does not start Python or PostgreSQL. |
| `pool` | Bounded Database transactions, cancellation, connection reuse, unknown commit outcomes and safe diagnostics. |
| `migrations` | Controlled Alembic CLI, serialized history, interruptions and restricted roles. |
| `isolation` | Real runtime/Training permissions, owner RLS and reuse after transaction outcomes. |
| `recovery` | Synthetic encrypted backup/copy/restore, restricted-owner reads, history/ownership/grants/RLS equivalence, timings and unsafe bundle/path/target rejection. Not an operational recovery command. |
| `all` | Contracts → environment → pool → migrations → isolation → recovery → lock/static checks, then real Docker harness regressions. Each group has its own project/DB so fixtures cannot inherit earlier ACLs or history. |

Required prerequisites, test failures, skipped/xfail/xpass/deselected required
Python proofs and cleanup failures return nonzero. `FOUNDATION_ALL_OK` is emitted
only after every group, its cleanup and the Docker regressions succeed. Docker
and host-harness commands have a five-minute deadline per invocation.
The runner bounds pytest to 60 seconds (180 for migrations) and scans captured diagnostics before
replaying them. A passing group proves only its synthetic scope, not platform
parity, HTTP authorization or operational acceptance.

The [archived OpenSpec tasks](../openspec/changes/archive/2026-10-25-add-python-platform-foundation/tasks.md)
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
Builds verify the lock rather than resolving new dependencies. `all` also runs
`uv lock --check --offline`, `uv pip check`, Ruff lint/format checks and mypy over
source/tests without changing files. Mypy is not strict; only the untyped asyncpg
driver has a missing-import exception, not all dependencies. Its cache is disabled
to keep the private 64 MiB tmpfs bounded. Evidence currently covers Linux/amd64;
other platforms and providers need their own verification.

```sh
node --test scripts/python-foundation.test.mjs backend/contracts-compare.test.mjs api/foundation/environment.test.mjs api/foundation/configuration.test.mjs
```

These host regressions exercise the harness, ownership guards, failure propagation
and cleanup. Full API/frontend suites and their build/locale checks are listed
in [CONTRIBUTING.md](../CONTRIBUTING.md) and existing CI. Synthetic Foundation results
do not replace those checks or operational gates.

## Builds and CI

Dependency manifests precede source/test copies. Node API and frontend
install in independent stages so a changed API manifest does not reinstall the
other projects. UID/GID-1000 BuildKit mounts cache uv/pnpm downloads outside image
layers. The pinned BuildKit builder is test tooling, not the application runtime.

```sh
node --test scripts/python-foundation-all.test.mjs
node --test scripts/python-foundation-build.test.mjs
```

The first command independently checks the complete `all` result. The build
probes use owned temporary fixtures of selected non-ignored build inputs and fresh builders: cold and
repeated builds, isolated source/test/image-metadata edits, coherent manifest/lock
constraint changes with the same installed versions, and rejected inconsistent
locks. They retain command/revision/platform/cache-state/timing/log evidence in a
printed temporary directory, then remove only their own builders and images.
These are observations of dependency-layer reuse, not speed guarantees or a
production-image benchmark. Never prune shared caches to imitate a cold build.
A hard-killed build probe may leave its printed builder and probe-tagged images;
inspect their token against the retained commands before exact removal. The normal
Foundation `cleanup` command does not own these separate build-probe resources.

[Consolidated CI](../.github/workflows/test.yml) runs on every pull request, including tooling,
Compose, backend, contract-consumer and OpenSpec changes on PR/push. Its job has no
continue-on-error and runs the same `all` and build-probe commands. Buildx imports
and exports GHA layer caches separately for each test image; download mounts are
builder-local, not remotely persisted by that export. No image is published and
branch protection is unchanged. Remote Actions/cache behavior requires an actual
workflow run; local results do not establish it. Existing product/Node Foundation
jobs remain in [test.yml](../.github/workflows/test.yml).

## Phase and gate handoff

Foundation uses explicit `compose.python-foundation.yml` and `backend/empty.env`;
its configuration and data are synthetic, and build inputs are not runtime
secrets. It provides no instance dev/operations overlay or production image.
The authoritative [environment/image matrix](../docs/reference/platform-modularity.md#matriz-de-ambientes-y-comandos-objetivo)
and [phase ownership](../docs/reference/platform-modularity.md#responsabilidad-y-aceptación-por-fase)
define the later combinations, mounts/ports, configuration, commands and support
criteria. `compose.platform.yml` plus dev/ops overlays and runtime/test/migrate
image targets remain future deliverables, not usable Foundation commands.
Runtime must exclude dev/tests/harness and install nothing at startup; operation
must verify resolved configurations, digests, platforms and recovery before cutover.

[SQL schema](../docs/reference/platform-schema.md),
[security](../docs/reference/platform-security.md) and
[local operations](../docs/reference/platform-operations.md) are approved target
contracts, not executed business DDL or operational evidence. Their delivery owner
is [port-compatible-platform](../openspec/changes/port-compatible-platform/proposal.md).
The port owns minimal identity followed by compatible Training read/save, colocated
Pydantic contracts/operations/repositories, real intermodule transactions and the
preserved frontend path. It also owns moving runtime-neutral JavaScript to
`shared/coach-core/` and updating imports/generators/builds; current paths stay put.
The [contract matrix](CONTRACTS.md) records participants and remaining parity gaps.

Synthetic results contribute to G1 only. G0, operational G1, GP, GO, G2/G3 and
production Recovery remain pending. Health/logging do not complete EV-08;
Foundation ownership does not complete functional EV-09. Provider/TLS/pooler,
WebAuthn/session continuity, off-host durability, full media/auth recovery,
arm64 and cutover/legacy retirement require their later acceptance.
