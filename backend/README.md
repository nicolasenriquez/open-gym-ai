# OpenGym Python platform

This repository supplies the Python/FastAPI/PostgreSQL application and its isolated
verification tooling. The former Node/JSON backend and transition harness are retired.
Repository delivery does not migrate a running instance; real cutover remains deferred
and needs separate scoped authorization. Recovery remains outside this delivery.

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

There is no root Compose or legacy `just up`/`stop`/`logs` shortcut.
The prod filename does not authorize cutover or cloud deployment. The image target
`runtime` is also the default build; tests require explicit target `test`.
Targets `dev`, `migrate` and `ops` keep their separate dependencies and privileges.

The main `Dockerfile` owns Python application and verification targets.
`Dockerfile.client` runs frozen Node/client compatibility checks;
`Dockerfile.browser` supplies the compiled frontend and pinned browser proof;
`Dockerfile.security` supplies CI scanners. These tools stay outside the application
runtime. Their matching `.dockerignore` files protect each build context.
The former Foundation-only `Dockerfile.toolchain` is retired; current toolchain
checks run through `just test checks`. CI runs the same tests directly in its
`python-checks` job with uv; application runtime and integration tests remain in
images. Archived Foundation commands are historical.

This README owns current platform usage. Operational requirements live in
[platform operations](../docs/reference/platform-operations.md); delivery status
and acceptance evidence live in the [active port tasks](../openspec/changes/archive/2026-11-04-port-compatible-platform/tasks.md).

## Platform images and Compose

Use the base plus exactly one dev/prod overlay, always with `--project-directory .`
and an explicit private env-file. `just dev <absolute-dev.env>` builds web/API/migrator,
waits for PostgreSQL, runs bootstrap then migrations as one-off containers, and waits
for API readiness and web health. `just dev-stop <absolute-dev.env>` preserves data.
Dev serves the compiled frontend; backend sources are mounted read-only for reload.

