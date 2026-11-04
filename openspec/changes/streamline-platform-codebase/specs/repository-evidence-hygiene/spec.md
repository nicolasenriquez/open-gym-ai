## ADDED Requirements

### Requirement: Change-owned planning and evidence
Planning, tasks, decisions and necessary evidence SHALL be self-contained in the selected OpenSpec change. Agent tracker templates SHALL route to those artifacts without creating parallel tickets, maps or scratch directories. Disposable execution files SHALL use exclusive system temporary directories; necessary results SHALL be consolidated in the change and obsolete owned files removed. Historical provenance and exclusion sentinels MUST NOT be interpreted as instructions to recreate retired task directories.

#### Scenario: A skill requests a local ticket or experiment report
- **WHEN** work already belongs to an OpenSpec change
- **THEN** the agent updates the owning artifacts and retains only necessary evidence there instead of creating a scratch tracker or permanent execution dump

### Requirement: Purpose-based cleanup selection
Cleanup SHALL classify each candidate as retain, consolidate or remove, recording its exact scope, owner, purpose, consumers and reason in the existing task or review. Retained execution evidence SHALL state its outstanding obligation and removal condition. Age, filename, size, ignored status or a completed task checkbox alone MUST NOT authorize removal. Cleanup SHALL be a reviewed operation, not a new periodic garbage collector.

#### Scenario: Old proof still supports open acceptance
- **WHEN** an old log, capture or synthetic export is the required evidence for an open review, acceptance or unresolved regression
- **THEN** it is retained with its purpose and removal condition until the obligation is resolved or independently adequate evidence replaces it

#### Scenario: Superseded owned execution proof
- **WHEN** an owned execution artifact has no active consumers, retention obligation or remaining verification purpose and its writers have stopped
- **THEN** only the reviewed artifact is eligible for removal and useful results or limitations remain in the owning task rather than a new permanent cleanup report

### Requirement: Reviewed historical document retirement
Protected historical material SHALL be eligible for case-by-case retirement only after consumers, remaining requirements, decisions and evidence have been reviewed and necessary knowledge preserved in its owning source. Active links, indexes, configuration and historical manifests SHALL be updated consistently. A retained historical body MUST NOT be rewritten and rehashed merely to make checks pass. Archived OpenSpec decisions and outstanding task traceability MUST remain available.

#### Scenario: Protected research still owns a decision source
- **WHEN** a protected historical document remains necessary to explain an active decision and no adequate owner source preserves that knowledge
- **THEN** cleanup retains the document rather than treating protection or age as a reason to force deletion

#### Scenario: Historical material is demonstrably redundant
- **WHEN** reviewed historical material has no remaining obligation or consumer after necessary knowledge and links are migrated
- **THEN** its explicit retirement updates the corresponding indexes, configuration and manifest in the same change and does not rewrite Git history or fabricate historical evidence

### Requirement: Value-based code comment maintenance
Maintained first-party source SHALL contain no narrative comments, commented-out code or purely explanatory docstrings after its cleanup slice is accepted. Current invariants, race conditions and regressions SHALL be expressed through names, interfaces, validation and distinguishing executable tests before their explanation is removed. Necessary textual contracts and external constraints that cannot be encoded SHALL have a discoverable owning document. Cleanup MUST NOT copy all removed prose into another document or silently discard unresolved TODO/shortcut obligations.

Licenses and attribution SHALL remain preserved. Effective tool directives and observable docstrings SHALL be classified separately from narrative prose and retained until an equivalent configuration or explicit API is verified. Any remaining technical exception SHALL identify its exact scope, consumer and reason. Correctness suppressions SHALL require a root-cause fix or demonstrated false positive, rather than automatic exemption. Editorial removal MUST NOT change executable behavior.

#### Scenario: Comment explains a live data-loss invariant
- **WHEN** a narrative comment explains ownership, merge or concurrency behavior preventing data loss
- **THEN** the slice identifies or adds an executable test that distinguishes the violating behavior, gives necessary textual context an owning document and removes the narrative only after the guarantee is preserved

#### Scenario: Redundant narrative and postcommit invariant coexist
- **WHEN** a slice contains a comment narrating an obvious assignment and another explaining that postcommit bookkeeping cannot change acknowledged success
- **THEN** both narrative comments are removed after the postcommit guarantee has distinguishing proof and the code and owning contract express its ordering without changing the acknowledged result

#### Scenario: A comment-shaped token controls execution
- **WHEN** a candidate is a Vitest environment directive, Docker parser directive, shebang, build pragma or a docstring consumed as an observable contract
- **THEN** cleanup verifies an equivalent replacement before removal or records an exact technical exception and does not claim it was harmless prose

