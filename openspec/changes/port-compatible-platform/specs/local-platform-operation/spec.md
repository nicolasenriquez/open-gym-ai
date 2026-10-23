## ADDED Requirements

### Requirement: Isolated local Compose operation
The initial accepted operation SHALL be one personal instance with Linux/amd64 containers, one API worker, permanent web/api/db services and point-in-time migration/operations tooling. It SHALL bind web to host loopback port 8080, use internal web 80/API 3000/PostgreSQL 5432, keep API/DB unpublished, separate app and internal DB networks and preserve authorized push/coach egress. Dev/CI/operations configuration, volumes and credentials SHALL be explicitly separated. Remote/LAN authentication and arm64 SHALL require their own configuration/evidence without silently withdrawing existing client support.

#### Scenario: Resolved topology and environment isolation
- **WHEN** dev and operations Compose combinations are inspected and executed on synthetic fixtures
- **THEN** only the intended loopback entry is published, web cannot directly reach DB, API retains required egress and unrelated/legacy data is not mounted
- **AND** operation uses identified images without source/dependency host binds while dev retains its explicit reload behavior

### Requirement: Controlled images migrations and lifecycle
Test/runtime/migrate images SHALL use the same revision/lock with immutable delivery references and no package installation at runtime. Runtime SHALL exclude development/test/Node harness dependencies. A separate least-privilege migrator SHALL hold the dedicated history lock through schema execution and finish before compatible traffic. API SHALL NOT migrate at startup. Bounded pool/timeouts, live/ready and dependency recovery SHALL be tested; no transaction SHALL wait on provider/network/file transfer work.

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

#### Scenario: Monthly complete recovery rehearsal
- **WHEN** a representative bundle is restored in isolation
- **THEN** measured results verify required secrets, credentials, roles/RLS, documents, external media, lineage and client reconciliation within the stated scope
- **AND** evidence reports whether the accepted RPO/RTO objectives were met without inventing guarantees from scheduling alone

### Requirement: Restore preserves later security decisions
Restore SHALL remain isolated with external effects disabled, invalidate restored sessions/pairings/MCP tokens and reconcile subsequent deletions/revocations including passkeys using sufficiently protected later information. A snapshot SHALL NOT be treated as proof of current authorization. Access without sufficient reconciliation SHALL remain blocked until explicit review; stale clients SHALL NOT silently overwrite restored Training or lose pending work.

#### Scenario: Deleted account or revoked credential exists in snapshot
- **WHEN** a restored snapshot contains an account/credential later deleted or revoked and the later information is missing or incomplete
- **THEN** restored access remains blocked pending reconciliation/review rather than automatically reactivating it
- **AND** invalidating session tokens alone is not credited as resolving resurrected passkeys or missing deletion evidence

### Requirement: Private bounded diagnostic operation
Operation SHALL provide private operator diagnosis without external telemetry services, structured bounded logs up to seven days and an optional local profile with traces up to 24 hours and metrics up to seven days. Storage caps and effective age deletion SHALL be tested for all durable copies. Probes/metrics SHALL remain internal or diagnostic interfaces loopback-private. Credentials, notes, prompts, personal history and SQL values SHALL be excluded. Exporter failure SHALL NOT change committed results or block requests indefinitely; audit remains separately governed.

#### Scenario: Age expiry sensitive fixture and unavailable exporter
- **WHEN** signals exceed age/space limits, contain synthetic sensitive markers or the exporter is unavailable
- **THEN** retention and bounded-failure behavior are verified and no sensitive marker appears in emitted diagnostics
- **AND** size-only Docker rotation is not credited as age deletion and health/logging alone is not EV-08 acceptance

### Requirement: Single-authority cutover and verified retirement
Real cutover SHALL require G0 inventory/backups and prior G1/GP/GO evidence, an agreed rehearsed maintenance window, all writers paused and equivalent import before enabling PostgreSQL as the only authority. Origin/release/configuration/secrets SHALL remain frozen/protected for at least 30 days after accepted cutover without automatic deletion. Before new writes rollback SHALL use validated origin; after new writes recovery SHALL require validated reverse export or forward correction, never silent loss. G3/GO SHALL be demonstrated again after removing replaced dependencies before Recovery implementation begins.

#### Scenario: New writes followed by rollback request
- **WHEN** the new backend has accepted writes and an operator requests rollback
- **THEN** no automatic fallback or old-backup restore silently discards those writes and the explicit recovery procedure is used
- **AND** preserved original artifacts are not an active second authority or permission to delete them after the retention minimum

#### Scenario: Post-retirement acceptance
- **WHEN** platform closeout is considered after cutover and legacy removal
- **THEN** capability/security parity, operation/diagnosis/restore and absence of active retired storage readers are evidenced again
- **AND** documentation validation or Foundation fixtures alone cannot authorize platform acceptance or Recovery start
