# Executable delivery plan

## Status and authority

Writing this plan performed no product implementation, migrations, runtime
experiments or operational actions. Subsequent delivery is limited to the explicitly
selected tasks; [tasks](tasks.md) is the only progress ledger. Q1–Q3 and Q6 remain
binding with the revised Q1 two-path recovery and controlled-stop backup below;
Q4/Q5 are concluded diagnostic evidence, not delivery acceptance.

This plan closes technical preparation, not GP/GO/G3 or permission to cut over.
Physical backup location, real-client inventory, measured times and operational
credentials are inputs to later acceptance tasks, not facts supplied by this plan.
If an environment cannot satisfy the specified gates, stop rather than weaken them.

Authoritative detail: [DDL](../../../docs/reference/platform-schema.md#especificación-ddl-y-evolución),
[SQL functions/roles](../../../docs/reference/platform-security.md#catálogo-sql-y-contexto-transaccional),
[diagnostics](../../../docs/reference/platform-observability.md#configuración-cerrada-y-límites-iniciales),
[recovery](../../../docs/reference/platform-operations.md#procedimientos-operativos-especificados).
Do not duplicate editable SQL schemas or operating procedures here.

## Delivery checkpoints

1. Functional port: preserved frontend on Python/PostgreSQL with admitted
   capabilities; first tracer is login → read → save → reload → PG persistence.
2. Recoverable local operation: identified images, migrations, scheduled/startup/
   pre-migration backup and isolated restore pass on synthetic resources.
3. Authorized migration and retirement: S11 retains real cutover, retirement and
   actual G0/G2/G3 acceptance in this change, under separately granted operational permissions.

Checkpoints 1/2 and rehearsals of 3 use disposable resources. Task 11.1 is
administratively closed by explicit promoter decision (2026-11-03); tasks 11.2–11.5
remain pending in tasks.md, the sole progress ledger. Existing operational cutover
conditions remain unchanged; no work or scope is added to 11.2. Complete S11 before archive.
The [collection plan](collection-plan.md) and [empty inventory](inventory.template.json)
are supporting artifacts. Documentary preparation and synthetic completion neither
establish platform acceptance nor authorize operation or Recovery.

## Commands and safety contract

**Existing checks**, executable now without delivering product code:

```sh
openspec validate port-compatible-platform --strict --no-interactive
node scripts/docs/okf.mjs check
node --test scripts/docs/okf.test.mjs
git -c core.safecrlf=false diff --check
```

**Incremental delivery command**: task 1.2 supplies `harness/ownership` and
`contracts/baseline`; task 1.4 adds `schema/history_lock` with its disposable
PostgreSQL and test image; 1.5 adds `images/isolation`, and 1.3 adds
`lifecycle/readiness` with real bootstrap HTTP. Other suites below remain future contracts:

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

A suite/case manifest maps delivered cases to requirement/scenario, setup, command,
expected proof and checkpoint. Add mappings/images with their implementing slice,
not empty placeholders for the entire port. Unknown or undelivered suites/cases
return exit 2; absent/empty mapping or silent skip cannot pass.
Reuse Foundation execution/ownership mechanisms without sharing instance settings.
Extract only behavior needed by both harnesses; preserve their separate resource
namespaces and rerun Foundation regressions. Do not duplicate cleanup engines.
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
against Python, not mocked API. Task 1.2 delivers initial harness mapping/image;
browser pins/image arrive with 3.4 before browser verification, not in bootstrap.
No host browser/dependency installation is implied. Operational suites run the
actual host wrapper and ops commands on synthetic projects, not mock-only CLI.

**Future operating prefix O**, a textual abbreviation, not a shell function or
installed binary (replace only the explicit operator.env placeholder):

```sh
docker compose --project-directory . --env-file <absolute-operator.env> -p opengym-ops -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml run --rm ops -m opengym_platform.operations
```

Append one command below; ops keeps its Python entrypoint and the prefix selects
`opengym_platform.operations`. Operator env contains only non-secret
configuration/file refs; `/run/operator/config.json` is mounted read-only. Secrets
are distinct restricted file mounts. The revised operation also requires Node 22+
on the host for the small Compose wrapper, not in API images. Wrapper contract:
`node scripts/platform.mjs operate <backup|migrate|maintenance-recover> --config
<absolute-operator.json>`; backup also requires `--reason scheduled|startup|pre-migration`.
It owns host exclusion, writer stop/start and private journal; ops owns capture and
cryptographic tools. Direct ops backup/migrate must reject absent writer-stop proof.
Commands are future contracts, not permission to install Node or run operations.

| Future command appended to O | Preconditions and result |
| --- | --- |
| `preflight --config /run/operator/config.json` | Validate instance ownership, paths/devices, tools, digests, keys and isolation; no mutation. 0 valid, 1 blocked, 2 usage/config error. |
| `migrate --config /run/operator/config.json` | Pre-migration verified backup for populated instance, exclusive lock, explicit known head; nonzero prevents ready/up. |
| `import --config /run/operator/config.json --source /run/import/source --target <new-id>` | Frozen read-only source; new owned target only, prevalidate then import/compare. Nonzero leaves target unexposed, never edits source. |
| `backup --config /run/operator/config.json --reason scheduled` | Called by host wrapper after verified writer stop; exclusive lock, coherent capture and verified encrypted destination. Only exit 0 advances recovery-point state; reason also accepts startup/pre-migration. |
| `restore --config /run/operator/config.json --bundle <id> --target <new-id>` | New isolated target, full verification and blocked restored access; not permission to open traffic. |
| `restore-review --config /run/operator/config.json --target <id> --review /run/review/review.json` | Protected Q1 evidence and explicit per-credential decision; reject missing coverage, no new security ledger. |
| Host: `node scripts/platform.mjs operate restore-rehearse --config <absolute-rehearsal.json>` | Delivered 10.7 host coordination of the isolated ops restore/new-access commands; incident/config binds bundle/target/review. Full timing includes preparation/review and operation-bound private client evidence with PG readback, temporary internal runtime only, normal gate blocked. Missing evidence/access uncertainty is incomplete; no automatic production promotion. This row is not appended to O. |
| Host: `node scripts/platform.mjs operate forward-repair --config <absolute-private-host.json> --incident <id> --release sha256:<tested-local-image-id>` | Surviving destination and independent Training/media witness, coherent current copy, same-head no-root release; persists API digest selection, requires readiness. Nonzero after maintenance starts holds gate/exclusion for review, without old-data restore or corrective DDL. This row is not appended to O. |
| `maintenance-recover --config /run/operator/config.json --operation <id>` | Host wrapper verifies journal ownership, exclusion, stopped capture processes and compatible schema before restoring only previously running services. |
| `restore-access-recover --config /run/operator/config.json --target <id> --review /run/review/review.json` | New path on isolated restored target for explicitly selected verified account; historical doubtful credentials stay blocked, no role elevation. 10.5 uses the approved private per-account review/new-password delivery contract in design.md; historical credentials stay inactive. |
| `diagnose --config /run/operator/config.json` | Private redacted live status; exit 1 degraded and 2 invalid config/usage. Request lookup uses standard rotate/grep in the private collector shell. |
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

#### Delivered pre-cutover evidence validator (synthetic preparation)

`node scripts/platform.mjs verify gates --case pre_cutover` runs only temporary
synthetic CLI fixtures, without Docker, instance configuration or network access.
It does not establish operational readiness; 11.1 is administratively closed.
Add `--evidence <index.json>` to inspect an explicitly
selected sanitized index; no recorded command is executed. The separate `node_capture`
case rehearses the stopped-Node copy procedure on disposable resources, as described
in the [collection plan](collection-plan.md#procedimiento-ensayado-de-captura-node-detenida).
`node_capture_import` continues that capture through the existing importer into new
isolated PostgreSQL, with an independent observer and runtime CONNECT still denied.
`node_capture_recovery` adds the existing real host backup wrapper, verified age
bundle and a separate isolated restore; fixture-only runtime checks end with the
restored gate/CONNECT closed. It preserves the original Node cutoff in configuration
and does not establish Q1, real RPO/RTO, operational permission or acceptance.
Other gate cases remain undelivered. Exit 0 means structurally valid evidence, exit 1 rejected evidence,
and exit 2 unsupported arguments. Both modes report `realGateCompleted: false`
and `cutoverAuthorized: false`; evidence inspection also reports
`manualReviewRequired: true`. No index can authorize traffic or complete a real gate.

The v1 index is a JSON object with these required fields:

- `version: 1`, `case: "pre_cutover"`, `synthetic` (boolean), `instance` (nonempty ID),
  `revision` (40 lowercase hex characters), `digest` (`sha256:` plus 64 lowercase
  hex characters), and `platform` (nonempty platform name).
- `artifactRoot: "artifacts"`: the fixed allowlisted directory beside the index.
  `artifacts` contains unique `{ "path": "proof.txt", "sha256": "<64 lowercase hex>" }`
  entries. Paths use relative forward-slash components made of letters, digits,
  `_`, `-`, and interior dots; traversal, absolute paths and links are rejected.
- `review` and `authorization` name checksummed artifact paths recording the human
  review and permission to inspect operational evidence. These are references,
  not trusted assertions of actual permission or authorization to cut over.
- `releaseManifest` names a checksummed JSON artifact with `version: 1`, a `binding`
  identical to the index, `contentIdentity` (`sha256:` plus 64 lowercase hex),
  nonempty `schemaHead`, and `images` (6–128 unique roles). Required roles are
  `api`, `web`, `postgres`, `migrate`, `ops`, `collector`; include other images used
  with distinct roles. Each entry has `role`, immutable `digest`, the candidate
  `platform` and nonempty `sourceIdentity` identifying its pinned source/locks.
  The API digest equals the index digest. Content identity identifies the complete
  candidate, including uncommitted content; HEAD alone does not do that. The
  validator checks declarations, not Docker images, source contents or SQL head.
- `gates` has exactly one `{ "gate": "G0", "checks": [...] }` entry for each gate
  below. Each named check occurs exactly once and contains `result: "passed"`,
  `skipped: 0`, nonempty `command`, `scope`, `limitations`, a nonempty `ev` array
  of `EV-01` through `EV-09` references, and a nonempty `artifacts` array naming
  checksummed paths. Its `binding` object repeats `instance`, `revision`, `digest`,
  and `platform` exactly from the index, so mixed targets/releases are rejected.
  Each check also has `provenance` with the original `instance`, `revision`,
  `digest`, `platform` and `observedAt` (canonical UTC ISO with milliseconds).
  When that identity differs from the candidate binding, `applicability` must name
  a checksummed review artifact. Preserve original evidence identity; this reference
  does not certify that historical or synthetic evidence suffices for a real gate.
- `recovery` contains `sourceType` (`node_json` or `python_postgresql`),
  `sourceCutoffAt`, `capturedAt`, `importedAt` (required timestamp for Node, `null`
  for native Python), and `report` naming a checksummed sanitized rehearsal JSON.
  Its `version: 1` and added `binding` identify the candidate. Retain the existing
  rehearsal fields `snapshot_at`, `incident_at`, `started_at`, `finished_at`,
  `elapsed_ms`, `rpo_ms`, `objectives_ms`, `complete`, `closed`, `reviewed`,
  `unresolved_accesses`, `rpo_met`, `rto_met`, `rto_credited`,
  `operational_acceptance`. Export only this sanitized subset plus binding; never
  submit the raw private report, config or bundle paths. Keep original provenance
  and the binding/applicability justification with the check's evidence.
  All timestamps use canonical UTC ISO with milliseconds and must be ordered:
  source cutoff ≤ capture ≤ Node import (when applicable) ≤ snapshot ≤ incident
  ≤ start ≤ finish. Effective RPO is incident minus **source cutoff**, at most
  6 hours; RTO includes incident through finish, at most 24 hours. The original
  `rpo_ms` must match incident minus Python snapshot; it cannot hide an older Node
  cutoff. `elapsed_ms` must cover wall time and remain within 24 hours (the existing
  rehearsal uses the greater wall/monotonic elapsed time). Objectives must be
  exactly 6/24 hours, completion/review/closure and RPO/RTO credit true, unresolved
  accesses zero, operational acceptance false. The `GO/restore_rpo_rto` check must
  reference this report. These are consistency checks on supplied claims, not an
  independently timed restore or proof of physical backup, capture or client state.

| Gate | Required check names |
| --- | --- |
| G0 | `clients_origins`, `client_pending_active_media`, `frontend_api_mapping`, `physical_backup_keys`, `protected_later_access_source`, `rehearsed_window` |
| G1 | `target_environment`, `pool_lifecycle`, `roles_rls_transactions`, `migrations_lock_interrupt`, `backup_restore` |
| GP | `capability_parity_q6`, `frontend_offline_sync`, `security_audit`, `module_contracts` |
| GO | `clean_checkout_images_ci`, `runtime_environments`, `restore_rpo_rto`, `diagnostics_privacy_retention`, `forward_repair_new_writes` |

The index is limited to 1 MiB, each regular single-link artifact to 4 MiB, and the
inventory to 128 files/32 MiB total. Symlinks/junctions in all path components and
hardlinked input files are rejected. Output contains fixed result codes/flags only;
file contents, paths, commands and parser errors are not printed. The operator must
own and keep the sanitized index/root stable during inspection: this read-only
validator does not enforce ACLs, authenticate authorship, certify completeness of
real client inventory, verify a physical disk/key, or judge the substance of human
review. No secret, operational config or original user data belongs in this input.
`scripts/platform-gates.test.mjs` supplies the synthetic format example and negatives.

Task 11.1 is administratively closed, accepting its documented preparation only.
S11 still needs actual scoped evidence, manual review and operational permission
under the existing cutover conditions; closing 11.1 neither satisfies those
conditions nor expands 11.2. S11 completion, real inventory and cutover remain pending.

#### Delivered authorized-cutover evidence validator

`node scripts/platform.mjs verify gates --case authorized_cutover` runs synthetic
inspector tests only, without Docker. With `--evidence <sanitized-index.json>`, it
inspects a recorded execution package; it never executes or authorizes a cutover.
It reuses the complete pre-cutover v1 format and all coverage, digest, provenance,
recovery and safe-file checks above, with `case: "authorized_cutover"` and:

- `authorization` names a checksummed JSON artifact: `version: 1`, candidate
  `binding`, `releaseManifestSha256` matching the indexed release file, `scope:
  "cutover"`, `decision: "approved"`, nonempty `operator`/`approvedBy`, `approvedAt`
  and `window: {start, end}`. Times use canonical UTC ISO strings. Approval follows
  recovery completion and all check observations, and precedes the window start.
- `cutover` names a checksummed JSON artifact: `version: 1`, candidate `binding`,
  `authorization` matching the index reference, `startedAt`, `finishedAt`, `outcome`,
  `authority`, `acknowledgedNewWrites`, `protectedUntil` and `evidence`. Execution
  times are ordered inside the positive-length approved window. Protection lasts
  at least 30 days after completion; this date never authorizes deletion.
- `evidence` references indexed artifacts for `writersStopped`, `equivalentImport`,
  `singleAuthority` and `protectedOriginReleaseConfigurationSecrets`.
  `outcome: "cutover"` requires `authority: "python_postgresql"` and a nonnegative
  safe-integer new-write count. `rollback_before_writes` requires zero new writes,
  `authority: "node_json"` and `validatedOriginRollback` evidence. `forward_repair`
  requires a positive new-write count, `authority: "python_postgresql"` and
  `preservedNewWrites` evidence. Other outcomes or authorities are rejected.

Exit codes and output are the same as pre_cutover, with the selected case name.
Even `synthetic: false` never changes `manualReviewRequired: true`,
`realGateCompleted: false` or `cutoverAuthorized: false`. Statements, names and
proof references are structurally checked, not authenticated or substantively
accepted. The fixture in `scripts/platform-gates.test.mjs` supplies a complete
synthetic example. Real evidence collection, permission and execution remain
pending; delivering this inspector does not close 11.2 or reopen 11.1.

## Slice contracts and first proofs

Paths below are future module roots under `backend/src/opengym_platform/` unless
explicitly frontend/shared. No empty modules/tables are created in advance. Services
own transactions; collaborators receive the same handle. External network/filesystem
work occurs outside SQL transactions. Backup captures only after all application
writers have stopped; no application lease/socket protocol is introduced.
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

- Scope: `training/`, p002; GET/PUT `/api/v1/data`, `/api/v1/data/rev`, ServerSync/store.
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
  The authorized 6.3 adjustment adds next_attempt_at and the five narrow internal
  Administration functions in the security catalog. Claim commits before files;
  processing rechecks absent owner/unbound references under namespace and task locks
  until local no-follow unlink completes. Private status/run/retry uses configured
  runtime credentials, no new HTTP surface; done metadata remains inspectable.
- Invitations consumed remain consumed after account deletion. Audit read/clear is
  admin-only, sequence retained; both age/count limits and IP-off default work.
  Failed audit append is observable after business commit, never converts success.
- Checkpoint: pending and completed external cleanup evidenced separately; no secrets
  reassigned, no history/invitation destroyed through an accidental FK cascade.

### S7 — notifications/activity (tasks 7.*)

- Scope: `notifications/`, p005; Settings/SW/device, `/api/v1/push/*`, `/api/v1/activity`.
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

9.2 resolves the retention prerequisite with pinned rsyslog/logrotate and its
private Compose collector. Promoter approved Unix for API and non-blocking Docker
syslog without durable cache/published ports for nginx/PostgreSQL. The delivered
configuration, CVE applicability and acceptance limits live in platform-observability.

- 9.1 is independently authorized for image/cache/lifecycle verification; retention
  selection/configuration gates only 9.2–9.4.
- Scope: delivered images, standard structured logging and private diagnose;
  no OpenTelemetry, custom exporter, span store or metric snapshots.
- Prerequisite: select/pin standard rotation and age/space retention tooling and
  enumerate all durable copies, including Docker/nginx/PG. Resolve before 9.2–9.4 code;
  this revision does not claim a tested tool/configuration.
- Proofs: cold/repeat/source-only/lock-change/test-only builds; DB/schema readiness,
  reconnect and bounded shutdown. Follow HTTP→DB→fake external call using request_id,
  safe result and duration. Synthetic sensitive markers absent from every copy.
  Active-file expiry, restart, stopped API sweep and full/unavailable sink preserve
  HTTP/commit contract, bounded buffers and shutdown.
- Checkpoint: CLI distinguishes 409, DB failure and external timeout by correlated
  records; green health alone is insufficient. No advanced tracing is claimed.
  9.3 uses private collector rotate/grep for hex32 lookup and existing ops diagnose
  for live status; no custom --request reader. HTTP/DB adapter/provider/job records
  share process-local context, including completion after 202, without external
  propagation or SQL/exception content.
  9.4 reuses collector/image tests with persistent restart controls, real nginx and
  a private provider; synthetic Compose ports are removed before execution. Timer
  proofs advance only the disposable supervisor clock, plus utime on fixtures,
  including an actual stopped API. Docker LogPath/cache/read rejection and native
  file destinations cover diagnostic copies. ENOSPC may tear a record; privacy
  checks every byte, and schema checks complete records. Business SQL/audit are not
  diagnostic copies. The Unix socket backpressure proof remains operator_status.

### S10 — faithful import and recovery (tasks 10.*)

10.1 delivers the separate ops-only import command described in
[the operation reference](../../../docs/reference/platform-operations.md#importación-aislada-de-origen-node).
It requires a provisioned empty target with explicit DB ownership marker, denied
runtime CONNECT and no connected writers; it never bootstraps/migrates or opens
traffic. Q3 proofs use image-frozen read-only files, the actual command, real PG,
independent inspection and HTTP only after explicit synthetic target opening.
Unknown data, personal instance-result details and current jobs without trigger
remain blocked rather than discarded/invented. Source stopping, backup/restore and
Q1 review are separate tasks. SQL/readback/file equivalence precedes completion;
sequence RESTART rolls back on copy failure, partial files remain quarantined.

10.8 extends the existing host/ops capture with data/GC/Coach/VAPID, actual runtime
secret mounts and selected host inputs plus resolved Compose/runtime configuration.
The approved trust boundary requires exclusive operator custody of Docker/host
sources during the pause. Observed early/late external writable mounts, changed
source inventories/bytes/identity, unsafe links and selected/runtime secret mismatch
block capture/restart. Read-only mounts and point-in-time inspection do not freeze
arbitrary host writers or exclude transient containers; no such guarantee is made.
Private staging retains an unverified checksummed set unless 10.3 bundle publication
is configured. Full restore remains separate; explicit journal recovery is delivered
in 10.10 below. The three older backup case IDs reuse the integration proof with a bounded ten-minute harness deadline; individual
capture budget remains 120 seconds. Actual pause is measured, not inferred.

10.3 adds optional host bundle configuration with separate destination/X25519 identity
and recipient, never a captured Compose secret/config. Pinned official age 1.3.2
asset/digest/license goes only into ops/test. After compatible restart, retain host
exclusion and acquire the PG session mutex, without a transaction over streaming IO.
Build USTAR v1/encrypted manifest with actual images/head/tools/coverage/checksums,
copy ciphertext to destination .partial, fsync, reread/decrypt to authenticated EOF,
verify entries/hashes and unchanged ciphertext before rename and atomic receipt.
Only complete publication credits a point; wrong key, truncation, unsafe entries,
post-EOF mutation, ENOSPC, mutex or process failure preserves the old point. Protect
partials/cleanup pending. Persist named bundle process/client for explicit recovery,
including death between publication and unlock; uncertain publication needs review.
Private diagnose reads snapshot age from a RO receipt, not a live disk probe.
`verify backup --case verified_bundle` uses a separate test with existing shared proof
setup/cleanup, avoiding replay of the encryption matrix for each old case. It checks
real CLI/age/PG and bounded filesystem faults; no full restore/physical disk claim.
Windows host ACL attestation handles synthetic POSIX modes in Docker Desktop.
Pre-migration stays held until coordinated DDL; no retention/scheduler delivery.

10.4 delivers the documented ops restore CLI and standalone docker-compose.restore.yml,
not a new host recovery protocol. Fresh isolated cluster/volumes/role passwords,
explicit ownership comment, migrated exact schema/defaults, revoked runtime CONNECT,
zero other DB peers and shared session mutex are required. Reuse authenticated age
reader twice (no-extract preflight then safe extraction), strict USTAR/data_filter,
bounded inventory and post-extraction rereads; compare capture.json and stable source.
Load only data/sequences into trusted schema/roles/grants/FORCE RLS, never dump
DDL/ACL/passwords. Exit 0 is RESTORE_QUARANTINED with private result/journal and
blocked gate, not current credential approval or an exposed application. Partial or
uncertain attempts remain closed, cannot be reused automatically and require operator
review/new isolated target, not lock deletion or another recovery state machine.
verify restore --case isolated_target uses the existing encrypted capture setup and
the real standalone target template, independent all-table/file/sequence/catalog
comparison and real runtime A/B, new PG passwords, corruption/missing secrets/unsafe
archives, rejected foreign/exposed/nonempty/busy targets/mutex, real extraction ENOSPC
and kill during age. No source mutation, API bootstrap, egress or access opening.
Q1/signature/reconciliation/full timing remain 10.5/10.7, physical prerequisites unproven.

10.10 adds `operate maintenance-recover --config <host-config> --operation <hex32>`
using the same host/ops seams. API startup checks only a separate RO gate marker
before creating DB/filesystem/background writers; missing/foreign/invalid admission
fails closed. Only explicit new-instance provisioning initializes admission; the
fixed gate directory is never replaced to clear a hold. Controller ownership uses
OS creation identity plus host/PID, with atomic immutable recovery successors and
no TTL release. A live owner blocks; incomplete legacy/identity/journal or uncertain
capture creation requires forensic review, not automatic takeover. Registered ops
capture/check containers and Docker client must cease, originals/images/schema must
match, and actual API readiness precedes success. Failed restart reblocks/stops
writers. Recovery of recovery is covered, as are unrelated sentinels and stopped API;
startup never calls another backup. Pre-migration stays held without DDL. This is
service recovery, not a verified backup, hardware power-loss or real host rehearsal.

10.9 uses the promoter-approved public host CLI/template seams, not a second
scheduler or backup coordinator. Windows XML and Linux cron templates call existing
scheduled/startup backup, monthly restore-rehearse and hourly diagnostics-retain;
pre-migration remains a manual fail-closed prerequisite without DDL. Startup checks
valid owned receipt age once under existing local exclusion, after unresolved-journal
rejection: <3 h skips without crediting a new point, >=3 h/missing/invalid evidence
uses the existing capture. Real Python UTC offset/microsecond receipts are covered.
Retention executes the pinned owned live collector's rotate under its existing lock,
with API absent and backup disk/key unavailable; it does not restart a stopped collector
or touch backups. Monthly config must select a new isolated target and explicit
private review; partial/reused/missing preparation fails, never unattended success.
`verify backup --case scheduling_and_age` checks public CLI/real Docker retention,
foreign sentinels, lock/journal/age/failure codes and template frequencies/actions;
Windows XML actions execute without registration. Existing verified_bundle and
full_timing cases provide integrated backup/restore regressions. No jobs are installed;
Linux native scheduler/Windows Task Scheduler service execution and real boot remain
operational proof, not inferred from template parsing or synthetic commands.

- Scope: host Compose wrapper, `operations/` CLI, ops image, manifest/age/staging and
  private operation journal; no business router migration at startup. Test actual
  commands with synthetic bundles. Stop/start uses host Docker CLI, never a container
  socket. Preserve previously stopped service state.
- Proofs: invalid Unicode/duplicate JSON keys or ownership mismatch blocks untouched
  source/new target; valid import preserves internal state/types/sequences/secret refs.
  Writer shutdown before SQL/files capture is independently observed; unknown external
  writers block backup. Wrong key, truncation, disk full and wrapper/host death never
  advance recovery point. Journal recovery waits for capture processes to stop;
  schema mismatch prevents API startup. Pre-migration backup stays stopped through
  DDL; startup check never recursively triggers another backup.
  Q1 fixture has post-snapshot revocation/deletion/counter evidence and unknown access;
  new signing key rejects all old tokens without losing coach decryption. Restore
  covers roles/RLS/media/client lineage and full timed review. Q1 also proves new-path
  recovery without reviving doubtful credentials or elevating roles; specify local
  authorization and private credential delivery before implementing 10.5.
  Q2 independent W1/W2
  receipts survive bad API image, failed migration and uncertain reply; W3 works after
  compatible forward repair, incompatible repair remains no-go.
- Checkpoint: measured pause, snapshot/verified age and complete RTO scope including
  manual review. Synthetic result never claims physical independent disk, real keys,
  successful production recovery, zero RPO or universal failure preservation.

### S11 — operational review, cutover and retirement (tasks 11.*)

[tasks.md](tasks.md) owns progress. The [collection plan](collection-plan.md)
owns permissions, the unchanged twenty-check coverage matrix and the
[existing retirement/closeout checks](collection-plan.md#checks-existentes-para-retirada-y-cierre).
The private runbook instantiates resources and commands; do not copy it here.
Rehearsals/inspectors already delivered are reused, not expanded by routine.

After explicit cutover authorization, retire only reviewed obsolete paths after
migrating native coverage/consumers. Reuse pytest/Vitest/browser/build/restore/
diagnostic suites on the retired tree; preserve foreign sentinels and protected
originals and demonstrate the retired-consumer negative in a disposable checkout.
No new cleanup/parity/acceptance verifier is required. Human EV/gate acceptance
uses those final results once; no implicit operation, deletion, Recovery, commit,
push, sync or archive is authorized by documentation or synthetic success.

## Evidence and readiness gate

Per task, retain sanitized CI/temporary artifact: task/requirement/scenario, initial
proof and reason, revision/digests/platform, exact expanded command, restricted role,
fixture/fault/clock coordinates, independent observation, result and limitation.
Retention of run artifacts is not another permanent documentation report. A failed
critical check stops the dependent task; no checkbox is completed by drafting tests.

Readiness is slice-local: delivered task has executable case+suite, prerequisites
and decisions resolved, Q6 explicit and seams within Q3. Initial harness does not
require future browser/diagnostic tooling. 9.2–9.4 are blocked until standard retention
selection/configuration is fixed; 10.5 required a local recovery authorization/private
delivery decision. That decision is now approved in design.md; delivery evidence and
remaining gates belong to tasks.md. This plan does not claim whole-change Implementation Ready. Delivery prerequisites (actual tools, built images, initial RED, measurements,
operator config and real-data permission) are obligations of the tasks, not claimed
results here. Material changes in client support, security, recovery guarantees or
seams require renewed promoter decision; implementation still needs an explicit
request even when the specification is ready.
