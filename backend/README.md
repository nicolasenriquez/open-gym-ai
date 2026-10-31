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

Prepare five UTF-8 files: `bootstrap_password`, `migrator_password`,
`runtime_password`, `session_secret` and `coach_secret`, each 32–4096 bytes, without BOM, CR/NUL or embedded newline.
A terminal LF is supported. Protect the directory using permissions/ACLs; on Linux
UID 1000 must be able to read the mounted files. Secret contents never belong in env
files, image arguments, Git or evidence. API mounts only its runtime password,
session-signing key and Coach decryption material; migrate mounts only its own password, and bootstrap mounts the
three database passwords. Ops mounts none yet. `PLATFORM_SESSION_SECRET_FILE` points
to the API's key mount. For compatible session continuity, provision the original
signing key explicitly; never generate or rotate it implicitly during startup or port.
Keep it separate from all database passwords and Coach decryption material.

The Python subscription API provides `/api/v1/push/public-key`, `subscribe`,
`status` and `unsubscribe`. VAPID keys stay in `DATA_DIR/vapid.json`, outside SQL
and images. On the first public-key request a missing pair is created atomically
with mode 0600; an unreadable or invalid existing pair returns 503 and is never
replaced. Provision the original pair explicitly when porting existing subscribers.
Status and unsubscribe are owner-scoped; endpoint transfer preserves the original
creation date and valid device ID, with at most twenty subscriptions per owner.
`ALLOWED_PRIVATE_IPS` retains the explicit address/range/CIDR exception contract.
Registration checks HTTPS, credentials and private IP literals without contacting
the endpoint. Apply `p005_delivery` before starting the updated API for internal
reminders and missed-workout nudges. The single-worker scheduler reads Training
preferences under a revalidated owner lock, uses local dates and atomically claims
the day's alert before sending outside SQL. It catches up reminders within fifteen
minutes and applies the existing evening window, queue/pins, excused days and
three-miss back-off. Failed sends are not automatically retried for that date;
claiming does not establish external receipt or exactly-once delivery.

Web Push uses the existing external VAPID pair, RFC 8291 encryption and bounded
HTTPS sends. Each connection resolves/checks all addresses, pins a checked IP and
verifies TLS against the original hostname; redirects and environment proxies are
not followed. Dead 403/404/410 subscriptions are pruned only if still owned with the
same keys. Notification copy is generated from existing strings with
`node scripts/build-push-assets.mjs`; `--check` detects drift. Verification uses a
private TLS fixture and independent Node encryption vectors, not real push services
or physical devices. Activity/presence updates and rest timers remain pending in
7.3; the nudge's process-local active-owner hook is not yet wired to HTTP.

