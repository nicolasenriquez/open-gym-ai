## ADDED Requirements

### Requirement: Isolated reproducible Python environment
The Foundation SHALL run CPython/FastAPI and real disposable PostgreSQL independently of the ordinary API/web stack and the historical Node Foundation. It SHALL use exact stable versions, immutable image references, uv lock verification and recorded dependency licenses before runtime slices proceed. Local and CI execution SHALL use the same container entry point without host Python/PostgreSQL installation. No real environment, credentials, user state, personal media, public ports or Docker socket SHALL be supplied to test containers.

#### Scenario: Independent run from a clean checkout
- **WHEN** the operator runs the environment group with Node 22 and trusted Docker Compose v2
- **THEN** it builds/runs the pinned toolchain as non-root with private run-owned network, volume, tmpfs and synthetic configuration
- **AND** the ordinary API remains usable without PostgreSQL and neither Foundation shares its schema/history with the other

#### Scenario: Dependency resolution fails
- **WHEN** stable dependencies cannot resolve for the selected Python family or the lock/image/license verification fails
- **THEN** the prerequisite fails before runtime proofs are credited and no floating version or silent compatibility downgrade bypasses the failure

#### Scenario: Unsafe cleanup target
- **WHEN** cleanup receives a non-test project or any resource in its selected set has mismatched ownership, marker, service or name
- **THEN** it rejects the complete target set before deleting anything
- **AND** unrelated sentinel resources remain intact

### Requirement: Bounded Python database lifecycle
The Python application SHALL create and close its asyncpg pool through FastAPI lifespan. Database operations SHALL use finite acquisition, connection, command, SQL and shutdown limits. All transactional work SHALL use one leased connection. A failure before commit SHALL roll back when the connection permits; a SQL error that aborts the transaction SHALL prevent successful exit even if the caller catches that error. The interface SHALL distinguish acknowledged commit, confirmed rollback and unknown commit outcome. If commit has been sent but its outcome cannot be established, the interface SHALL report a safe machine-readable unknown outcome, discard the connection and SHALL NOT automatically retry or claim rollback. Unusable connections SHALL be discarded. Owner context SHALL be transaction-local and absent context SHALL grant no protected access. Expired transaction handles SHALL reject use. Cancellation SHALL propagate without falsely confirming either commit or rollback.

#### Scenario: Rollback and connection reuse
- **WHEN** a synthetic write fails or is cancelled before commit and a max-one pool serves the next owner
- **THEN** the failed write is absent and the next operation inherits neither transaction nor owner context
- **AND** the prior transaction handle cannot execute new work

#### Scenario: Caught SQL failure cannot confirm success
- **WHEN** a transaction writes a synthetic row, a later SQL statement aborts the transaction, and the caller catches that error and exits the transaction body normally
- **THEN** the transaction interface raises a safe transaction-aborted error instead of reporting success
- **AND** none of that transaction's writes persist, the handle expires and the next borrower inherits no owner or transaction context

#### Scenario: Commit response lost after server commit
- **WHEN** PostgreSQL commits a synthetic write but a controlled connection failure prevents the caller from receiving its commit acknowledgement
- **THEN** the interface reports an unknown commit outcome, discards the affected connection and does not retry the write or claim that it rolled back
- **AND** an independent restricted connection can observe the committed fixture row while the caller still receives no success confirmation
- **AND** cancellation during an unresolved commit propagates cancellation with the same machine-readable unknown outcome

#### Scenario: Saturation connection failure and shutdown
- **WHEN** the pool is saturated, a connection breaks or shutdown exceeds its configured grace period
- **THEN** operations fail within their documented limits, broken connections are not reused and the process terminates without leaked clients

#### Scenario: Invalid TLS or unsafe diagnostics
- **WHEN** unverified TLS settings or an unsupported connection option are supplied, or a database operation fails
- **THEN** configuration is rejected or the operation returns a safe stable error code
- **AND** errors and emitted diagnostics contain no DSN, credentials, SQL values or synthetic sensitive payload markers
- **AND** plaintext is allowed only for the explicitly identified private synthetic database

### Requirement: Foundation process health
The isolated app SHALL expose internal liveness and readiness separately. Readiness SHALL require both an accessible database and the expected Alembic revision, and SHALL fail without file fallback. These routes SHALL NOT replace or alter the current application health contract.

#### Scenario: Database or schema becomes unavailable
- **WHEN** the running Foundation loses database access or observes an incompatible schema
- **THEN** liveness remains 200 while readiness returns 503 with a non-sensitive code
- **AND** when database/schema compatibility returns, readiness can return 200 again

#### Scenario: Startup and graceful stop
- **WHEN** startup cannot connect within its limit or a started Uvicorn process receives termination
- **THEN** startup fails explicitly or lifespan closes the pool within the shutdown deadline, respectively

