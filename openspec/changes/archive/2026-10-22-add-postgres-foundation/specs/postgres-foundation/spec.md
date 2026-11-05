## ADDED Requirements

### Requirement: Isolated synthetic environment
The foundation SHALL run reproducibly against an explicitly pinned supported stable PostgreSQL release using synthetic credentials and data only. Its environment SHALL be independent of the existing API/web stack, DATA_DIR, coach credentials and personal media. PostgreSQL SHALL NOT become authoritative for existing domains. Tooling SHALL reject non-test targets before destructive operations.

#### Scenario: Independent foundation run
- **WHEN** an operator starts the foundation environment
- **THEN** it creates only isolated test resources without loading the instance's real environment or mounting personal directories
- **AND** the existing API, including health, remains usable without PostgreSQL

#### Scenario: Unsafe target rejected
- **WHEN** cleanup or restore targets a database or resource outside the explicitly identified disposable environment
- **THEN** the operation fails before modifying that target

### Requirement: Bounded connection lifecycle and transactions
The foundation SHALL expose an explicit bounded pool lifecycle and transaction boundary compatible with the project's Node 22 ESM runtime. All statements in a transaction SHALL use the same leased client. Failures SHALL roll back and release or discard the client appropriately. Acquisition and queries SHALL have finite timeouts; shutdown SHALL release resources. Errors SHALL NOT disclose credentials, connection strings or personal payloads. TLS configuration SHALL NOT disable certificate validation.

#### Scenario: Failure and reuse
- **WHEN** a transaction fails after a synthetic write and its connection is reused
- **THEN** the failed write is absent and the next operation has no prior transaction or owner context

#### Scenario: Pool saturation and shutdown
- **WHEN** all configured clients are occupied and another acquisition exceeds its timeout
- **THEN** it fails within the configured bound without leaking a client
- **AND** closing the pool after releasing work terminates the process cleanly

#### Scenario: Connection loss and safe diagnostics
- **WHEN** a database connection breaks or insecure TLS configuration is supplied
- **THEN** the operation fails with safe diagnostics and a broken client is not returned as healthy
- **AND** no diagnostic includes a password or full DSN

### Requirement: Controlled migration history and privilege separation
The foundation SHALL use stable pinned `pg` and `node-pg-migrate` releases validated on Node 22, one migration history, a privileged bootstrap limited to disposable setup and a separate migrator identity. Runtime SHALL lack schema ownership, DDL, superuser, BYPASSRLS and elevating role memberships. Migrations SHALL run as a controlled separate process with locking enabled, never on each legacy API startup. Applied migrations SHALL remain immutable; failures SHALL NOT be bypassed with fake history or disabled locks.

#### Scenario: Empty database and previous test schema
- **WHEN** migrations run against an empty database and separately against a previously applied test migration prefix
- **THEN** both reach the expected schema/history without replaying applied migrations
- **AND** the runtime identity cannot create, alter or drop schema objects or bypass its privileges

#### Scenario: Concurrent migration runners
- **WHEN** two migration processes overlap while one holds the migration lock
- **THEN** at most one executes migrations and the other fails explicitly or waits according to documented configuration
- **AND** history contains each successful migration once

#### Scenario: Failure interruption and recovery
- **WHEN** a transactional migration fails or its process is interrupted before completion and is subsequently rerun
- **THEN** no partial migration is recorded as successfully applied
- **AND** locks are released on disconnection and rerunning reaches a consistent expected schema without manual history falsification

### Requirement: Synthetic owner isolation
The foundation SHALL demonstrate RLS using disposable fixtures with two synthetic owners and a real restricted runtime identity. Both read and write policies SHALL enforce owner isolation and missing context SHALL deny access. Owner context SHALL be transaction-local and installed by trusted server code. Fixture policies SHALL NOT be represented as validated production Recovery policies. Training-only consumer identities SHALL have no privileges on the protected fixture.

#### Scenario: Cross owner and missing context
- **WHEN** owner A reads or modifies B's rows, supplies B as a new row owner, or runtime operates without owner context
- **THEN** unauthorized reads expose no rows and unauthorized writes fail or affect no rows according to the operation
- **AND** an authorized same-owner write succeeds

#### Scenario: Connection reused after commit rollback or error
- **WHEN** the same pooled connection serves A, then B or a request without context, after commit, rollback or a failed transaction
- **THEN** no subsequent operation inherits A's context or can access A's protected rows

#### Scenario: Restricted consumer and non-row privileges
- **WHEN** a Training-only fixture role accesses protected tables or runtime attempts TRUNCATE, DDL or role elevation
- **THEN** PostgreSQL rejects the unauthorized action

### Requirement: Verifiable isolated backup and restore
The foundation SHALL demonstrate a consistent synthetic backup, authenticated encryption, transfer to a separate test destination and restore into a distinct disposable database. Keys SHALL remain separate from artifacts and logs. A manifest SHALL identify application revision, schema version, database/tool versions, integrity and recovery scope. Required roles/grants SHALL be provisioned explicitly and verified. Restore SHALL fail on integrity/decryption errors and SHALL NOT access the real deployment. Measured recovery time SHALL NOT be reported as production RPO/RTO compliance.

#### Scenario: Restore and verify
- **WHEN** a backup with synthetic data for both owners is encrypted, transferred and restored separately
- **THEN** semantic data, migration history, ownership, grants and RLS match expectations
- **AND** the source database remains unchanged and elapsed time and scope are recorded

#### Scenario: Corrupt artifact or wrong key
- **WHEN** an artifact has been altered or the wrong decryption key is used
- **THEN** restoration fails before applying unverified content

### Requirement: Real database CI and explicit gate evidence
CI SHALL exercise the foundation against real disposable PostgreSQL with no production credentials, including lifecycle, migrations, privileges, RLS and restore. Missing prerequisites SHALL fail explicitly rather than silently skip database proofs. CI triggers SHALL include foundation tooling and environment definitions. Existing relevant frontend/API/MCP suites, build and locale checks SHALL remain passing. The report SHALL distinguish synthetic results from provider validation and SHALL NOT claim G0, G2–G5 or operational G1 satisfied.

#### Scenario: Changed environment definition
- **WHEN** a pull request changes only the foundation environment or tooling definition
- **THEN** the foundation job is selected and runs its real database proofs

#### Scenario: Missing database or failed proof
- **WHEN** PostgreSQL is unavailable or a required foundation proof fails
- **THEN** CI fails and the evidence report identifies the missing or failed proof

#### Scenario: Synthetic success
- **WHEN** all synthetic proofs and legacy checks pass
- **THEN** the report records exact versions, commands and results while explicitly leaving untested provider and production recovery guarantees pending
