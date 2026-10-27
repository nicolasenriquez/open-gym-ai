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

The main `Dockerfile` owns Python application and verification targets.
`Dockerfile.contracts` runs frozen Node/client compatibility checks;
`Dockerfile.browser` supplies the compiled frontend and pinned browser proof;
`Dockerfile.security` supplies CI scanners. These tools stay outside the application
runtime. Their matching `.dockerignore` files protect each build context.
The former Foundation-only `Dockerfile.toolchain` is retired; current toolchain
checks run through `just test checks`. Archived Foundation commands are historical.

This README owns current platform usage. Operational requirements live in
[platform operations](../docs/reference/platform-operations.md); delivery status
and acceptance evidence live in the [active port tasks](../openspec/changes/port-compatible-platform/tasks.md).

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

`GET /api/v1/me` now verifies compatible cookie/bearer sessions and authorizes the actor
under a PostgreSQL row lock before installing transaction-local RLS ownership.
`ORIGIN` selects the current cookie name (`__Host-gymsid` on HTTPS); `SESSION_DAYS`
controls bearer renewal. These values retain their Node defaults.
With `PASSWORD_LOGIN=1`, `POST /api/v1/login/password` accepts the current identifier
and legacy name/email inputs, verifies compatible scrypt/NFKC credentials and
issues the same signed cookie. HTTPS also expires the legacy unprefixed cookie.
Crypto runs outside database leases with two workers and a queue of 32; credentials
and session version are rechecked under the account lock before issuance. Password
attempt/address budgets are process-local and reset on restart, as in Node.
`TRUST_PROXY=1` trusts the proxy-supplied client address; enable it only behind a
proxy that overwrites those headers. The supplied Uvicorn commands disable its
implicit proxy-header processing so it cannot bypass this flag.
`POST /api/v1/register/password` uses the same password-mode flag, transport
protections and session cookie. It preserves optional email, Unicode login aliases
and password policy. A namespace lock serializes claims, one-use invitations and
`FIRST_USER_ADMIN`; `ADMIN_UIDS` remains server configuration, never a signup field.
Scrypt runs outside database leases; the final transaction rechecks claims and
invitation before creating the account and consuming the code. Expired reset-only
alias reservations can be reclaimed without changing historical user dates.
WebAuthn registration/login use `POST /api/v1/register/options`, `/register/verify`,
`/login/options` and `/login/verify`. `RP_ID`, `RP_NAME` and `ORIGIN` keep the Node
defaults (`localhost`, `openGym`, `http://localhost:8080`). Ceremonies are process-local,
one-use, expire after five minutes and are capped at 20,000, so use the supported
single worker; restarting it abandons pending ceremonies. Login options ignore the
request body, as in Node. The four routes retain their Node CSRF exemption; the
verifier binds cryptographic responses to the expected origin, RP and challenge.
`webauthn==3.0.1` verifies existing COSE keys/counters without re-registration or
requiring UV. Crypto shares the bounded worker queue, outside DB leases; completion
rechecks key/counter/session version and owner before issuing the compatible cookie.
With password sign-in enabled, `GET/POST/DELETE /api/v1/account/password` and
`POST/DELETE /api/v1/account/email` support the current Settings contract. Changes
require a fresh own passkey assertion or the current password; the password cannot
be removed without a remaining passkey. Password replacement bumps session version,
removes pending reset/device links and renews only the caller cookie or bearer token.
Email changes and password removal preserve existing sessions. Email claims remain
reserved without passwords; only expired reset-only aliases can be reclaimed.
`POST /api/v1/logout/all` works even with passwords off, clears cookies and revokes
all owner sessions and pending device links without removing credentials.
Additional-passkey management, reset/link redemption, pairing and audit routes are not yet delivered.
Synthetic vectors do not establish physical-authenticator or native-device support.