### Requirement: Serialized Alembic history and privilege separation
The Foundation SHALL use Alembic as its sole schema migrator with a separate migrator identity and a bootstrap restricted to disposable setup. Runtime SHALL have no schema ownership, DDL, superuser, BYPASSRLS, unnecessary public privileges or elevating role memberships. A dedicated connection SHALL hold a session advisory lock from before inspecting migration history until execution completes. Migrations SHALL run as a controlled separate process, never inside normal app startup. Applied revisions SHALL be immutable; fake history, stamp and disabled locking SHALL NOT be exposed as recovery actions. Infrastructure migrations SHALL NOT create identity, Training or Recovery domain tables.

#### Scenario: Empty database previous revision and rerun
- **WHEN** migrations run from empty and from a previous synthetic revision prefix, then run again
- **THEN** both paths reach the same expected schema/history without replaying applied revisions
- **AND** unknown revision history fails explicitly rather than being stamped as valid
- **AND** runtime cannot perform DDL or elevate privileges

#### Scenario: Concurrent runners
- **WHEN** two migration processes overlap while one owns the migration lock
- **THEN** only the owner applies migrations and the other fails explicitly
- **AND** each successful revision appears once

#### Scenario: Transactional failure interruption and recovery
- **WHEN** a transactional migration fails, is terminated or loses its database connection before completion
- **THEN** no partial work is recorded as successfully applied and the session lock is released on disconnect
- **AND** rerunning reaches the expected state without manual history fabrication

### Requirement: Real restricted-role owner isolation
Disposable fixtures SHALL demonstrate ENABLE/FORCE RLS, USING/WITH CHECK ownership enforcement, missing-context denial and transaction-local context installed by trusted code. Tests SHALL exercise real restricted runtime and Training-only consumer logins. Privileged SQL SHALL be limited to fixture setup and metadata inspection, not used to claim authorized runtime behavior. Fixture policies SHALL NOT be presented as HTTP authorization or production Recovery policies.

#### Scenario: Ownership and privilege matrix
- **WHEN** A/B runtime owners read or mutate protected rows, forge a new row owner, omit context, or a Training-only consumer accesses the fixture
- **THEN** same-owner permitted operations succeed and unauthorized reads expose no rows or writes fail/affect no rows as appropriate
- **AND** TRUNCATE, DDL and role elevation are denied

#### Scenario: Reuse after every transaction outcome
- **WHEN** one physical pooled connection serves A followed by B or missing context after commit, rollback, SQL error, timeout or cancellation
- **THEN** no later operation obtains A's protected access or context

### Requirement: Authenticated isolated synthetic recovery
The Foundation SHALL demonstrate consistent pg_dump backup, authenticated encryption, transfer excluding the separate key and restore into a distinct verified empty disposable database. A versioned authenticated manifest SHALL identify application revision, Alembic history, database/tool versions, checksum, required roles and recovery scope. Wrong key, altered content, unsafe paths or unowned/nonempty destinations SHALL fail before unverified content is applied. Roles/grants SHALL be provisioned explicitly and the restored data, history, ownership and RLS SHALL be verified through restricted interfaces. Source state SHALL remain unchanged. Durations and same-cluster/small-fixture limits SHALL be reported without production RPO/RTO, PITR or off-host claims.

#### Scenario: Restore and semantic verification
- **WHEN** a two-owner synthetic fixture is backed up, encrypted, copied and restored separately
- **THEN** restricted-role queries demonstrate equivalent data and owner isolation, and metadata confirms history/ownership/grants
- **AND** the transfer contains neither plaintext nor key and the source remains unchanged

#### Scenario: Tampered bundle or wrong key
- **WHEN** ciphertext, authenticated manifest or key is incorrect
- **THEN** restore rejects the bundle before connecting to the destination and leaves it unchanged

#### Scenario: Unsafe path destination or failed restore
- **WHEN** a path traverses outside the private artifact root, uses a symlink, would overwrite an artifact, or restore targets the source/unowned/nonempty database
- **THEN** the operation fails before modifying the unsafe target
- **AND** an execution failure during a valid restore reports the target unusable rather than returning partial success

### Requirement: Required real-database verification and honest gate evidence
CI SHALL run the same Foundation entry point as local verification, including contract cases, static/lock checks, real PostgreSQL lifecycle/migrations/RLS/recovery and unsafe-target/missing-database regressions. Changes to tooling, environment, capabilities and this change SHALL select the job. Missing prerequisites, skipped required proofs, failed tests or cleanup SHALL fail the run without continue-on-error. Existing pertinent API/frontend/MCP/build/locale checks SHALL remain supported. Evidence SHALL identify revision, versions, commands, results and limits, and SHALL separate historical Node, new synthetic Python and pending operational gates. Diagnostics SHALL be structured, bounded and scanned for sensitive synthetic markers.

#### Scenario: Environment-only change and unavailable database
- **WHEN** only the Foundation Compose/tooling definition changes
- **THEN** CI selects the mandatory real-database job
- **AND** an explicit execution without PostgreSQL fails instead of skipping tests or crediting proofs

#### Scenario: Completed synthetic verification
- **WHEN** all required proofs and compatibility checks pass
- **THEN** the delivery records reproducible commands and fresh synthetic results while leaving G0, operational G1, GP, GO, G2/G3 and later Recovery gates pending
- **AND** health/logging alone is not reported as EV-08 or platform acceptance