The PostgreSQL healthcheck probes the maintenance database `postgres`, keeping
its transient connections outside the application database during capture/restore.
API readiness still checks the actual application database and schema; see the
[capture contract](../docs/reference/platform-operations.md#procedimientos-operativos-especificados).

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
or physical devices.

`POST /api/v1/push/test` attempts all of the caller's subscriptions. Rest alerts use
`POST /api/v1/push/rest-timer` and `/push/rest-timer/cancel`, with one replaceable
timer per owner/device. Missing or invalid device IDs retain account-wide behavior;
subscriptions without a device ID also receive device-specific alerts. Sends
revalidate the initiating session, so expired/revoked sessions cannot send a pending
alert. These operations do not require reminders to be enabled.
`POST /api/v1/activity` supplies the ephemeral live-workout snapshot used by the
admin list and nudge suppression. Presence expires after 70 seconds without a
heartbeat or 45 seconds after the first hidden signal; a new heartbeat clears that
signal. Navigation clears presence immediately. Disabling a profile clears its
presence and pending timers. API shutdown cancels pending timers; restart restores
neither timers nor presence. No migration or persistent timer store is added.

Python administration provides `GET /api/v1/admin/users`, `GET /api/v1/admin/user?id=…`
and `POST /api/v1/admin/user/disable`. Apply bootstrap and the `p004_admin_users`
migration before starting the updated API. Active administrators can inspect the
existing workout/bodyweight projection without media or internal document metadata.
The list includes real subscription and ephemeral live-workout presence.
Password/email/reset availability is disclosed only with `PASSWORD_LOGIN=1`.
Disabling any administrator is refused. Disabling another profile immediately denies
its sessions and removes pending device links; re-enabling retains Node's session
version behavior. Pull-only profiles update last-sync at most every ten minutes;
failed timestamp bookkeeping does not fail a successful Training read.

`POST /api/v1/admin/user/delete` requires `p004_deletion_tasks`. It refuses
self-deletion and deletion of the last administrator, disconnects personally bound
Coach credentials, cascades operational SQL data and records pending external
cleanup in one transaction. Consumed invitations and historical audit are not
deleted. Access ends at SQL commit, including late Coach results. The compatible
response remains `{ok:true,id}`; it does not certify external cleanup. Media and
secret cleanup runs afterward under `p004_external_cleanup`. The single worker
persists each attempt before unlinking, schedules the first attempt after one
second and subsequent attempts after 5/15/60/300 seconds, and stops after five
attempts per cycle. The final stored deadline never authorizes a sixth attempt. Failure retains `retry` and a safe
`media`/`secret`/`internal` code; it never restores account access. A missing file
is already clean. Symlinks, unexpected nested media paths, noncanonical owner IDs,
live owner/path collisions and still-referenced Coach keys stay pending rather than
risk another profile's bytes. Unknown/protected imported secret references require
operator review; they are not guessed or traversed. Completed tasks retain `done`
metadata for verification.

Apply `p004_admin_invites` for `GET /api/v1/admin/invites` and
`POST /api/v1/admin/invites/new` / `revoke`. Active administrators can create
64-bit uppercase hexadecimal codes, with notes limited to 60 UTF-16 units, and
revoke unused codes. Existing legacy codes retain exact matching without a new
length rule. Consumed history stays burned after the profile or issuer is deleted;
the deleted profile's resolved display name becomes null. Runtime receives no
direct invitation-table access. PostgreSQL-unrepresentable NUL/isolated surrogates
are rejected without silent replacement.

With `PASSWORD_LOGIN=1`, `POST /api/v1/admin/user/password-reset` returns a new
one-use 24-hour code once to the authorized administrator. It refuses every admin
target, removes the old password, reserves the normalized login name, replaces the
stored digest, revokes sessions/device links and clears live presence/timers.
Email, passkeys and disabled status are retained. A conflicting active alias
returns 409 without changes; SQL failure rolls the whole operation back. The route
is absent while password sign-in is disabled. No email delivery is added.

Apply `p004_audit` for `GET /api/v1/admin/audit` and
`POST /api/v1/admin/audit/clear`. Both revalidate the current administrator,
including after lock waits. The existing Admin activity card reads newest-first
ID pages (`limit`, `before`, `cat=auth|admin|fail`); clear deletes rows, not the
identity sequence, and then attempts an `admin.audit.clear` event separately.
Historical actor/target IDs and names have no account FK or deletion cascade.
There is no new export or public diagnostic endpoint.

Audit defaults to enabled, 5000 events, 90 days, IP off. `AUDIT_LOG=0` disables
new events, not authorized history access or clear. `AUDIT_MAX` and `AUDIT_DAYS`
apply both limits on append and read; zero disables that limit. Expired rows are
never served, including after an idle restart. Physical pruning happens with
those operations, not through a new scheduler. `AUDIT_IP=net` stores /24 IPv4 or
/48 IPv6; `full` stores validated addresses. As with Node, proxy address headers
require a proxy that overwrites untrusted values. No user-agent or failed passkey
ID is stored.

| Event producers | Recorded context |
| --- | --- |
| Password/passkey signup and login, reset consumption, pairing/device links | Success/failure and verified identity where available; no submitted identifier, code, password or credential. Anonymous passkey/signup/pair failures are capped at ten per address/event/minute and 120 per event globally. |
| Own password/email/passkey changes, proof failures and logout/all | Verified owner, action and safe reason/proof labels; first password/email setup remains distinct from change. Plain logout clears cookies without revoking other sessions. |
| First administrator, admin denial, enable/disable/delete, invite create/revoke and reset issuance | Administrative actor and applicable target; deleted display name remains historical. Invitation/reset codes and notes are not copied into new audit events. |
| Media sweep and upload/sweep throttling | Owner and bounded file-count/kind summary; no paths, hashes or Training content. |

Business transactions finish before audit starts its own transaction. Append is
best effort with no retry queue or delivery guarantee: failure leaves the business
response/cookie and committed data unchanged. A safe `AUDIT_WRITE_FAILED` warning
is emitted once per degraded interval; the process-local `Audit.degraded` and
`Audit.failures` state remains available even if the logging sink fails. A later
successful append clears the degraded flag without replaying lost events.
Operational status/diagnose wiring remains S9, not proof delivered by this slice.

The private operator command uses the existing runtime environment and credential
file, not an HTTP session, privileged database login or a new public endpoint.
Inside the configured API container, run:

```sh
python -m opengym_platform.administration.cleanup status
python -m opengym_platform.administration.cleanup status <task-uuid>
python -m opengym_platform.administration.cleanup retry <task-uuid>
python -m opengym_platform.administration.cleanup run <task-uuid>
```

Use your existing isolated Compose configuration with `exec api` (or a one-off
`run --rm --no-deps api -m ...` using its Python entrypoint when API is stopped).
Do not mount original protected material to resolve a pending task. `status` lists
at most 500 tasks, incomplete first, without secret references or content; exact-ID
lookup remains available. `retry` resets only an exhausted task for one new bounded
cycle after the operator fixes the cause. `run` performs at most one due attempt
of that exact task; it exits 1 while incomplete, 0 when done. Repeated run/retry
cannot reopen done work. A crash or cancellation consumes the committed attempt;
restart respects its deadline and budget. A failed final SQL acknowledgment may
leave retry after successful unlinks; missing-file idempotency resolves the next
attempt. No automatic schema migration or external provider call is involved.

Prod uses `PLATFORM_WEB_DIGEST`, `PLATFORM_RUNTIME_DIGEST`,
`PLATFORM_MIGRATE_DIGEST`, `PLATFORM_OPS_DIGEST` and `PLATFORM_DIAGNOSTICS_DIGEST`: the hex suffix of tested local
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
per-account lockout. Administrative issuance and audit routes are described above.
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
The synthetic browser proof covers reconciliation against Python; it does not
establish readiness to cut over an existing instance.

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
These route checks do not establish real-instance cutover readiness.

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
by `node scripts/build-coach-assets.mjs`. Runtime-neutral JavaScript and editable
prompts live in `shared/coach-core/`; host tests and the local phone Coach import that
same tree. Generated Python assets are data, not a second editable source.
`node scripts/build-coach-library.mjs --check` remains a supported alias.

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
own slices. Uvicorn access logging is disabled; private diagnostics are described below.

## HTTP API v1

The Python Compose stack includes private diagnostics. Set
`PLATFORM_DIAGNOSTIC_SOCKET` to an unused Unix socket path in a private writable
directory to enable live operator status (mode 0600). A JSON operator config with
only `diagnostic_socket` selects it for
`python -m opengym_platform.operations diagnose --config <operator.json>`.
The command reports DB/schema, pool and audit/logging degradation; missing verified
backup evidence remains degraded. No public HTTP diagnostic route is added.
`PLATFORM_LOG_SOCKET` selects the private local datagram syslog receiver. Logging
uses fixed fields and route templates, excludes request content and never waits
on a full socket. Transport failures remain visible until restart; a successful
send reports delivery as unconfirmed. Compose includes the pinned private
rsyslog/logrotate collector; its transport and limits are documented in
[platform observability](../docs/reference/platform-observability.md).

Each HTTP request generates an internal random `request_id` shared by pool/query/
transaction records and Coach provider calls, including asynchronous jobs after
HTTP 202. Incoming trace headers are ignored and no diagnostic header is returned
or forwarded. Fixed outcome codes and monotonic durations exclude SQL, URLs,
credentials and provider content. In the private collector shell, run `rotate`
before `grep -hF '<hex32>' /logs/api.log*` to follow an operation within retention.
Verify with `node scripts/platform.mjs verify diagnostics --case correlation`.
Use `node scripts/platform.mjs verify diagnostics --case retention_and_failure`
for persistent retention/restart, stopped-API sweeps, full/stopped sinks and privacy
across real nginx/API/PostgreSQL and Docker logging. The disposable supervisor's
clock is advanced only in the test; host clocks and the personal instance are untouched.
Disk exhaustion can leave incomplete log records; delivery remains best effort.

All Python HTTP routes use `/api/v1`, including the internal probes
`GET /api/v1/health/live` and `GET /api/v1/health/ready`.
Unversioned routes are removed; there are no aliases or redirects.
Nginx blocks the two internal probes while forwarding the public API.
Swagger, ReDoc and the HTTP OpenAPI endpoint remain disabled.

The hand-maintained public authority is `backend/openapi.yaml`. Regenerate the
static reference with `node scripts/build-api-docs.mjs`; `--check` rejects drift.
`node scripts/platform.mjs verify contracts --case python_routes` compares all
public methods/paths and unauthenticated HTTP response status/JSON/cache headers
against that YAML, with password sign-in and media enabled. Authenticated behavior
is covered by the capability suites; the router comparison alone does not prove
every response schema. Internal probes are excluded. The frozen Node YAML and
transition comparator are retired; the independently maintained public YAML is the authority.

Frontend builds select their HTTP contract with `VITE_API_PREFIX`:
`/api/v1` is the default for web/mobile/development; explicit `/api` remains selectable
for clients paired with an older frozen release. The Python Dev overlay also sets this argument. For a permanent Python web image, build from
the repository root before selecting its tested image ID:

```sh
docker build -f web/Dockerfile --build-arg VITE_API_PREFIX=/api/v1 -t opengym-platform-web:v1 .
```

The value is compiled into the frontend; a runtime environment variable cannot
change an existing image. A Python frontend build does not fall back to Node
paths or deliver capabilities that have not yet been ported.

## Current verification

Forward repair of a surviving destination uses the existing private host maintenance
configuration, plus `repair.witness_file` with independent acknowledged Training/media
receipts. Run `node scripts/platform.mjs operate forward-repair --config <absolute-host-json>
--incident <id> --release sha256:<tested-local-image-id>`. The wrapper captures current
SQL/files, verifies receipts and the exact schema, replaces only the API image,
persists its digest overlay in that host configuration and requires readiness.
Failed preservation or incompatibility holds maintenance for operator review.
This repairs a bad API image, rolled-back transactional migration or uncertain reply;
it executes no corrective DDL and restores no old data. See the exact witness contract
and limits in [Q2 operations](../docs/reference/platform-operations.md#reparación-hacia-adelante-q2).

`just test <suite>` and `just test-case <suite> <case>` delegate to the same verifier
used by CI. Unknown/unimplemented cases fail with exit 2; missing prerequisites,
empty/skipped/failed proofs and cleanup failures never count as success.

| Suite | Proof |
| --- | --- |
| `harness` | Ownership, contamination rejection and protected sentinels. |
| `contracts` | Public Python routes checked against the canonical `backend/openapi.yaml`. |
| `database` | Pool, cancellation, rollback, owner isolation and commit uncertainty. |
| `schema` | Current Alembic history, locking and restricted roles. |
| `repair --case acknowledged_writes` | Independent W1/W2/media, surviving destination after image/DDL/lost-reply faults, W3 after repair and no-go on missing content, bytes or incompatible release. |
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
| `notifications --case device_isolation` | HTTP activity/test/rest/cancel, owner/device isolation and legacy fallback, replacement/revocation, ephemeral presence/hidden grace, nudge suppression and restart without timer recovery. |
| `notifications --case local_dates` | Internal scheduler, local/DST dates, queue/pins and nudge back-off; concurrent revocation, date claims, private TLS transport/SSRF, independent encryption vectors and safe pruning. |
| `admin_delete --case atomic_delete` | Atomic SQL cascades, Coach disconnection and pending external references, access denial, safeguards, rollback/retry, concurrent revocation/deletion and restricted upgrade/ACLs. |
| `admin_delete --case external_retry` | Real HTTP deletion followed by owner-only external cleanup, safe failure/backoff, restart/cancellation, private operator status/retry and preserved foreign sentinels. |
| `admin_audit --case failure_and_retention` | Restricted admin read/clear, age/count retention, ID cursor/sequence, IP policy, anonymous failure caps, postcommit SQL failure isolation and upgrade/ACLs. |
| `admin_invites --case consumed_history` | Current admin authority, preserved consumed history, create/revoke guards, atomic reset/reissue, alias conflicts, rollback and restricted upgrade/ACLs. |
| `admin_users --case actor_target` | Active admin/target separation, bounded Training projections, subscription presence, disable safeguards, ordered revocation, rollback, pull timestamps and restricted migration/ACLs. |
| `shared_client --case canonical_sources` | Single shared JS/prompt source, generated assets, plain Node loading, HTTP pipeline and local phone Coach parity. Formats/bundle acceptance and OpenAPI relocation remain separate. |
| `shared_client --case formats_and_bundles` | CSV/JSON/media backup/FIT hostile cases, catalogue/ID continuity, web Node/Python and mobile Python bundles, shared-source graph and byte-for-byte Android/iOS asset copies. |
| `checks` | Frozen dependencies, lint, format and types inside the test image. |

The verifier uses `backend/empty.env`, unique `opengym-platform-test-<hex16>`
projects and `org.opengym.platform=synthetic` labels. It exposes no ports or personal
mounts and cleans up only owned resources. After confirming an interrupted run ended:

`node scripts/platform.mjs cleanup <exact-printed-project>`

No global prune, volume wipe or removal of foreign/shared images is part of cleanup.

### Client formats and bundles

Run `node scripts/platform.mjs verify shared_client --case formats_and_bundles`.
The pinned contracts image runs the existing format cases and builds in a disposable
workspace, leaving host `dist/` and native projects untouched. Source maps check
that each bundle includes `shared/coach-core/` without Node API sources. The mobile
build stages the repository's exercise media and uses Capacitor `copy` for both
Android and iOS, checking all copied bytes. Its isolated tmpfs is capped at 1 GiB
to hold the bundle and both media copies. This is portable bundle/copy evidence,
not `cap sync`, Gradle/CocoaPods compilation, signing, device execution or publication.

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
bundle; this does not verify nginx deployment. Screenshots for fourteen cases (including Admin invitation create/revoke, reset
issuance and audit filtering/clear with independent SQL observation and reload) and a sanitized
result are copied to an exclusive system temporary directory printed by the runner before owned
containers are removed. Browser state, passwords and SQL documents are not exported.

Cold/warm/source/manifest cache and lockfile regressions live in
`scripts/platform-build.test.mjs`. Contract ownership and retention are described below.

`node scripts/platform.mjs verify images --case reproducibility` runs the existing
target, cache and HTTP lifecycle proofs from a clean detached HEAD worktree.
It verifies the committed runtime, excluding uncommitted changes; commit nothing
just to run it. Evidence and the tested revision remain in an exclusive system
temporary directory printed by the runner; the owned worktree/builders/images are removed.
Consolidate necessary results in the owning OpenSpec and discard obsolete temporary evidence.
Cold builds use isolated caches and can take several minutes. CI uses this case
instead of repeating the cache matrix separately. Retention tooling remains a
prerequisite of diagnostic tasks 9.2–9.4, not image verification.

### Native compatibility coverage

The transition `contracts/` dumps, comparator, source-hash manifest and generators
are retired. `tests/platform/identity_vectors.py` pins small independent HMAC/scrypt/
normalization answers. `webauthn_vectors.py` expands signed public WebAuthn transcripts
from `fixtures/webauthn.json` (no private keys). `test_training_stamps.py` expresses
stamping/legacy-write regressions directly; HTTP/PG lineage stays in its native suite.
Expectations must not be regenerated from the Python code under test.

The pure coach/client suites live in `frontend/src/lib/coach-core/`; run them with
Vitest. `node scripts/platform.mjs verify contracts --case python_routes` checks
the current public API. The former `--case baseline` is deliberately rejected.
[Compatibility reference](CONTRACTS.md) owns the current coverage map.

Build contexts are allowlisted: root `.dockerignore` serves web and
`backend/.dockerignore` serves Python. Client/security/browser Dockerfiles have
matching ignore files overriding the root filter. Keep each allowlist aligned with
its `COPY` inputs; catalogue media and shared coach source remain required web inputs.
Git ignores do not filter Docker contexts. Host dependencies, credentials, env files
and caches stay out; frozen pnpm installs use builder-local cache mounts.

## Isolated legacy import

The `ops` image includes `python -m opengym_platform.operations import --config
/run/import/operator.json --source /run/import/source --target new-a`. It requires
a frozen read-only Node data source and a separately provisioned empty PostgreSQL
target, explicitly marked for that ID and denied runtime CONNECT. It does not
bootstrap/migrate the database or start/promote an application.

Full internal Training state, identity, subscriptions, Coach state, audit and
external media/HTTP secrets are compared before completion. Unsupported data
blocks with a private report; nothing is silently dropped or normalized. Deferred
Claude/Codex credentials remain in the protected origin. See the
[preconditions, configuration and capability matrix](../docs/reference/platform-operations.md#importación-aislada-de-origen-node),
including known blocking differences in legacy Coach logs/current jobs.

```sh
node scripts/platform.mjs verify import --case faithful_or_blocked
```

This verification uses disposable PostgreSQL, actual operator commands, read-only
synthetic source files and HTTP after explicit test-only opening of that target.
It proves no real-data cutover, backup or reviewed restore access.

## Coordinated SQL capture

The host wrapper `node scripts/platform.mjs operate backup --config <absolute-host-config>
--reason scheduled|startup|pre-migration` stops the selected writers, keeps PostgreSQL
available and runs the ops-only SQL/files capture with an explicitly provisioned restricted
backup role. See [preparation, private configurations and limits](../docs/reference/platform-operations.md#captura-sql-entregada)
and the optional `deploy/docker-compose.maintenance.yml` overlay before use.

Without the optional host `bundle` configuration, a captured dump is **not a verified backup**: the wrapper reports
`BACKUP_CAPTURED_UNVERIFIED`, `verified: false`, exit 1. The protected staging set
includes data/media/GC/Coach/VAPID, actual runtime secrets and selected host/Compose
configuration, with a private SHA-256 inventory. It rejects unsafe files, source
changes and external containers sharing writable capture resources. The operator
must control Docker and host sources throughout the pause; stability checks do not
freeze arbitrary host writers. Scheduling and reviewed-access/full-recovery delivery
remain separate; isolated data restore is described below. Failures retain the private journal/lock; pre-migration capture does not
reopen traffic. Never remove an unresolved lock or edit startup admission blindly.

With `bundle.destination`, `bundle.identity_file` and an X25519 `bundle.recipient`,
the same host command publishes an age 1.3.2 encrypted USTAR bundle outside the writer
pause. See [bundle preparation and limits](../docs/reference/platform-operations.md#bundle-cifrado-entregado).
The official asset/digest/license are pinned in `versions.json`; age binaries exist
only in ops/test, never API/dev/migrate or host installs. **Do not declare the age
identity as a Compose secret/config**: selected files are capture inputs. The wrapper
mounts the separate identity RO only for encryption/verification, outside capture.

Ops takes the shared session mutex without holding a transaction over file IO,
streams ciphertext to protected staging and the destination `.partial`, fsyncs and
rereads/decrypts the destination to authenticated EOF with manifest/checksum and
ciphertext identity checks before atomic publication. `BACKUP_VERIFIED`/exit 0 credits
an intact bundle, not a complete restore or Q1/RPO/RTO acceptance. Wrong key, corruption,
ENOSPC or interruption preserves the prior valid point; named bundle processes also
participate in explicit recovery. Pre-migration remains held pending coordination.
Staging/partials remain protected with cleanup pending; no retention job or automatic
capture deletion is added. Physical independent-disk/encrypted-volume acceptance
remains an operator prerequisite, not synthetic proof.

The maintenance overlay also gives API a separate read-only `gate/` directory, not
staging or backup credentials. Provision its initial admission explicitly **only
for a new instance without pending maintenance**, as described in the operation
reference. Missing/invalid/foreign/blocked admission prevents application startup
before DB/background writers. The directory stays fixed; the wrapper atomically
updates its admission marker and last verified backup receipt. Private diagnose reads
snapshot age from that receipt (not a live disk availability/crypto probe), rejecting
invalid/foreign evidence. No leases, control listener or startup backup is added.

`node scripts/platform.mjs operate maintenance-recover --config <absolute-host-config>
--operation <journal-hex32-id>` explicitly takes ownership after proving the old
controller ended (OS creation identity, not PID/TTL alone). It stops only recorded
ops capture/check/bundle containers, waits for their Docker client, verifies original
writers/DB/images and compatible schema, then starts only previously running IDs.
API must become ready; failed restart closes admission and stops writers again.
Success is `MAINTENANCE_RECOVERED`, exit 0: service recovery, not a new backup
verification. It does not discard or advance an existing verified backup receipt.
Interrupted recovery can itself be recovered; live/concurrent controllers block.
Unknown ownership/missing process proof or uncertain capture creation stays blocked
for operator investigation. Older journals without controller proof are not guessed.
Pre-migration recovery stays `MAINTENANCE_MIGRATION_HELD`/exit 1 without DDL or restart.

```sh
node scripts/platform.mjs verify backup --case verified_bundle
node scripts/platform.mjs verify backup --case writer_shutdown
node scripts/platform.mjs verify backup --case sql_files_coherence
node scripts/platform.mjs verify backup --case interrupted_capture
node scripts/platform.mjs verify training_browser
```

The capture/recovery cases reuse the existing integration proof; `verified_bundle`
uses its shared setup in a separate test to avoid repeating the longer encryption
matrix for each older case. It adds independent age/tar/SQL/file readback, identity
exclusion, authenticated EOF, unsafe/corrupt archive and post-verification mutation,
real bounded ENOSPC, mutex/wrong key, private status and interruption before unlock.
The capture proof includes actual shutdown, independent SQL
readback and exact file bytes/checksums, plus early/late external writers, host-file
mutation and real wrapper/recovery death, startup admission and failed restart.
They preserve initially stopped services and unrelated sentinels, without restarting
the real host/daemon or proving physical power-loss recovery. The browser command separately checks client offline/dirty/active and
media-queue persistence.
These are synthetic regression proofs, not a complete restore or real-client rehearsal.

## Isolated data restore

`python -m opengym_platform.operations restore --config <private-json>
--bundle <hex32> --target <new-id>` consumes the verified age v1 format in ops only.
Use the standalone `deploy/docker-compose.restore.yml`, **never the active instance's
project/volumes or combined overlays**. It has no API/web/jobs/ports and only an internal
network. [Preparation, credentials and exact commands](../docs/reference/platform-operations.md#restore-de-datos-entregado-cuarentena)
are prerequisites: new private target, fresh role passwords, trusted bootstrap/migrations,
explicit DB ownership comment, exact table catalog with no foreign tables in other
schemas either, runtime CONNECT revoked and no other DB peers. Truncation never
cascades into foreign data.

Restore takes the existing PG session mutex, authenticates before extraction, applies
the standard tar data filter with strict USTAR/entry/path limits, checks capture
inventory and rereads extracted files before SQL load. It restores **data and sequence
state**, not old-cluster DDL/ownership/ACL/passwords, into the trusted migrated schema.
Old configuration/runtime secrets remain private quarantine inputs, not active config.

Success is `RESTORE_QUARANTINED`/exit 0, never traffic-ready. SQL/data/secret/config
copies, private journal/result and a blocked startup gate remain under the new root;
runtime still cannot connect. The separate ops-only `restore-access-recover` command
now provides a locally authorized **new password path**, private delivery files,
new session signing with original Coach decryption material, and link/reset/job
invalidation. [Review schema, exact command and limits](../docs/reference/platform-operations.md#recuperación-local-de-acceso-entregada)
are mandatory. It does not enable historical credentials or open traffic; browser
reconciliation is separately covered by the synthetic `training_browser` suite. Never clear a
partial target to retry; preserve uncertainty and choose a fresh isolated instance.
The command does not clean, schedule or prove physical encrypted storage/full RPO/RTO.

```sh
node scripts/platform.mjs verify restore --case isolated_target
node scripts/platform.mjs verify restore --case reviewed_access
node scripts/platform.mjs verify restore --case full_timing
```

This runs the actual standalone template against a real 10.3 synthetic bundle and a
separate PG cluster. Independent all-table/file comparison, nontrivial sequences,
owner/grants/FORCE RLS and real runtime A/B prove the data copy. Wrong keys, missing
secrets, corruption including after extraction, unsafe archives, incompatible metadata,
foreign/exposed/nonempty/busy targets, mutex, real ENOSPC and killed age remain blocked.
The API admission probe receives only gate RO and no bootstrap; source API/data and
bundle stay unchanged. `isolated_target` alone is not reviewed access or a complete recovery rehearsal.

`node scripts/platform.mjs operate restore-rehearse --config <absolute-private-json>`
coordinates a monthly isolated rehearsal from the host. Use the
[rehearsal configuration and evidence contract](../docs/reference/platform-operations.md#ensayo-mensual-entregado-y-medición-completa).
It records the declared incident through review, private runtime checks, client
evidence/independent PG readback and CONNECT closure. Missing review or client proof,
unknown access and uncertain completion cannot credit full RTO. Objective failure is
not a successful recovery. The normal target gate stays blocked; no scheduler or
real-instance acceptance is installed or implied. `full_timing` exercises this CLI,
real HTTP/PG and the compiled frontend on synthetic data, not real identities/clients.

## Pre-cutover evidence inspection

`node scripts/platform.mjs verify gates --case pre_cutover` exercises synthetic
validator fixtures only, without Docker or instance access. With
`--evidence <sanitized-index.json>`, it checks the selected index and checksummed
files under its fixed sibling `artifacts/` directory. See the
[v1 format, coverage, limits and exit codes](../openspec/changes/archive/2026-11-04-port-compatible-platform/design.md#delivered-pre-cutover-evidence-validator-synthetic-preparation).
The index requires a complete release manifest, original proof provenance and
recovery chronology including the Node data cutoff, rather than only a recent
Python snapshot. Recorded commands are never executed. Success establishes structural validity;
human review and actual operational permission remain required. Delivery status
is recorded only in the [active tasks](../openspec/changes/archive/2026-11-04-port-compatible-platform/tasks.md).

`node scripts/platform.mjs verify gates --case authorized_cutover` runs synthetic
inspector fixtures. With `--evidence <sanitized-index.json>`, it checks the recorded
cutover authorization/window, candidate binding, single authority, protected
originals and rollback-before-writes or forward-repair evidence, reusing all
pre-cutover checks. See the [execution-package format](../openspec/changes/archive/2026-11-04-port-compatible-platform/design.md#delivered-authorized-cutover-evidence-validator).
It never runs a cutover, authenticates permission or declares operational acceptance;
manual review remains required and `cutoverAuthorized`/`realGateCompleted` stay false.

`node scripts/platform.mjs verify gates --case node_capture` rehearses the
Node drain and stopped-source capture in the existing locked client test image, on its
internal network and temporary synthetic files only. It checks acknowledged HTTP
writes/media through disposable protocol fixtures, drain proof, timeout refusal,
writer shutdown, hashes and failure quarantine. Original Node HTTP/Coach runtime
results remain historical evidence; this command does not run the retired API.
Host verification with actual isolated Docker containers uses
`node --test scripts/platform-node-drain-docker.test.mjs`; discovery is restricted
to the synthetic project and no real instance is inspected or operated. See the
[procedure and limits](../openspec/changes/archive/2026-11-04-port-compatible-platform/design.md#procedimiento-ensayado-de-captura-node-detenida).
There is no operational stop/start command or implicit access to instance paths.

`node scripts/platform.mjs verify gates --case node_capture_import` adds a fresh
PostgreSQL target and the existing importer to that rehearsal. The receiver mounts
the owned capture volume read-only and verifies SQL/files independently, rejected
unrepresentable input and occupied targets, and runtime CONNECT still denied. No
Python API is started or target promoted. See the
[integrated procedure](../openspec/changes/archive/2026-11-04-port-compatible-platform/design.md#ensayo-integrado-captura-node--importación-postgresql).

`node scripts/platform.mjs verify gates --case node_capture_recovery` extends the
fixture chain through the existing host backup wrapper, verified age encryption
and a restore in a separate private cluster. It retains the Node data cutoff and
checks SQL/files/roles plus the existing corruption/interruption negatives. Runtime
access exists only temporarily for fixture checks; the restored target ends closed
and quarantined. See the [scope and limits](../openspec/changes/archive/2026-11-04-port-compatible-platform/design.md#ensayo-integrado-hasta-backup-cifrado-y-restore-aislado).

## Retired transition tooling

Standalone Node/Python Foundation stacks, runners and their exclusive prototype
implementations are retired. Pool coverage is retained under the current verifier;
Current platform tests, native independent vectors, client tests and image/cache
checks remain active. The Node API and `backend/contracts/` transition artifacts
are retired; no current verifier requires that source tree.
[Node Foundation evidence](../openspec/changes/archive/2026-10-22-add-postgres-foundation/design.md)
and [Python Foundation evidence](../openspec/changes/archive/2026-10-25-add-python-platform-foundation/design.md)
remain historical records, not commands that still exist or proof of current recovery.

The old synthetic migration/recovery prototypes are not the current platform schema
or an operational restore. Current backup/restore and security tooling has its own
synthetic evidence in the [active port tasks](../openspec/changes/archive/2026-11-04-port-compatible-platform/tasks.md).
The [consolidated repository review](../docs/reference/platform-operations.md#evidencia-de-aceptación-y-límites-de-esta-revisión)
records evidence and limits; real cutover remains deferred and Recovery requires
separate authorization after repository acceptance.
The cleanup does not change application authority, user data or deployment acceptance.
