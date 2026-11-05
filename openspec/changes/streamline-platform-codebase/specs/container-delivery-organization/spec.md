## ADDED Requirements

### Requirement: Owned build recipes without arbitrary consolidation
Container delivery SHALL inventory recipe owner, context, effective ignore policy, targets, consumers and purpose. Product Dockerfiles SHALL remain with their product; active cross-product browser/security recipes and diagnostic delivery SHALL use deploy ownership per D10. Separate dependency/privilege lifecycles SHALL remain separate. Active transitional recipes SHALL preserve required consumers and isolation; their operational retirement is outside scope and MUST NOT be required for this change. No file count quota or single-image consolidation SHALL determine acceptance.

#### Scenario: Browser verification recipe is reorganized
- **WHEN** an active cross-product browser recipe moves from backend to deploy ownership
- **THEN** all build/CI/verifier consumers and its specific ignore are updated together while root context and browser isolation remain explicit

#### Scenario: Transition recipe is already retired
- **WHEN** baseline inspection finds a transition recipe already removed
- **THEN** inventory records retirement and this change does not recreate the recipe to match an old tree

### Requirement: Minimal effective contexts preserve required inputs
Every active recipe SHALL have verified required COPY inputs and excluded private/host artifacts under its actual build invocation. Specific ignores SHALL be evaluated with their precedence over root ignores. Relocation MUST NOT expose credentials, envs, user data, scratch, host dependencies or previous output, or silently omit required fixtures/shared sources.

#### Scenario: Relocation changes effective inputs
- **WHEN** a required input becomes unavailable or a private sentinel enters the effective context
- **THEN** synthetic context proof fails and a successful YAML render does not satisfy acceptance

### Requirement: Reproducible input policy and minimal runtime
Runtime SHALL preserve non-root execution and separation from test tools, Node backend, migration privileges and operational-only tools. Bases SHALL use reviewed immutable identities and an update policy. Locks SHALL be enforced, dependency layers SHALL precede source layers where applicable and cache claims SHALL use build evidence. Base pinning MUST NOT imply bit-for-bit reproducibility of unpinned package repository operations.

#### Scenario: Cache and lock behavior are verified
- **WHEN** cold, repeated, source-only and lock-changing builds run
- **THEN** actual dependency steps establish cache behavior, incompatible locks fail and runtime inspection confirms no privileged/test tooling leaked

#### Scenario: Mutable web base is resolved
- **WHEN** a web base or package source could change between builds
- **THEN** reviewed base identity and actual package inputs are recorded with an update policy without unproven identical-output claims

### Requirement: Compose relocation preserves operational identity
Dev, prod, test and prod-plus-maintenance SHALL have documented invocations and a canonical project directory. Rendered models SHALL preserve ports/networks, resource names, secret access, roles, logging, healthchecks and readonly/user/capability restrictions. Production MUST NOT inherit source mounts/reload/runtime installs. Relocation MUST NOT invalidate persistent volumes or registered configuration/journals. API MUST NOT migrate at startup; existing migration sequencing and readiness SHALL remain verified.

#### Scenario: Recipe paths change
- **WHEN** configurations render before and after relocation with synthetic values
- **THEN** differences are limited to reviewed recipe locations and immutable build inputs, API/DB remain private and resource identities/maintenance contracts remain unchanged

#### Scenario: Migration fails or database later goes down
- **WHEN** migration fails before activation or database becomes unavailable after startup
- **THEN** the entrypoint does not grant compatible API readiness falsely and runtime recovery preserves its contract without startup DDL

### Requirement: Isolated container proofs before documentation acceptance
Container acceptance SHALL cover effective contexts, targets, rendered models, runtime isolation and affected cache/lifecycle/maintenance proofs on owned synthetic resources. Unavailable Docker/Buildx access SHALL be a verification blocker, not a recipe defect or passing proof. AI Tutor SHALL remain an inspected reference, not a required checkout/runtime dependency. Stage 9 SHALL verify the final delivery layout after container acceptance.

#### Scenario: Docker access is unavailable
- **WHEN** rendering passes but image/context proofs cannot run because Docker or Buildx access is denied
- **THEN** render results are separate and container acceptance remains incomplete until required proofs run in an authorized environment

#### Scenario: Active guide still requires the old recipe
- **WHEN** image proofs pass but an active build/CI/operational guide still requires a removed recipe path
- **THEN** stage 9 and final closeout remain blocked until that consumer is corrected and verified