Python administration provides `GET /api/v1/admin/users`, `GET /api/v1/admin/user?id=…`
and `POST /api/v1/admin/user/disable`. Apply bootstrap and the `p004_admin_users`
migration before starting the updated API. Active administrators can inspect the
existing workout/bodyweight projection without media or internal document metadata.
The list includes real subscription presence; live-workout presence remains pending.
Password/email/reset availability is disclosed only with `PASSWORD_LOGIN=1`.
Disabling any administrator is refused. Disabling another profile immediately denies
its sessions and removes pending device links; re-enabling retains Node's session
version behavior. Pull-only profiles update last-sync at most every ten minutes;
failed timestamp bookkeeping does not fail a successful Training read. Deletion,
invitation management, reset issuance and administrative audit are not yet ported.

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
`GET/DELETE /api/v1/account/passkeys` and `POST /api/v1/account/passkeys/options`,
`/verify` and `/rename` support the existing Settings passkey list and management.
Adding/removing requires fresh owner proof; renaming requires the verified session.
The cap of 20 and last-way-in protection are rechecked under the owner lock. A
password counts only while password sign-in is enabled. Add ceremonies are one-use,
owner/version-bound and expire after five minutes; logout-all invalidates them.
Removing a passkey also removes pending device links, but preserves existing sessions.
With password sign-in enabled, `POST /api/v1/login/password-reset` redeems an
admin-issued 24-hour code by profile name or email. Only the digest is stored;
case, spaces and dashes do not matter. Password-policy errors preserve the code.
Successful redemption atomically claims the password alias, replaces the password,
consumes the code, revokes sessions/device links and sets a new session cookie,
preserving passkeys. Wrong codes share the password address budget, without a
per-account lockout. Administrative issuance and audit routes are not yet delivered.
`POST /api/v1/pair/create` makes one replaceable mobile pairing code per owner,
valid for five minutes. Pairings remain process-local and disappear on restart.
`POST /api/v1/pair/redeem` is CSRF-exempt and returns a bearer token and public user,
without a cookie. Redemption rechecks the code deadline and current owner/session
version under lock; logout-all or password replacement invalidates pending codes.
`POST /api/v1/account/device-link` requires fresh own proof and returns a one-use
10-minute code, stored only as a digest under owner RLS. A new code replaces the old
one. `POST /api/v1/device-link/options` and `/verify` bind a five-minute WebAuthn
ceremony to that code and owner. Verification atomically adds the passkey, consumes
the link and issues a cookie without revoking other sessions. The 20-key cap,
duplicate credentials, code expiry and concurrent revocation are checked under lock.
Both device-link routes retain CSRF protection and a separate link-address failure
budget. Device links survive restart, but require new ceremony options afterwards.
Pairing and device-link routes remain available with password sign-in disabled;
creating a device link then requires fresh passkey proof.
Synthetic vectors and the browser's virtual authenticator do not establish
physical-authenticator or native-device support.

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
failure cannot change the saved result. With media enabled, the default collaborator
updates the owner's external reference marks.
Omitting `baseRev` or sending null allows the compatible unconditional legacy replacement.
Edit/deletion stamps, private prior-value history and monotonic reset metadata follow
the Node contract. Server-owned write IDs retain at most 50 ancestors; a lost reply
retried with its old base conflicts against the committed document. Revisions retain
room for a two-step correction within JavaScript's safe integer range. Prior-value
matching accepts both legacy JSON key order and PostgreSQL JSONB key order.
The synthetic browser proof covers reconciliation against Python; this is not a
cutover-ready backend.

`PUT /api/v1/media/{sha256}` streams an owner's raw upload to a private temporary
file, checks its hash, declared/sniffed category, actual format cap and bounded
MP4/MOV headers/duration, then rechecks the session under the account lock before
publishing. Transfers hold no database lease. The seven existing formats, 201/200
idempotency and replacement of truncated files are preserved. `GET` streams only
the actor's file with private/no-store and sandbox headers; a foreign hash returns
the same 404 as an absent file, including for administrators. There are no Range
or ETag responses. `MEDIA_UPLOADS=0` removes both routes.

The API's writable `/data` volume stores `uploads/<profile>/<hash>.<ext>` and
`.gc.json`; dev and ops use separate named media volumes, separate from PostgreSQL.
Standalone Python uses `DATA_DIR` (default `/data`). Files and owner directories use
0600/0700 permissions. Training supplies references through its public, owner-scoped
interface and database errors propagate before new publication.
`POST /api/v1/media/missing` accepts at most 1000 lowercase SHA-256 hashes and returns
only the actor's missing files and usage. Empty files and files truncated since this
process observed their size are missing; no checksum scan at startup is promised.
Uploads reserve their declared length (or full kind cap for a stream of unknown length)
against the owner's quota, with two concurrent uploads and an hourly per-account budget.
Reservations and temporary files are released after refusal, disconnect or failure.
Quota pressure may reclaim the actor's files unused for an hour, only after a successful
Training reference read; missing Training state or unreadable marks preserve bytes.
The free-disk floor uses the media filesystem. Startup removes abandoned regular
temporary files; hourly maintenance removes temporary files older than an hour,
preserving symlinks and ordinary media. Budgets/reservations are process-local under
the supported single worker. The existing client queue is verified through a real
picker, failed upload, reload and manual retry.
`POST /api/v1/media/sweep` collects only the signed-in owner's unreferenced files
without a grace period, at most ten requests per hour. It reads current Training
under the account lock before deleting; a database failure never means no references.
Periodic GC starts five minutes after startup and repeats hourly, using
`MEDIA_GC_GRACE_DAYS` (14 by default). Corrupt/unreadable marks restart that grace;
missing Training and orphan directories preserve bytes. Restored directory/blob
links and links at the temporary marks path cannot redirect reads or collection.
The internal identity interface confirms only an existing account ID under lock;
it is not exposed through HTTP and grants no global SELECT. Apply the new forward-only
`p002_media_gc` migration before serving traffic; older schema heads fail readiness.
These routes do not make the partial Python platform ready for cutover.