### Requirement: No retained superseded implementations
The maintained source and delivered build contexts SHALL NOT retain executable copies of superseded implementations, including copies renamed as legacy, archive or compatibility facades without active purpose. Retirement SHALL migrate active consumers and preserve independently required regression expectations without executing the retired server. Repository history MAY retain removed source. Active supported compatibility transformations and operational import tooling MUST be distinguished from dead implementations; their removal SHALL require an explicit support decision and corresponding owning specification changes when observable contracts change.

#### Scenario: Retired Node code is kept under another directory
- **WHEN** a change copies retired Node HTTP handlers into a legacy or archive source directory for future reference
- **THEN** source retirement acceptance fails even if the directory is excluded from the runtime image

#### Scenario: Old offline documents still have an active reader
- **WHEN** the current store consumes an old-format transformation to preserve pending offline edits
- **THEN** the transformation is not treated as dead code and any proposed removal identifies its support cutoff and migration or rejection behavior before changing the contract

#### Scenario: Source is retired but ignored local residues remain
- **WHEN** Git contains no retired implementation but the workspace contains ignored artifacts from prior work
- **THEN** the audit reports those categories separately and filesystem removal still requires bounded ownership and path checks

### Requirement: Bounded safe artifact removal
Artifact removal SHALL resolve exact absolute targets and real paths, confirm ownership and stopped writers, preserve foreign/concurrent work and exclude user data, credentials, backups, recovery journals and protected material still required by policy. Symlink/junction escapes SHALL block removal. Broad document retirement SHALL preserve required untracked/local work in a private external backup with a path/hash inventory. Container resources SHALL use their owning verifier; filesystem cleanup MUST NOT imply global Docker cleanup.

#### Scenario: Candidate escapes task scope or belongs to another task
- **WHEN** a target resolves outside its authorized owned directory through a link, is foreign, has active writers or has uncertain ownership
- **THEN** it is not removed and the uncertainty is reported without expanding cleanup scope

#### Scenario: Foreign sentinel and recovery material are present
- **WHEN** reviewed obsolete task artifacts are cleaned in a disposable fixture containing a foreign sentinel and protected recovery material
- **THEN** only eligible owned artifacts disappear and the foreign sentinel and protected material remain byte-for-byte intact

### Requirement: Cleanup preserves reproducible guarantees and active navigation
Cleanup SHALL retain executable regression tests and independent fixtures needed for supported behavior, even when they originate in past implementations. It SHALL validate incoming references outside docs, affected generators/builds/tests, documentary truth and the configured documentation checks. Operational cutover is outside this change and retirement by another change MUST NOT be assumed or required; this change MUST NOT replace missing native coverage with prose or copy obsolete dumps into a different directory.

#### Scenario: Old implementation proof is actually a regression test
- **WHEN** a candidate is an executable test or independent known-answer fixture still protecting a supported guarantee
- **THEN** cleanup preserves the guarantee and cannot delete it as an old proof without equivalent reviewed coverage

#### Scenario: Retirement leaves a stale consumer
- **WHEN** an instruction, OpenSpec reference, generator, test or build still needs a proposed removal candidate
- **THEN** retirement completion is blocked until the consumer is migrated or the candidate is retained and relevant checks pass

### Requirement: JSON purpose classification and active contract preservation
JSON artifacts SHALL be classified by consumers and guarantees as runtime data, independent native fixtures, transitional comparison tooling or disposable execution evidence. Runtime assets and necessary known-answer fixtures MUST NOT be removed by extension, size or Node provenance alone. This change SHALL inventory actual consumers and reconcile retention guidance with current guarantees. Active contracts SHALL remain until an explicitly scoped removal has independent replacement coverage and no remaining consumers. An unfinished external change MUST NOT block entry. A new hygiene subsystem MUST NOT be required for editorial cleanup.

#### Scenario: Large generated Coach data is selected as old proof
- **WHEN** a generated JSON supplies the runtime exercise catalogue, prompts or validation schemas
- **THEN** cleanup preserves its canonical sources and generator checks and does not delete it as an execution artifact

#### Scenario: Retention guide conflicts with accepted retirement
- **WHEN** an active guide still instructs retaining transitional comparison contracts while another active guide requires removal
- **THEN** guidance is reconciled with actual consumers and guarantees; only the affected deletion remains blocked until coverage is adequate, while unrelated slices stay independent

#### Scenario: Independent fixture contains old implementation provenance
- **WHEN** a readable bounded fixture has independent expected values and tests a supported guarantee but cites a retired implementation as its origin
- **THEN** provenance is retained and any reduction preserves independent expectations and coverage without copying full dumps or deriving expectations from the implementation under test
