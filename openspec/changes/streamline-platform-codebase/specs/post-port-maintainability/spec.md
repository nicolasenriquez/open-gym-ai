## ADDED Requirements

### Requirement: Independent execution and current-state baseline
This change SHALL be independent of all other OpenSpec changes. Their completion, acceptance, archival or retirement MUST NOT be a prerequisite or a completion criterion. Scheduling after a platform port is a nonbinding preference. The executor SHALL record the current checkout, active runtimes/contracts, verification and permissions, preserving unrelated work. Missing evidence SHALL block only the affected unsafe action or unverified journey, not unrelated slices because another change remains unfinished.

#### Scenario: Another change remains unfinished
- **WHEN** another port or cleanup change is open but this slice has the required current code, permissions and verification
- **THEN** this slice can proceed when explicitly authorized without requiring completion or acceptance of the other change

#### Scenario: Active consumers still require transition tooling
- **WHEN** the baseline identifies active Node or transitional tooling consumers
- **THEN** their contracts and required artifacts remain intact and their presence does not block unrelated refactoring or documentation

### Requirement: Composition-independent compatibility metadata
Schema compatibility metadata SHALL have one pure authority consumed by HTTP composition and operational commands. Functional modules and operational commands MUST NOT import HTTP composition to obtain metadata. Runtime, migration and ops packaging and privileges MUST remain separated.

#### Scenario: Cleanup or backup checks schema compatibility
- **WHEN** a cleanup or backup command evaluates supported schema metadata
- **THEN** it obtains the same accepted metadata as HTTP composition without importing the HTTP composition module and still rejects an incompatible schema

### Requirement: Explicit atomic Training and Coach collaboration
The Training save collaboration SHALL declare its initiator, authorized participants, shared transaction and postcommit effects. Reorganization MUST preserve public results, permissions, revisions, consent and job/quota behavior. Failure of a transactional participant SHALL roll back the coordinated SQL changes; irreversible external effects MUST NOT precede the durable decision authorizing them.

#### Scenario: Coach participant fails while withdrawing consent
- **WHEN** a Training save reaches a failing transactional Coach participant
- **THEN** Training and related transactional changes are rolled back and authorized work is not cancelled as though the save had committed

#### Scenario: Successful save requiring job cancellation
- **WHEN** an authorized coordinated save commits a change that cancels a Coach job
- **THEN** the committed state and observable response preserve their contracts and the corresponding runtime cancellation occurs after commit

#### Scenario: Authorization changes during a wait
- **WHEN** authorization is revoked while a coordinated operation waits on its required lock
- **THEN** the operation revalidates authorization and cannot persist an unauthorized Training or Coach change

### Requirement: Single-authority frontend synchronization
Synchronization coordination SHALL be localized behind a cohesive interface without creating another persistent owner of the Training document, revisions, pending changes or profile identity. Pure training/session helpers SHALL remain colocated with their tests under the existing pure-helper convention. Error, offline and concurrency behavior MUST remain compatible.

#### Scenario: Lost reply and concurrent profile handover
- **WHEN** a pending save loses its reply and a profile or tab ownership handover occurs before retry
- **THEN** retry does not acknowledge unsaved changes falsely, overwrite a newer document blindly or send one owner's pending data as another owner's data

#### Scenario: Offline active session resumes with conflicts
- **WHEN** a session in progress has local pending changes and reconnects to a newer server revision with repeated conflicts
- **THEN** the current merge, lineage and pending-state guarantees survive and no second local authority is introduced

### Requirement: Incremental locality across six frontend capabilities
Training, Identity, Coach, Media, Administration and Notifications SHALL each have an independently reviewed slice with an ownership map, public interface, collaborators, state, failure cases and relevant tests. Feature-specific UI, hooks and clients SHALL be grouped where this reduces dispersal; shared transport and persistent state SHALL remain single authorities. Existing UX, localization, PWA/mobile, formats and public contracts MUST remain compatible.

Changed UI journeys SHALL exercise actual user actions and independently observe their persistent or authorized side effects. Existing executable browser coverage SHALL be reused before extending the current harness.

#### Scenario: Evidence exists without executing the required journey
- **WHEN** an expected screenshot or case name exists but the required UI action and independent observation were not executed
- **THEN** that journey remains unverified and its acceptance checkpoint does not pass

#### Scenario: Training and Identity slices are accepted
- **WHEN** Training/sync or Identity organization changes
- **THEN** tests preserve offline sessions, owner adoption, pending data, login/pairing and rejection/revocation behavior for the affected slice without introducing a feature-specific persistent store

#### Scenario: Coach and Media slices are accepted
- **WHEN** Coach or Media organization changes
- **THEN** tests preserve local/demo/HTTP selection and consent/Q6 constraints, or media queue/ownership/reference safety, respectively, including relevant failure paths

#### Scenario: Administration and Notifications slices are accepted
- **WHEN** Administration or Notifications organization changes
- **THEN** tests preserve actor-target permissions and administrative results, or device isolation/opt-out/ephemeral timers and web/mobile distinctions, respectively, without promising exactly-once push delivery

### Requirement: Discoverable ownership and enforceable dependency rules
Current documentation SHALL identify each capability's owner, interfaces, collaborators and targeted verification commands without duplicating authoritative rules. Existing verification and CI SHALL reject forbidden imports toward composition, functional dependencies from core and access to agreed private internals. Controls SHALL include negative fixtures and explicit treatment of local/dynamic imports; static checks MUST NOT substitute for behavioral verification of indirect collaboration.