Coach configuration starts at the forward-only `p003_coach` migration. Run bootstrap
before upgrading an existing schema so the restricted, non-login Coach executor
exists; API startup never creates roles or migrates. `GET /api/v1/config` now reads
the Coach disclosure from PostgreSQL, requires a migrated database and fails safely
rather than inventing configuration when that read fails.
The configuration tables preserve provider IDs, models, allowlisted non-secret options
and external secret references. The runtime cannot read these tables directly.
Imported `claude` (Agent SDK) and `codex` (CLI) selections remain identifiable in
public configuration with `enabled:false`; they are never converted to Anthropic or
OpenAI HTTP. `COACH_DISABLED=1` hides the Coach disclosure without changing storage.
Authenticated `GET /api/v1/coach/status` and `POST /api/v1/coach/plan`, `/review`,
`/debrief` return the compatible 503/code `off` before any work for unavailable providers.
They revalidate sessions under the actor lock and retain POST CSRF checks.
The forward-only `p003_coach_jobs` migration adds current jobs, profile generations,
UTC usage counters and bounded personal history. Its restricted reservation function
atomically checks the actor, consent, generation, single-flight and both caps;
zero caps mean unlimited.
The application-operation coordinator admits at most two executions, holds no SQL
transaction during a call and cancels queued/running tasks at shutdown.
Before readiness, the single API worker records interrupted jobs as `failed/restart`
and removes them atomically, preserving usage and never replaying work. Recovery
requires a compatible writable schema; it does not create roles or migrate.
The forward-only `p003_coach_http` migration adds owner-scoped pending proposals
and the restricted `coach.execution_config` function. With an active instance
configuration and consent, the status/plan/review/debrief routes use the Python
payload, HTTP transport and validator. Responses become pending proposals; they
never write Training. Payloads use bounded disclosed categories and a keyed
pseudonym, and proposals retain the client's plan fingerprint. The pipeline has
one repair round; transports retain bounded transient retries, compatible endpoint
and JSON-mode fallbacks, routed headers and classified safe failures. `httpx==0.28.1`
is a runtime dependency. Prompts, schemas, catalogue and icon data are generated
by `node scripts/build-coach-assets.mjs`; the editable sources remain singular.

The four HTTP wire formats are verified with private endpoints and synthetic keys.
A configured keyless compatible endpoint can execute. The application factory's
credential callback remains a private operation seam, not an HTTP credential field.
Scheduling and the client
availability UX remain in their later slice. No SDK/CLI launcher,
credential cache mount, refresh or Node fallback is present; original credentials
stay outside active runtime mounts.

`p003_coach_client` adds authenticated consent disclosure, private opt-in cohort
medians and scheduled reviews. Cohorts require three participants and three
contributors per exercise; only coarse aggregates enter review/debrief prompts.
Sharing and Coach consent are checked separately, without caching participants.
The single worker checks configured cadence at startup and every minute, skips
unread proposals and active jobs, and uses the existing atomic quota reservation.
Finished reviews prevent replay on restart. Disabling cadence prevents new work;
an already admitted review can finish under its original consent and generation.
SDK/CLI selections remain unavailable without fallback or quota consumption;
the web Coach and mobile server setup show their provider and unavailable state.
The existing phone HTTP Coach remains independent of server availability.

