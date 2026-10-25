# Executable delivery plan

## Status and authority

Documentation-only preparation. No product implementation, migrations, runtime
experiments or operational actions were performed by writing this plan. All tasks
remain unchecked in [tasks](tasks.md), the only progress ledger. Q1–Q3 and Q6 remain
binding; Q4/Q5 are concluded diagnostic evidence, not delivery acceptance.

This plan closes technical preparation, not GP/GO/G3 or permission to cut over.
Physical backup location, real-client inventory, measured times and operational
credentials are inputs to later acceptance tasks, not facts supplied by this plan.
If an environment cannot satisfy the specified gates, stop rather than weaken them.

Authoritative detail: [DDL](../../../docs/reference/platform-schema.md#especificación-ddl-y-evolución),
[SQL functions/roles](../../../docs/reference/platform-security.md#catálogo-sql-y-contexto-transaccional),
[diagnostics](../../../docs/reference/platform-observability.md#configuración-cerrada-y-límites-iniciales),
[recovery](../../../docs/reference/platform-operations.md#procedimientos-operativos-especificados).
Do not duplicate editable SQL schemas or operating procedures here.

## Commands and safety contract

**Existing checks**, executable now without delivering product code:

```sh
openspec validate port-compatible-platform --strict --no-interactive
node scripts/docs/okf.mjs check
node --test scripts/docs/okf.test.mjs
git -c core.safecrlf=false diff --check
```

**Future delivery command**, to be implemented by task 1.2, not available now:

```sh
node scripts/platform.mjs verify <suite> --case <case>
node scripts/platform.mjs verify <suite>
```

Every runtime task below names a suite/case; task 1.1 uses the existing Foundation
contracts command before the new runner exists. The full suite runs all its cases; omission,
unknown case, skipped test or missing prerequisite is a failure, never a green
placeholder. Before implementation, run the named proof against the initial or
preceding revision: it must fail for the stated missing behavior, not for a broken
runner, absent dependency or unstarted DB. Then implement and rerun that case and
full affected suite before checkpoint. Do not gather all REDs before implementation.
For migration/infra tasks the proof is a real rejected/failed configuration or
schema operation; for final acceptance it is independent evidence inspection,
not an artificial runtime RED.

A suite/case manifest must map each case to requirement/scenario, setup, command,
expected proof and checkpoint; absent/empty mapping or silent skip blocks the runner.
Runner requirements: same ownership guards as Foundation, unique synthetic Compose
project/labels, disposable PG and tmp volumes, no user environment/config inheritance,
no real secrets, no published DB/API, no network to real providers, no privileged
containers/socket/capability overrides and no global cleanup. Fault controls use
owned resources only. Build installs pinned dependencies in test images, never at
runtime or on the host. Use a local fake transport on a private test network; a
fixture subprocess is unnecessary. Verification exits 0 pass, 1 assertion/gate
failure, 2 invalid invocation/prerequisite. Report revision, image digest, platform,
case IDs, counts (including skips), fault/clock/seed, results and sanitized evidence
path; never raw HTTP credentials, SQL values, user payloads or private config paths.

Python suites live in `backend/tests/platform/test_<suite>.py`, through real Python
HTTP + disposable PostgreSQL using api_runtime; privileged setup/independent observer
is separate. Pure vectors live under `backend/contracts/` and test domain helpers.
Browser suites live in `frontend/e2e/platform/`, driving the preserved frontend
against Python, not mocked API. Task 1.2 delivers this explicit mapping and test
image/browser pins; no host browser/dependency installation is implied. Operational
suites run the actual `ops` commands against synthetic projects, not mock-only CLI.

**Future operating prefix O**, a textual abbreviation, not a shell function or
installed binary (replace only the explicit operator.env placeholder):

```sh
docker compose --env-file <absolute-operator.env> -p opengym-ops -f compose.platform.yml -f compose.platform.ops.yml run --rm ops
```

Append one command below; ops image entrypoint is
`python -m opengym_platform.operations`. Operator env contains only non-secret
configuration/file refs; `/run/operator/config.json` is mounted read-only. Secrets
are distinct restricted file mounts. A Node host is required for the synthetic
verification runner, not for operating the delivered stack. Commands are contracts
of task delivery, not permission to create operator.env or run them now.

| Future command appended to O | Preconditions and result |
| --- | --- |
| `preflight --config /run/operator/config.json` | Validate instance ownership, paths/devices, tools, digests, keys and isolation; no mutation. 0 valid, 1 blocked, 2 usage/config error. |
| `migrate --config /run/operator/config.json` | Pre-migration verified backup for populated instance, exclusive lock, explicit known head; nonzero prevents ready/up. |
| `import --config /run/operator/config.json --source /run/import/source --target <new-id>` | Frozen read-only source; new owned target only, prevalidate then import/compare. Nonzero leaves target unexposed, never edits source. |
| `backup --config /run/operator/config.json --reason scheduled` | Private maintenance control, exclusive lock, coherent capture and verified encrypted destination; only exit 0 advances recovery-point state. reason also accepts startup/pre-migration. |
| `restore --config /run/operator/config.json --bundle <id> --target <new-id>` | New isolated target, full verification and blocked restored access; not permission to open traffic. |
| `restore-review --config /run/operator/config.json --target <id> --review /run/review/review.json` | Protected Q1 evidence and explicit per-credential decision; reject missing coverage, no new security ledger. |
| `restore-rehearse --config /run/operator/config.json --bundle <id> --target <new-id> --review /run/review/review.json` | Full isolated monthly sequence, timed including review; reports objective pass/fail and unresolved access, no automatic production promotion. |
| `forward-repair --config /run/operator/config.json --incident <id> --release <compatible-digest>` | Surviving destination and independently verified acknowledged writes; nonzero keeps maintenance/no-go. |
| `maintenance-recover --config /run/operator/config.json --operation <id>` | Confirm owned interrupted capture, mutex free and subprocesses stopped before releasing fail-closed marker. |
| `diagnose --config /run/operator/config.json` | Private redacted status; optional `--trace <hex32>`; exit 1 degraded and 2 invalid config/usage. |
| `diagnostics-retain --config /run/operator/config.json` | Exact owned diagnostic volume only; age/space cleanup even when API is stopped, no business backups touched. |

`<id>` is a validated opaque identifier resolved under configured roots, not an
arbitrary shell/path. No shell interpolation, arbitrary subprocess arguments or
implicit current `.env`. Synthetic verify supplies all config/keys and simulates
operator reviews. Real ops and scheduler installation need separate authorization.

Gate evidence commands additionally require `--evidence <protected-index.json>`.
Without it they test only synthetic validator fixtures and cannot complete a real
gate task. The explicit index identifies gate/EV, revision/digest/platform, commands,
results, scope/limitations, artifact checksums and human review/authorization refs.
Only read the selected sanitized index and its allowlisted owned artifact root;
never follow config/data paths or contact an instance. Missing artifacts, skips,
digest mismatch or absent actual authorization are no-go. Structural completeness
is not proof of authenticity or human acceptance; final review remains manual.

## Slice contracts and first proofs

Paths below are future module roots under `backend/src/opengym_platform/` unless
explicitly frontend/shared. No empty modules/tables are created in advance. Services
own transactions; collaborators receive the same handle. External network/filesystem
work occurs outside SQL transactions, under the operation/write-gate discipline.
All protected routes test unauthenticated, own A, foreign B and admin as applicable;
body/query/header owner forgery never establishes identity. Expected HTTP bodies,
status, cookies and headers come from the independent Node baseline/OpenAPI, not
FastAPI defaults. Missing route coverage blocks parity.

### S1 — boot, guards and controlled schema (tasks 1.*)

- Scope: `core/`, application factory, platform Compose dev/ops and test/ops images;
  reuse Foundation Database semantics without weakening its synthetic config guards.
  New application settings are separate. Existing Foundation evidence stays archived.
- Initial proofs: runner rejects foreign labels/config; public health/config responds
  with compatible fields, internal readiness refuses unknown head; migration failure
  leaves no advanced history. A second migrator cannot enter the lock.
- Data/actors: bootstrap only for setup; schema_owner/migrator/runtime/executors/backup
  roles from security reference. Start p001 when identity consumes it, not all DDL.
- Checkpoint: owned dev HTTP stack and repeatable test mapping; ops combination has
  no host sources/dependency binds, no root API, Node/SDK/CLI or coach seccomp override.

### S2 — identity operations (tasks 2.*)

- Scope: `identity/`, `audit/` append and p001; Login, PasswordAuth, Passkeys, Settings,
  api/remote/store consumers. Pure HMAC/scrypt/Unicode/WebAuthn vectors precede HTTP.
- 2.1 selected cookie/bearer A reaches only A; invalid/duplicate/mixed credentials
  fail or resolve exactly as specified. Wait past expiry/revocation returns denied.
- 2.2 password login valid/invalid/NFKC and password-mode-off use compatible response
  and cookie/token; crypto outside TX, material/actor rechecked after waiting.
- 2.3 concurrent registration for one alias/invite admits one claim/consumption and
  exactly one first admin; email/name collisions and absent historical fields intact.
- 2.4 register/login passkey vectors include ES256/RS256/Ed25519, counter/UV/backup,
  wrong rp/origin/challenge/signature, replay and revoked-during-ceremony cases.
- 2.5 password/email own changes require proof; last-way-in and alias-expiry/Unicode
  concurrency prevent takeover, reset/password change preserves passkeys and revokes
  sessions/device links atomically.
- 2.6 add/rename/remove passkey is owner-only, cap 20/last-way-in enforced and late
  verification cannot attach after revocation.
- 2.7 reset is one-use/24 h, consumed with password/version/alias update; expired or
  duplicate redemption cannot commit. Admin issuance follows S6 privileges.
- 2.8 pairing/device-link are owner-bound/one-use, 10 min link, replacement and
  revocation work; no stale ceremony returns a session after account deletion.
- 2.9 pool max=1 across commit/rollback/error/timeout/cancel remains clean; real SQL
  assertions confirm FORCE RLS, no bypass, public EXECUTE or privileged SET ROLE.
- Run 2.1/2.2 first, then S3's Training pilot; registration/account/link operations
  and full identity regression 2.9 follow it. They are not prerequisites for proving
  Training with independently seeded synthetic accounts and real verified login.
- Checkpoint per task: named HTTP route family and negative cases pass; no assertion
  that a synthetic authenticator proves real hardware/native-device acceptance.

### S3 — Training pilot (tasks 3.*)

- Scope: `training/`, p002; GET/PUT `/api/data`, `/api/data/rev`, ServerSync/store.
  Owner lock exists even without document; update/stamps and response are one TX.
- 3.1 empty B sees state null/rev 0 while A reads its preserved document; generated
  projections reject fractional/string/out-of-range revisions without rounding.
- 3.2 concurrent first PUT produces compatible conflict, not overwrite; response
  rev+1 versus stored rev+2 and post-commit media-mark failure are preserved.
- 3.3 baseWid, lineage/reset/_unstamped/_prior and lost response retry preserve
  semantic state, including missing/null and safe-number boundaries.
- 3.4 browser holds active session/dirty edits through offline, 401, two 409s, lost
  reply and restore lineage. Verify persisted client storage and PG, not screenshot.
- Checkpoint: A/B HTTP→verified actor→RLS→commit and frontend reconciliation; Node
  fixtures or direct SQL alone cannot pass this slice.

### S4 — media (tasks 4.*)

- Scope: `media/`, Training reference interface; ProgressPhotos/CustomMediaField,
  uploads/GC outside SQL. No media table or second Training authority.
- Proofs: own upload/hash/download roundtrip; foreign resource 404, hash/type/body/
  quota rejection; missing references/DB outage/corrupt .gc.json never delete bytes;
  in-flight upload versus sweep and maintenance capture has independent sentinels.
- Checkpoint: byte hash/headers/ownership, pending client files and safe retry; SQL
  read error is not an empty reference list. Actor invalidated before finalization
  cannot publish a newly authorized resource through an old decision.

### S5 — coach local/HTTP and Q6 (tasks 5.*)

- Scope: `coach/`, p003, shared contract vectors; CoachSetup/CoachChat/AdminCoach.
  Settings/global operations use catalog functions; personal state uses owner RLS.
  Profile HTTP secret files remain external encrypted records, never Training.
- 5.1 imported claude/codex and old clients get 503/code off, no jobs/quota/refresh;
  settings/history remain identifiable, no brand remap or Node fallback.
- 5.2 concurrent enqueue near both caps atomically admits/counts one job per owner;
  two global executions, queued/running transition and restart without replay.
- 5.3 four HTTP transports use private fake endpoints and independent valid/invalid
  proposals; no-consent rejects before enqueue and malformed reply cannot apply data.
- 5.4 repeated ready/applied/dismissed/expired events preserve history; forget,
  consent withdrawal/deletion plus late result cannot resurrect content; daily quota
  retained only as contracted. Client still explicitly applies validated proposal.
- 5.5 admin config/models/test/connect/disconnect and profile account enforce actor,
  bound ownership, encryption errors and secret absence in responses/exports. Deferred
  connection/test routes stay visibly unavailable, including imported enabled=true.
- 5.6 cohort/scheduled work only reads explicitly consented candidates through public
  Training interface; opt-out and aggregates preserve current privacy contract.
  Candidate enumeration is an internal capability, never arbitrary HTTP owner input;
  recheck consent/account under each owner lock before reading/committing. Browser
  checks local coach survives shared-source move and Q6 copy covers every locale.
- Checkpoint: normal provider failure, timeout/cancel and unavailable-provider failure
  remain distinct; no new tools, memory, agent framework or speculative adapters.

### S6 — administration and audit (tasks 6.*)

- Scope: `administration/`, `audit/`, p004; Admin and existing admin routes. Actor and
  target stay separate, both locked deterministically; no admin may be disabled,
  self-deletion and last-admin deletion are denied. S7 subscription data precedes
  this slice because the existing admin list includes hasPush. Training collaboration
  preserves the existing workout/bodyweight drill-down without media references.
- Proofs: non-admin denied; stale/revoked admin cannot disable/read/delete B;
  delete disconnects personally bound coach credential + cascades + deletion_task in
  one SQL TX, then filesystem/secret cleanup can fail without restoring access.
- Retry command/internal worker uses exact deleted owner/task, bounded attempts (5
  automatic with backoff 1/5/15/60/300 s, then visible retry requiring operator); no
  generic queue. Missing bytes is idempotent success; unknown error retains task.
- Invitations consumed remain consumed after account deletion. Audit read/clear is
  admin-only, sequence retained; both age/count limits and IP-off default work.
  Failed audit append is observable after business commit, never converts success.
- Checkpoint: pending and completed external cleanup evidenced separately; no secrets
  reassigned, no history/invitation destroyed through an accidental FK cascade.

### S7 — notifications/activity (tasks 7.*)

- Scope: `notifications/`, p005; Settings/SW/device, `/api/push/*`, `/api/activity`.
  Global endpoint upsert and owner context follow SQL catalog; no public scheduler.
- Proofs: owner endpoint transfer preserves original date/device fallback and cap 20;
  foreign unsubscribe/timer cancel denied; SSRF/redirect/private-IP validation remains.
  Fake send failure/410/pruning and local reminder/nudge dates preserve current retry
  semantics, without promising exactly-once external delivery. Reboot does not invent
  durability for process presence/rest timers. Candidate/account revalidation precedes
  owner-scoped internal reads, no anonymous body selects a notification recipient.
- Checkpoint: transport fixture is not real push/device delivery; G0 identifies which
  actual devices/origins need separately authorized smoke evidence before cutover.

S7 runs before S6 in the default order: notifications use the already available
identity/admin authorization primitives, not administration routes. This avoids
faking hasPush or introducing a forward dependency on an uncreated table in S6.

### S8 — canonical JS, formats and OpenAPI (tasks 8.*)

- Scope: `shared/coach-core/`, prompts/generators, frontend imports, web/mobile build,
  CI and backend/openapi.yaml. No second editable JS/YAML source.
- Proofs: generated assets --check and client local coach agree with independent
  vectors; CSV/JSON/media backup/FIT/catalogue preserve current types/IDs and reject
  hostile imports; web/mobile bundles resolve no retired API source.
- Move OpenAPI only after every route family has method/path/response coverage;
  preserve generator --check, no new /docs or framework 422 behavior. Existing
  `node scripts/build-api-docs.mjs --check` and locale checker remain supported.
- Checkpoint: clean bundles/import graph and format cases pass, no claimed native
  hardware behavior from build-only checks.

### S9 — delivered images and diagnosis (tasks 9.*)

- Scope: dev/ops overlays, test/runtime/migrate/ops images, `core/telemetry` and
  diagnostic volume. No extra permanent service or exposed diagnostic endpoint.
- Proofs: cold/repeat/source-only/lock-change/test-only builds establish actual cache
  behavior; incompatible DB fails readiness, recovery reconnects, shutdown bounded.
  Trace links HTTP→pool/TX/query→fake external call; missing/false success is failure.
  Synthetic secret/history/SQL markers absent from every sink, error and durable copy.
  Active-file expiry, stopped API sweep, disk cap, exporter outage and queue overflow
  meet the reference without changing confirmed commits. Measure overhead versus
  profile off (report p50/p95/RSS/drop counts, no unapproved performance SLA).
- Checkpoint: private CLI finds a known synthetic trace and distinct 409/DB/external
  failure; logs-only health green is insufficient. Test log-driver/config inventory
  so an unnoticed Docker copy cannot invalidate age limits.

### S10 — faithful import and recovery (tasks 10.*)

- Scope: `operations/` CLI, ops image, manifest/age/staging/control volume; no business
  router migration at startup. Tests call actual commands with synthetic bundles.
- Proofs: invalid Unicode/duplicate JSON keys or ownership mismatch blocks untouched
  source/new target; valid import preserves internal state/types/sequences/secret refs.
  Concurrent client/internal writers cross write barrier coherently. Wrong key,
  truncation, failed copy/disk full and supervisor death never advance recovery point;
  interrupted capture is fail-closed and explicitly recoverable, with no orphan worker.
  Q1 fixture has post-snapshot revocation/deletion/counter evidence and unknown access;
  new signing key rejects all old tokens without losing coach decryption. Restore
  covers roles/RLS/media/client lineage and full timed review. Q2 independent W1/W2
  receipts survive bad API image, failed migration and uncertain reply; W3 works after
  compatible forward repair, incompatible repair remains no-go.
- Checkpoint: measured pause, snapshot/verified age and complete RTO scope including
  manual review. Synthetic result never claims physical independent disk, real keys,
  successful production recovery, zero RPO or universal failure preservation.

### S11 — authorization-gated cutover and clean acceptance (tasks 11.*)

- Precondition: all synthetic cases pass; actual G0 inventory/origins/RP ID, destination
  disk/key/config, protected later-access source and maintenance window verified under
  separately granted access. G1 operational/GP/GO reviewed before real cutover.
- No automatic command performs real cutover as a side effect of verification.
  Task 11.2 has an explicit human authorization hold. Before new commits, validate
  origin rollback; after commits only Q2 procedure, never return to stale Node.
- Classify each path/consumer remove/retain/protected, update consumers/tests before
  removing code; no second disabled business API. A protected frozen reference image
  may support historical comparison but is not a live reader/writer/dependency.
  Post-retirement acceptance uses frozen independent expected fixtures against Python,
  not active imports/tests of removed Node handlers. Preserve useful Foundation
  evidence/tooling or adapt its consumers explicitly; do not break it accidentally.
- Proofs: foreign sentinel and protected originals survive cleanup; independent clean
  checkout builds/format/HTTP/RLS/browser/restore/diagnostic suites pass after removal.
  Negative inventory test injects a retired import in disposable checkout and must
  fail. Original data/release/backups are not deleted at retention expiry.
- Checkpoint: G2/G3/GO evidence and EV-01–EV-09 acceptance recorded only after actual
  authorized delivery; no archive, sync, commit or Recovery start by this plan.

## Evidence and readiness gate

Per task, retain sanitized CI/temporary artifact: task/requirement/scenario, initial
proof and reason, revision/digests/platform, exact expanded command, restricted role,
fixture/fault/clock coordinates, independent observation, result and limitation.
Retention of run artifacts is not another permanent documentation report. A failed
critical check stops the dependent task; no checkbox is completed by drafting tests.

Planning readiness requires: every task has case+suite, dependencies resolve, SQL/
role/lock/retention/recovery choices are fixed, Q6 is explicit, seams remain within
Q3. Delivery prerequisites (actual tools, built images, initial RED, measurements,
operator config and real-data permission) are obligations of the tasks, not claimed
results here. Material changes in client support, security, recovery guarantees or
seams require renewed promoter decision; implementation still needs an explicit
request even when the specification is ready.