`GET /api/v1/data` and `GET /api/v1/data/rev` read the verified actor's Training document
under the same account lock and transaction-local RLS context. A missing document
returns state null/revision zero without creating a row. PostgreSQL preserves the
complete JSONB document and generates strictly validated revision/write-id columns;
the client response omits only the server notes `_prior` and `_unstamped`.
`PUT /api/v1/data` compares a supplied non-null `baseRev` and optional `baseWid`. The verified actor's account
lock serializes first writes and revision comparison with the canonical update;
a conflict returns only that actor's client-visible document. Unknown-field
correction can store revision +2 while acknowledging +1 so the client fetches the
corrected copy. The application factory accepts an async `training_note_state`
collaborator, called only after confirmed commit with a two-second budget; its
failure cannot change the saved result. No media adapter is wired yet.
Omitting `baseRev` or sending null allows the compatible unconditional legacy replacement.
Edit/deletion stamps, private prior-value history and monotonic reset metadata follow
the Node contract. Server-owned write IDs retain at most 50 ancestors; a lost reply
retried with its old base conflicts against the committed document. Revisions retain
room for a two-step correction within JavaScript's safe integer range. Prior-value
matching accepts both legacy JSON key order and PostgreSQL JSONB key order.
The synthetic browser proof covers reconciliation against Python; this is not a
cutover-ready backend.

Public HTTP configuration retains the current names/defaults: `INVITE_ONLY`,
`ALLOW_GUEST`, `PASSWORD_LOGIN`, `DEFAULT_LANG`, `MEDIA_UPLOADS`,
`MEDIA_QUOTA_MB`, `MEDIA_IMAGE_MAX_MB`, `MEDIA_GIF_MAX_MB`,
`MEDIA_VIDEO_MAX_MB` and `MEDIA_VIDEO_MAX_SEC`. Business routes arrive in their
own slices. Uvicorn access logging is disabled; operational diagnostics are pending.

## HTTP API v1

All Python HTTP routes use `/api/v1`, including the internal probes
`GET /api/v1/health/live` and `GET /api/v1/health/ready`.
Unversioned routes are removed; there are no aliases or redirects.
Nginx blocks the two internal probes while forwarding the public API.
Swagger, ReDoc and the HTTP OpenAPI endpoint remain disabled.

Frontend builds select their HTTP contract with `VITE_API_PREFIX`:
`/api/v1` for Python and the default `/api` for Node. The Python Dev
overlay sets this build argument. For a permanent Python web image, build from
the repository root before selecting its tested image ID:

```sh
docker build -f web/Dockerfile --build-arg VITE_API_PREFIX=/api/v1 -t opengym-platform-web:v1 .
```

The value is compiled into the frontend; a runtime environment variable cannot
change an existing image. A Python frontend build does not fall back to Node
paths or deliver capabilities that have not yet been ported.

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
| `identity_register` | Password/email policy vectors, concurrent Unicode claims, invitation consumption, first-admin assignment and rollback/crypto-time revalidation. |
| `identity_account` | Own password/email and logout-all, current proof, last-way-in, Unicode/expired/concurrent claims, atomic revocation/rollback and restricted migration/ACLs. |
| `identity_passkey` | Independent Node/Python ES256/RS256/Ed25519 vectors, HTTP registration/login, replay/expiry, counters, concurrent revocation and restricted migration/ACLs. |
| `training_read` | Authenticated own/empty reads, canonical metadata, strict generated SQL projections, RLS and migration continuity. |
| `training_write` | First/legacy saves, conflicts, Node stamp vectors, reset/history/lineage, lost replies, persisted correction and postcommit failure boundary. |
| `training_browser` | Compiled frontend login, offline dirty/active state, real 401/two 409s, lost reply and restored lineage with independent PG observation. |
| `images` | Runtime/tool separation, dev/prod topology and file-secret isolation. |
| `checks` | Frozen dependencies, lint, format and types inside the test image. |

The verifier uses `backend/empty.env`, unique `opengym-platform-test-<hex16>`
projects and `org.opengym.platform=synthetic` labels. It exposes no ports or personal
mounts and cleans up only owned resources. After confirming an interrupted run ended:

`node scripts/platform.mjs cleanup <exact-printed-project>`

No global prune, volume wipe or removal of foreign/shared images is part of cleanup.

### Browser proof

Run `node scripts/platform.mjs verify training_browser --case offline_sync`.
The isolated browser image builds the existing frontend with `/api/v1`, using the
same pinned Node/pnpm and frontend lock. Its separate npm lock fixes Playwright
1.62.1; `versions.json` fixes the official browser image digest and Chromium revision.
There are no browser installations at runtime or on the host.

The Playwright library drives UI actions; pytest owns synthetic accounts, the real
restricted Python API, faults and a separate PostgreSQL observer. It does not use
Playwright CLI or substitute successful API responses. Only its test image contains
the fixture control server. No fixture routes are added to the application.

The current HTTP flow preserves the loaded page and saved dirty/active state offline,
then reloads on reconnection. HTTPS service-worker cold launch and native devices are
outside this proof. A test-only same-origin static/proxy transport serves the compiled
bundle; this does not verify nginx deployment. Screenshots for six cases and a sanitized
result are copied to `.scratch/platform-browser/<printed-project>/` before owned
containers are removed. Browser state, passwords and SQL documents are not exported.

Cold/warm/source/manifest cache and lockfile regressions live in
`scripts/platform-build.test.mjs`. Contract ownership and retention are described below.

### Compatibility fixtures and transition baseline

`contracts/` contains synthetic test inputs and independent expected results, not
application storage or execution logs. Their lifecycle depends on the guarantee
they protect, rather than their JSON format or the retirement of Node alone.

| Files | Purpose and retention |
| --- | --- |
| `port-baseline.v1.json`, `suites.v2.json` | Transition manifest and Node/client suite inventory. Retain until replacement coverage and retirement acceptance allow their consumers to be removed or migrated. |
| `http-baseline.v1.json`, `http-health.v1.json` | Frozen HTTP expectations used by the transition harness and comparator. Preserve relevant behavior as regression tests before retiring the harness or fixtures. |
| `identity-sessions.v1.json`, `identity-passwords.v1.json`, `training-stamps.v1.json` | Independent compatibility vectors consumed by Python tests. Retain while session, credential and synchronization compatibility remains supported, including after Node retirement. |
| `identity-registration.v1.json` | Registration validation vectors belonging to the registration slice. Its delivery and acceptance status is tracked in the active port tasks, independently of this inventory. |
| `password-vectors.mjs`, `generate-training-stamps.mjs` | Node-based authoring tools, not runtime dependencies. Review intentional coverage extensions; migrate or retire the generators separately from the retained vectors. |

Run `node scripts/platform.mjs verify contracts --case baseline` for the current
integrated Node HTTP and client compatibility verification. The command
`node scripts/python-foundation.mjs run contracts` in the frozen
[historical inventory](CONTRACTS.md#ejecución-y-handoff) is retired; use the platform
command above. `node scripts/platform-baseline.mjs` checks frozen file hashes only
and does not execute the behavioral tests.

`port-baseline.v1.json` protects the initial inventory and listed sources by hash;
it does not cover every later identity or Training vector. Keep expected results
independent of the Python implementation under test. Generator output requires
review of changed scenarios and expectations, never automatic regeneration to
accept implementation drift. Full Training documents in the stamp vectors make
input/output differences reviewable; repeated structure alone is not a removal criterion.
Before removing or merging a fixture, identify its consumers and demonstrate that
replacement tests preserve its guarantee. Delivery status and retirement acceptance
remain in the [active port tasks](../openspec/changes/port-compatible-platform/tasks.md).

Build contexts are allowlisted: root `.dockerignore` serves the web image,
`api/.dockerignore` serves Node, and `backend/.dockerignore` serves Python.
The contracts/security/browser Dockerfiles have their own ignore files, which override the
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