`p003_coach_admin` adds authenticated admin configuration, connect/disconnect,
model listing and test routes under `/api/v1/admin/coach`, plus own
`GET /api/v1/coach/account`. Provider switches preserve each provider's model,
options and key. HTTP calls run outside SQL transactions and admin authorization
is rechecked afterward. The admin card reads real UTC usage and up to one hundred
anonymous results, showing the latest twenty without personal readings or job IDs.

Compose mounts `coach_secret` separately and supplies `PLATFORM_COACH_SECRET_FILE`.
Keep the original Coach decryption secret when rotating the session-signing key.
For imported records, `coach_secret` contains the original Node `data/secret`;
a new value requires reconnecting those credentials.
Outside Compose, omitting this setting leaves filed credentials unreadable and
prevents connecting a new key; a keyless compatible endpoint remains usable.
Encrypted records live in `DATA_DIR`: opaque `coach-key-<32 hex>.json` files are
referenced from SQL; imported `coach-auth-<uid>.json` records remain personal and
outside Training/export. Files use legacy HKDF-SHA256/AES-256-GCM format, bounded
reads, no symlink following and mode 0600 for new keys. `cryptography==50.0.2`,
already present through WebAuthn, is now an explicit direct dependency.
Wrong keys and corrupt records fail closed, including optional-key endpoints.
Configuration limits must fit the schema's whole-number bounds; fractional limits
are rejected instead of silently rounded.
Per-profile mode uses only the requesting profile's existing record; admin tests
never spend a profile credential. As in Node, there is no public authMode switch
or per-profile connect route. Imported personal instance bindings reject foreign
profiles; disconnecting clears the binding rather than sharing that credential.
SDK/CLI connect/test/execute return 503/code `off` and preserve their selection.

`p003_coach_lifecycle` grants only owner-scoped forgetting under the existing RLS
policies. `POST /api/v1/coach/pending/resolve` records applied/dismissed counts and
clears the proposal without changing Training; repeated calls are harmless. Status
and resolution expire proposals lazily, retaining the latest twenty events, including
multiple events for one job. `POST /api/v1/coach/forget` works even when the provider
is unavailable: it clears current jobs, proposals and history, disables sharing and
advances the persistent generation. It retains today's UTC profile usage and the
anonymous instance aggregate. Training opt-out/reset clears Coach in the same SQL
transaction; cancellation happens after commit. Queued work is dropped and active
HTTP requests are cancelled. Completion still rechecks owner, consent and generation
so late responses cannot restore forgotten/deleted content or recreate usage.