#### Scenario: Forbidden dependency is introduced
- **WHEN** a fixture or proposed change introduces a forbidden dependency including a local import of HTTP composition
- **THEN** the architecture check fails with the offending dependency and does not require a new monorepo framework

#### Scenario: Agent locates a capability
- **WHEN** a maintainer or agent starts a change in any of the six capabilities
- **THEN** the existing entry points lead to its owning code, relevant rules and executable targeted checks and distinguish current implementation from historical evidence

### Requirement: Single initiator and one-way participant knowledge
The coordinated save SHALL have exactly one transaction initiator. The Training participant MUST NOT receive a Coach object or decide Coach policy; Coach SHALL own its consent, job and quota decisions and access Training only through declared public projections. Participants MUST NOT acquire another pool, commit independently or perform precommit runtime cancellation. Existing operations satisfying these conditions SHALL be reused without mandatory facade extraction.

The composition-owned Coach collaborator SHALL be explicitly injected into the save coordinator. The coordinator MUST NOT construct another Jobs instance or obtain it through global application state.

#### Scenario: Coordinator uses the application-owned collaborator
- **WHEN** an authorized save invokes Coach participation and subsequently commits
- **THEN** participation and postcommit cancellation use the injected collaborator without creating another worker or transaction

#### Scenario: Hidden reciprocal collaboration remains
- **WHEN** an import check passes but Training still invokes a supplied Coach object to coordinate the save
- **THEN** backend reorganization is not accepted until coordination belongs to the single initiator and Training and Coach participants satisfy their declared interfaces

### Requirement: Explicit dependency contract and bounded static analysis
Architecture checks SHALL use a reviewed map of concrete module ownership and public exports before enforcement. Core MUST NOT import functional modules; functional modules and operational commands MUST NOT import HTTP composition for metadata; cross-feature private imports and shared UI imports of features SHALL be rejected. Local imports and literal dynamic targets SHALL be covered; computed dynamic targets SHALL be reported as unverified pending explicit review. Passing static checks MUST NOT imply complete data-flow analysis or transactional correctness.

#### Scenario: Computed dynamic import is not decidable
- **WHEN** a computed import target prevents the check from establishing the dependency
- **THEN** verification reports the unresolved target for explicit review rather than silently crediting the dependency as permitted

#### Scenario: Public operation and private internal differ
- **WHEN** one fixture consumes a declared public projection and another consumes a private repository or undeclared internal of the same module
- **THEN** the first passes the relevant dependency rule and the second fails with the offending source and target

### Requirement: Per-journey proof and task traceability
Each task SHALL identify its requirement/scenario and observable check. Each runtime journey SHALL record the current exact command, cases, environment, observation seam and success/failure expectations before modification. Retired verifier commands SHALL be replaced with current native equivalents, not restored as legacy dependencies. Existing behavior-preserving refactors SHALL pass characterization before and after; a new rule SHALL include a negative proof. Six capabilities SHALL remain in scope but SHALL be delivered through bounded journeys with independent acceptance, not mandatory wholesale moves.

Each journey SHALL form a coherent reviewable change including required consumers and verification. Editorial removals SHALL remain distinguishable from executable changes. Overlapping journeys MUST NOT advance without recording the preceding checkpoint result.

#### Scenario: A subsequent journey overlaps unfinished changes
- **WHEN** the next journey modifies code or state whose preceding checkpoint is unverified
- **THEN** the overlapping journey waits while independent work may continue

#### Scenario: Retired verifier command is referenced
- **WHEN** a proposed proof command no longer exists after the port
- **THEN** the journey remains blocked until equivalent native verification is identified and recorded and the missing command is not reported as passed

#### Scenario: Capability already has adequate locality
- **WHEN** a journey's current ownership and interfaces already satisfy the specified separation
- **THEN** the executor records its consumers and passing behavioral proof without introducing empty layers or moving files merely to satisfy a directory quota

### Requirement: Final project documentation acceptance
After technical acceptance, stage 9 SHALL reconcile project documentation with the final code tree. Its inventory SHALL cover affected root and package guides, agent instructions, architecture, API, operations/recovery and deployment examples. Relevant claims SHALL be traceable to current source, contract or evidence; applicable documented commands SHALL be checked from a clean isolated checkout. Supported, pending and historical examples SHALL be distinguished. Structural documentation checks alone MUST NOT establish semantic acceptance, and any subsequent code change SHALL trigger revalidation of affected claims.

#### Scenario: Initial documentation becomes stale during refactoring
- **WHEN** stage 3 documentation passes but a later slice changes a path, interface, command or packaging assumption
- **THEN** stage 9 reconciles and verifies the affected documentation against the final revision and does not accept the earlier check as sufficient

#### Scenario: Required operational example cannot be verified
- **WHEN** an example requires real credentials, production data, hardware or a destructive operation outside this change's authorization
- **THEN** it is not executed on a real instance and its validation limit is explicit; missing evidence blocks any acceptance claim that requires it

#### Scenario: Final documentation check finds a contradiction
- **WHEN** active documentation contradicts the final runtime or references a retired artifact or broken command
- **THEN** documentation acceptance and final closeout remain blocked until the contradiction is resolved and affected checks pass
