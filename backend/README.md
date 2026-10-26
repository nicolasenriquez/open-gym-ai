# OpenGym Python platform

The current personal application remains Node/JSON. The Python port supplies its
bootstrap HTTP lifecycle, restricted PostgreSQL access and controlled migrations;
it is not yet a replacement for the complete application or an operational backup service.

## Start here

Run commands from the repository root with Node 22+ and Docker Engine Linux/Compose.
Python, uv and PostgreSQL run inside images. Bare `just` lists commands.

`deploy/` contains exactly four entrypoints:

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Shared Python service topology, networks, secrets and data. |
| `docker-compose.dev.yml` | Development builds and backend reload. |
| `docker-compose.prod.yml` | Permanent local operation with tested image IDs; no source mounts or startup builds. |
| `docker-compose.test.yml` | Current disposable verifier, never an application instance or Foundation stack. |

The root Compose and `just up` still run the authoritative Node application.
The prod filename does not authorize cutover or cloud deployment. The image target
`runtime` is also the default build; tests require explicit target `test`.
Targets `dev`, `migrate` and `ops` keep their separate dependencies and privileges.

## Platform images and Compose

Use the base plus exactly one dev/prod overlay, always with `--project-directory .`
and an explicit private env-file. `just dev <absolute-dev.env>` builds web/API/migrator,
waits for PostgreSQL, runs bootstrap then migrations as one-off containers, and waits
for API readiness and web health. `just dev-stop <absolute-dev.env>` preserves data.
Dev serves the compiled frontend; backend sources are mounted read-only for reload.

Set `PLATFORM_WEB_PORT=8081` and `PLATFORM_SECRETS_DIR=<absolute-private-directory>`
in the private Dev env-file. The default web port is 8080 for permanent operation;
API 3000 and PostgreSQL 5432 stay private. Dev and prod use distinct database/volume
names even if given the same project name. Keep their secrets separate as well.

Prepare four different UTF-8 files: `bootstrap_password`, `migrator_password`,
`runtime_password` and `session_secret`, each 32–4096 bytes, without BOM, CR/NUL or embedded newline.
A terminal LF is supported. Protect the directory using permissions/ACLs; on Linux
UID 1000 must be able to read the mounted files. Secret contents never belong in env
files, image arguments, Git or evidence. API mounts only its runtime password and
session-signing key; migrate mounts only its own password, and bootstrap mounts the
three database passwords. Ops mounts none yet. `PLATFORM_SESSION_SECRET_FILE` points
to the API's key mount. For compatible session continuity, provision the original
signing key explicitly; never generate or rotate it implicitly during startup or port.
Keep it separate from all database passwords and future coach decryption material.

Prod uses `PLATFORM_WEB_DIGEST`, `PLATFORM_RUNTIME_DIGEST`,
`PLATFORM_MIGRATE_DIGEST` and `PLATFORM_OPS_DIGEST`: the hex suffix of tested local
image IDs, not tags or registry manifest digests. `just prod-config <absolute-prod.env>`
validates configuration without starting services. API never migrates at startup.
A failed bootstrap/migration stops the Dev recipe before API/web startup.

`GET /api/me` now verifies compatible cookie/bearer sessions and authorizes the actor
under a PostgreSQL row lock before installing transaction-local RLS ownership.
`ORIGIN` selects the current cookie name (`__Host-gymsid` on HTTPS); `SESSION_DAYS`
controls bearer renewal. These values retain their Node defaults.
With `PASSWORD_LOGIN=1`, `POST /api/login/password` accepts the current identifier
and legacy name/email inputs, verifies compatible scrypt/NFKC credentials and
issues the same signed cookie. HTTPS also expires the legacy unprefixed cookie.
Crypto runs outside database leases with two workers and a queue of 32; credentials
and session version are rechecked under the account lock before issuance. Password
attempt/address budgets are process-local and reset on restart, as in Node.
`TRUST_PROXY=1` trusts the proxy-supplied client address; enable it only behind a
proxy that overwrites those headers. The supplied Uvicorn commands disable its
implicit proxy-header processing so it cannot bypass this flag.
Registration, account-management and audit
routes are not yet delivered.