Public HTTP configuration retains the current names/defaults: `INVITE_ONLY`,
`ALLOW_GUEST`, `PASSWORD_LOGIN`, `DEFAULT_LANG`, `MEDIA_UPLOADS`,
`MEDIA_QUOTA_MB`, `MEDIA_IMAGE_MAX_MB`, `MEDIA_GIF_MAX_MB`,
`MEDIA_VIDEO_MAX_MB` and `MEDIA_VIDEO_MAX_SEC`. Private upload controls also use
`MEDIA_UPLOADS_PER_HOUR` (600) and `MEDIA_MIN_FREE_MB` (512, zero disables the floor).
`MEDIA_GC_GRACE_DAYS` is private configuration too; zero disables the grace.
Business routes arrive in their
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
| `identity_session` | Cookie/bearer actor selection, HMAC/version validation and expiry/revocation during waits; `restricted_pool` checks final SQL signatures/ACL/FORCE RLS and real HTTP with a one-slot runtime pool across commit, rollback, errors, timeouts and cancellation. |
| `identity_password` | Node scrypt/NFKC vectors, login cookies, failure budgets, dummy work and concurrent credential/version revalidation. |
| `identity_register` | Password/email policy vectors, concurrent Unicode claims, invitation consumption, first-admin assignment and rollback/crypto-time revalidation. |
| `identity_account` | Own password/email, logout-all and passkey management; current proof, cap/last-way-in, concurrent claims, atomic revocation/rollback and restricted migration/ACLs. |
| `identity_reset` | Single-use reset, code/identity revalidation, expiry, atomic password/alias/session changes and rollback. |
| `identity_links` | Mobile bearer pairing and code-bound passkey links; replacement, single-use, expiry/revocation, rollback and restricted migration/ACLs. |
| `identity_passkey` | Independent Node/Python ES256/RS256/Ed25519 vectors, HTTP registration/login, replay/expiry, counters, concurrent revocation and restricted migration/ACLs. |
| `training_read` | Authenticated own/empty reads, canonical metadata, strict generated SQL projections, RLS and migration continuity. |
| `training_write` | First/legacy saves, conflicts, Node stamp vectors, reset/history/lineage, lost replies, persisted correction and postcommit failure boundary. |
| `training_browser` | Compiled Settings passkey/device-link/reset flows, login, offline dirty/active state, real 401/two 409s, lost reply, restored lineage and a private progress photo downloaded into the verified local store and displayed offline. |
| `media` | `roundtrip`: seven formats, hash/type/cap rejection, private headers/foreign 404, streaming revocation/idle timeout, restart/idempotency/repair and public Training reference marks. |
| `media --case quota_and_missing` | Private missing/usage, concurrent quota reservations, safe pressure reclamation, upload/disk limits and temporary cleanup. |
| `coach_state --case deferred_provider` | Imported SDK/CLI selection preservation, public availability, 503/off without work, actor revalidation/CSRF, config constraints/ACL and previous-head upgrade. |
| `coach_state --case atomic_enqueue` | Atomic UTC caps and single-flight, two execution slots outside SQL, restricted ACL/RLS, configuration-head upgrade and HTTP lifecycle recovery without replay. Its private operation probe does not by itself verify the HTTP pipeline. |
| `coach_state --case late_result` | Decisions/expiry and twenty-event history; own forgetting while unavailable, current-day usage retention, HTTP/queued cancellation, opt-out/reset rollback and late completion after forgetting or synthetic account deletion. |
| `coach_http --case validated_proposal` | Private HTTP fixtures for all four wire formats, independent payload/validator/fingerprint vectors, one repair round, real timeout and safe failures; consent/RLS and pending proposals without changing Training. |
| `coach_admin --case credentials` | Admin config/models/test/connect/disconnect and own account; external ciphertext, profile isolation, unreadable keys, rollback, late revocation/expiry and migration/ACL/RLS. |
| `coach_client --case consent_and_availability` | Consent/sharing, coarse provider payloads, scheduled reviews/restart, timezone edges and bounded SQL grants/upgrades. UI proof is recorded separately from this backend case. |
| `media_gc --case fail_safe` | Explicit/periodic GC, identity lock/RLS, unreadable references/marks, upload/revocation races, symlink sentinels and previous-head migration. |
| `images` | Runtime/tool separation, dev/prod topology, private persistent media volumes and file-secret isolation. |
| `notifications --case subscription` | Owner endpoint transfer, original date/device fallback, cap twenty, VAPID continuity and restricted ACL/RLS. |
| `notifications --case local_dates` | Internal scheduler, local/DST dates, queue/pins and nudge back-off; concurrent revocation, date claims, private TLS transport/SSRF, independent encryption vectors and safe pruning. |
| `admin_users --case actor_target` | Active admin/target separation, bounded Training projections, subscription presence, disable safeguards, ordered revocation, rollback, pull timestamps and restricted migration/ACLs. |
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
bundle; this does not verify nginx deployment. Screenshots for twelve cases and a sanitized
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
