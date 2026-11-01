## ADDED Requirements

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
Comment cleanup SHALL remove literal restatements, false references and obsolete implementation chronology while preserving or sharpening current rationale, invariants, race conditions, compatibility constraints, relevant regression explanations and unresolved obligations. Licenses, attribution and effective lint/type/build/coverage directives MUST remain intact unless their removal is separately justified and verified. Removing TODO or shortcut text MUST NOT silently discard an unresolved obligation. Runtime behavior MUST remain unchanged by editorial cleanup.

#### Scenario: Historical QA comment explains a live data-loss risk
- **WHEN** an old QA comment still explains ownership, merge or concurrency behavior preventing data loss
- **THEN** its current rationale is retained or condensed and is not deleted solely because its version/date is old

#### Scenario: Redundant narrative and postcommit invariant coexist
- **WHEN** a slice contains a comment narrating an obvious assignment and another explaining that postcommit bookkeeping cannot change acknowledged success
- **THEN** the redundant narrative may be removed while the postcommit invariant remains clear and executable behavior is unchanged

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
