## ADDED Requirements

### Requirement: Isolated local Compose operation
The initial accepted operation SHALL be one personal instance with Linux/amd64 containers, one API worker, permanent web/api/db services and point-in-time migration/operations tooling. It SHALL bind web to host loopback port 8080, use internal web 80/API 3000/PostgreSQL 5432, keep API/DB unpublished, separate app and internal DB networks and preserve authorized push/coach egress. Dev/CI/operations configuration, volumes and credentials SHALL be explicitly separated. Remote/LAN authentication and arm64 SHALL require their own configuration/evidence without silently withdrawing existing client support.

#### Scenario: Resolved topology and environment isolation
- **WHEN** dev and operations Compose combinations are inspected and executed on synthetic fixtures
- **THEN** only the intended loopback entry is published, web cannot directly reach DB, API retains required egress and unrelated/legacy data is not mounted
- **AND** operation uses identified images without source/dependency host binds while dev retains its explicit reload behavior

### Requirement: Controlled images migrations and lifecycle
Test/runtime/migrate images SHALL use the same revision/lock with immutable delivery references and no package installation at runtime. Runtime SHALL exclude development/test/Node harness dependencies. A separate least-privilege migrator SHALL hold the dedicated history lock through schema execution and finish before compatible traffic. API SHALL NOT migrate at startup. Bounded pool/timeouts, live/ready and dependency recovery SHALL be tested; no transaction SHALL wait on provider/network/file transfer work.

Runtime API SHALL run without root privileges, added coach capabilities, a Docker socket or privileged containers. The first delivery SHALL NOT install SDK/CLI runtimes, mount their credential caches or require a custom seccomp profile for deferred providers. Diagnostic Q4/Q5 feasibility SHALL NOT imply acceptance or delivery of those mechanisms.

#### Scenario: Deferred coach runtimes do not expand operation
- **WHEN** the runtime image and resolved dev/ops combinations are inspected
- **THEN** no claude/codex executable runtime, SDK launcher, coach credential-cache mount or custom coach seccomp override is required
- **AND** admitted HTTP coach operation remains available under the non-root runtime without installing optional agent dependencies at startup

#### Scenario: Incompatible schema or failed migration
- **WHEN** migration fails or DB/schema becomes unavailable or incompatible
- **THEN** traffic is not falsely declared ready, failures remain bounded and no JSON fallback or fake migration history is used
- **AND** recovery and shutdown are observable using internal probes without publishing diagnostic data

### Requirement: Coordinated encrypted recovery points
Operation SHALL provide backup every three hours, startup catch-up when overdue, pre-migration backup and monthly isolated restore rehearsal. Retention SHALL be 30 days on storage independent of the instance disk, with bundle key separate. PostgreSQL/media/configuration/required secrets SHALL form a verified coherent recovery point, using an explicit relevant-write barrier during capture and encryption/transfer outside that pause. RPO six hours/RTO 24 hours SHALL remain accepted objectives until measured, not guarantees or claims of PITR/off-host disaster coverage.

#### Scenario: Capture with internal writers and failed transfer
- **WHEN** clients, coach or internal metadata writers compete with backup capture and transfer later fails
- **THEN** the barrier establishes a coherent SQL/files recovery set, client pending work is preserved and its duration/deadlines are recorded
- **AND** incomplete/corrupt/untransferred artifacts are not credited as verified recovery points and degradation is visible locally

#### Scenario: Interrupted capture remains controlled
- **WHEN** API, capture supervisor or a writer fails during drain/capture, or the capture budget expires
- **THEN** incomplete captures never become recovery points, owned subprocesses stop and restart honors the fail-closed maintenance marker
- **AND** explicit owned-operation recovery verifies mutex and process termination before reopening writes, without TTL-only release or global cleanup

#### Scenario: Scheduled failures do not satisfy recovery objectives
- **WHEN** scheduled/startup/pre-migration backup or monthly rehearsal is overdue, fails or has no valid verified bundle
- **THEN** the local operator surface distinguishes warning at three hours and RPO breach beyond six hours using the verified bundle's snapshot time
- **AND** delivered Windows/Linux scheduler templates use isolated explicit configuration, bounded mutual exclusion and exit status, without installing real host jobs during specification or synthetic verification

#### Scenario: Monthly complete recovery rehearsal
- **WHEN** a representative bundle is restored in isolation
- **THEN** measured results verify required secrets, credentials, roles/RLS, documents, external media, lineage and client reconciliation within the stated scope
- **AND** evidence reports whether the accepted RPO/RTO objectives were met without inventing guarantees from scheduling alone

### Requirement: Restore preserves later security decisions
Restore SHALL remain isolated with external effects disabled, invalidate restored sessions/pairings and reconcile subsequent deletions/revocations including passkeys using sufficiently protected later information. A snapshot SHALL NOT be treated as proof of current authorization. The initial procedure SHALL require explicit manual operator review for each restored access, identifying the account/credential, snapshot, protected later evidence, coverage, decision and verification result without recording secrets. A snapshot, successful login or deletable best-effort audit alone SHALL NOT establish sufficient evidence. Unverifiable access SHALL remain blocked; operator review alone SHALL NOT override missing evidence. A new persistent security ledger or automated reconciliation store SHALL require separate promoter approval. The full review and verification time SHALL be included in measured RTO. Stale clients SHALL NOT silently overwrite restored Training or lose pending work.