Public HTTP configuration retains the current names/defaults: `INVITE_ONLY`,
`ALLOW_GUEST`, `PASSWORD_LOGIN`, `DEFAULT_LANG`, `MEDIA_UPLOADS`,
`MEDIA_QUOTA_MB`, `MEDIA_IMAGE_MAX_MB`, `MEDIA_GIF_MAX_MB`,
`MEDIA_VIDEO_MAX_MB` and `MEDIA_VIDEO_MAX_SEC`. Business routes arrive in their
own slices. Uvicorn access logging is disabled; operational diagnostics are pending.

## Current verification

`just test <suite>` and `just test-case <suite> <case>` delegate to the same verifier
used by CI. Unknown/unimplemented cases fail with exit 2; missing prerequisites,
empty/skipped/failed proofs and cleanup failures never count as success.

| Suite | Proof |
| --- | --- |
| `harness` | Ownership, contamination rejection and protected sentinels. |
| `contracts` | Frozen Node/client compatibility expectations. |
| `database` | Pool, cancellation, rollback, owner isolation and commit uncertainty. |
| `schema` | Current Alembic history, locking and restricted roles. |
| `lifecycle` | HTTP health/readiness, schema compatibility and shutdown. |
| `identity_session` | Cookie/bearer actor selection, HMAC/version validation, RLS and expiry/revocation during waits. |
| `identity_password` | Node scrypt/NFKC vectors, login cookies, failure budgets, dummy work and concurrent credential/version revalidation. |
| `images` | Runtime/tool separation, dev/prod topology and file-secret isolation. |
| `checks` | Frozen dependencies, lint, format and types inside the test image. |

The verifier uses `backend/empty.env`, unique `opengym-platform-test-<hex16>`
projects and `org.opengym.platform=synthetic` labels. It exposes no ports or personal
mounts and cleans up only owned resources. After confirming an interrupted run ended:

`node scripts/platform.mjs cleanup <exact-printed-project>`

No global prune, volume wipe or removal of foreign/shared images is part of cleanup.
Cold/warm/source/manifest cache and lockfile regressions live in
`scripts/platform-build.test.mjs`. Baselines in `contracts/port-baseline.v1.json`
and their frozen [inventory](CONTRACTS.md) are unchanged; historical paths there are
not current launch instructions and must not be regenerated to admit drift.

Build contexts are allowlisted: root `.dockerignore` serves the web image,
`api/.dockerignore` serves Node, and `backend/.dockerignore` serves Python.
The contracts/security Dockerfiles have their own ignore files, which override the
root filter. Keep each allowlist aligned with its Dockerfile's `COPY` inputs;
exercise media and the shared coach core remain required web inputs.
`.gitignore` protects Git only; it does not filter Docker contexts. Local env files,
provider credentials, host dependencies and caches are excluded separately.
Node/web dependency installs use builder-local pnpm cache mounts with frozen locks;
the package store is not copied into images or mixed with application data.

## Retired transition tooling

Standalone Node/Python Foundation stacks, runners and their exclusive prototype
implementations are retired. Pool coverage is retained under the current verifier;
Node/client contracts, current platform tests and image/cache checks remain active.
[Node Foundation evidence](../openspec/changes/archive/2026-10-22-add-postgres-foundation/design.md)
and [Python Foundation evidence](../openspec/changes/archive/2026-10-25-add-python-platform-foundation/design.md)
remain historical records, not commands that still exist or proof of current recovery.

The old synthetic migration/recovery prototypes are not the current platform schema
or an operational restore. Their retirement does not complete pending backup/restore,
security, cutover or Recovery gates. Follow the [active port tasks](../openspec/changes/port-compatible-platform/tasks.md)
and [operation contract](../docs/reference/platform-operations.md) before those slices.
The cleanup does not change application authority, user data or deployment acceptance.