#### Scenario: Session invalidation does not destroy coach decryption
- **WHEN** an isolated restore invalidates sessions issued before or after the snapshot
- **THEN** a new session-signing key rejects old cookie/bearer tokens even if session versions collide, while separately retained original decryption material still permits authorized coach secret recovery
- **AND** all restored access starts blocked, later decisions are reviewed per credential and the normal compatible port does not silently rotate the original session key

#### Scenario: Deleted account or revoked credential exists in snapshot
- **WHEN** a restored snapshot contains an account/credential later deleted or revoked and the later information is missing or incomplete
- **THEN** restored access remains blocked pending reconciliation/review rather than automatically reactivating it
- **AND** invalidating session tokens alone is not credited as resolving resurrected passkeys or missing deletion evidence

#### Scenario: Manual review with partial evidence
- **WHEN** later evidence verifies one restored access but cannot establish whether another credential was revoked or its WebAuthn counter remains safe
- **THEN** the operator records the scope and result of each review in protected recovery evidence and enables only the verified access after isolated checks
- **AND** the unresolved access remains blocked, no new security ledger is introduced implicitly and measured recovery time includes review and verification

### Requirement: Private bounded diagnostic operation
Operation SHALL provide private operator diagnosis without external telemetry services, structured bounded logs up to seven days and an optional local profile with traces up to 24 hours and metrics up to seven days. Storage caps and effective age deletion SHALL be tested for all durable copies. Probes/metrics SHALL remain internal or diagnostic interfaces loopback-private. Credentials, notes, prompts, personal history and SQL values SHALL be excluded. Exporter failure SHALL NOT change committed results or block requests indefinitely; audit remains separately governed.

Delivery SHALL use the observability reference's fixed local OpenTelemetry/manual instrumentation and bounded JSONL/CLI design without an external collector/dashboard service. Logs SHALL be bounded to 256 MiB/seven days, optional traces to 128 MiB/24 hours and optional metrics to 64 MiB/seven days, with bounded queues/export/shutdown. Age enforcement SHALL cover active/rotated files, startup and stopped-API retention tasks, not only size rotation. Operator status SHALL remain available without sampled traces. Physical deletion while the host is off SHALL NOT be promised; expiry cleanup SHALL precede resumed diagnostic access.

#### Scenario: Local diagnosis has fixed tools and limits
- **WHEN** the operator diagnoses a known synthetic HTTP/DB/provider operation with the diagnostic profile on or off
- **THEN** private CLI reports health, bounded pool/export status, audit degradation and verified-backup age without requiring public endpoints or sampled traces for minimum status
- **AND** with the profile enabled, sanitized correlated spans and bounded metric snapshots prove the relevant causal path; no external service or accidental Docker log copy bypasses retention

#### Scenario: Age expiry sensitive fixture and unavailable exporter
- **WHEN** signals exceed age/space limits, contain synthetic sensitive markers or the exporter is unavailable
- **THEN** retention and bounded-failure behavior are verified and no sensitive marker appears in emitted diagnostics
- **AND** size-only Docker rotation is not credited as age deletion and health/logging alone is not EV-08 acceptance

### Requirement: Single-authority cutover and verified retirement
Real cutover SHALL require G0 inventory/backups and prior G1/GP/GO evidence, an agreed rehearsed maintenance window, all writers paused and equivalent import before enabling PostgreSQL as the only authority. Origin/release/configuration/secrets SHALL remain frozen/protected for at least 30 days after accepted cutover without automatic deletion. Before new writes rollback SHALL use validated origin; after new writes the baseline SHALL be rehearsed forward repair of Python/PostgreSQL preserving new writes, never automatic return to the frozen Node origin or silent loss. Reverse export to Node SHALL be excluded unless separately approved by the promoter. If forward repair cannot preserve required writes in the agreed failure scenario, cutover SHALL remain blocked pending an explicit decision; periodic backups SHALL NOT be presented as zero RPO. G3/GO SHALL be demonstrated again after removing replaced dependencies before Recovery implementation begins.

#### Scenario: New writes followed by rollback request
- **WHEN** the new backend has accepted writes and an operator requests rollback
- **THEN** the operator uses the rehearsed forward-repair procedure with independently verified preservation of the new writes, without automatic fallback, old-backup data loss or an unapproved reverse exporter
- **AND** preserved original artifacts are not an active second authority or permission to delete them after the retention minimum

#### Scenario: Forward repair cannot preserve new writes
- **WHEN** a pre-cutover rehearsal cannot recover required acknowledged writes under the agreed failure scenario
- **THEN** the rehearsal fails and real cutover remains blocked pending promoter resolution rather than silently accepting data loss or implementing reverse export
- **AND** results distinguish repair of the surviving destination from recovery after destination loss within the accepted RPO scope

#### Scenario: Post-retirement acceptance
- **WHEN** platform closeout is considered after cutover and legacy removal
- **THEN** capability/security parity, operation/diagnosis/restore and absence of active retired storage readers are evidenced again
- **AND** documentation validation or Foundation fixtures alone cannot authorize platform acceptance or Recovery start
