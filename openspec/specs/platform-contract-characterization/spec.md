# Platform contract characterization

## Purpose

Define the versioned synthetic reference cases and consumer handoff used to preserve the existing Node/JSON product while preparing a later Python capability port. Characterization does not establish Python parity, operational acceptance or production recovery.

## Requirements

### Requirement: Approved schema and operation handoff
The Foundation documentation handoff SHALL reference the approved platform SQL schema, security and local operation contracts and the separate planned port-compatible-platform change. It SHALL distinguish target tables/relationships/indexes, session and MCP policies, roles, private local topology and recovery objectives from executed Foundation evidence. It SHALL NOT implement business tables, credentials, backup scheduling or cutover, reopen completed characterization tasks or credit functional/operational acceptance from this handoff.

#### Scenario: Consolidated decisions stay outside synthetic delivery
- **WHEN** the pending Foundation closeout documentation is prepared
- **THEN** it identifies the separate port/operation owner, contract references and still-pending DDL/parity/restore/cutover evidence
- **AND** previously completed characterization retains its original scope and the future runtime tasks remain pending in their own change

### Requirement: Versioned capability and consumer reference
The change SHALL record a characterization matrix covering architecture section 9.1: HTTP/OpenAPI, identity/access/passwords/sessions, Training/sync and local/offline client state, administration/push/audit, catalogue/media/import/export, coach and MCP. Each entry SHALL identify producers, consumers, stores, current authority, observable contract, source revision, fixtures/test commands, coverage limits and the future parity gate. Every affected store SHALL have an explicit proposed disposition: replace, retain with justification or retire. Inventory alone SHALL NOT be reported as executed parity evidence.

#### Scenario: Complete baseline inventory
- **WHEN** the reference matrix is reviewed before the Python capability port
- **THEN** every required area and its persistent, in-memory, client, secret or media state is accounted for with a source and verification entry
- **AND** untested provider/client behavior and future migration decisions are identified without claiming GP or G0 satisfied

### Requirement: Functional ownership and frontend correspondence
The characterization matrix SHALL associate each required area with its proposed owning Python module, existing frontend views/components/hooks or store/helpers where applicable, current transport and persistence authority, and intended public collaborations. Areas without a frontend participant SHALL state that fact. The map SHALL preserve current file locations and distinguish future organization from implemented code. It SHALL provide a reusable handoff for colocated contracts, business operations and queries without requiring a frontend rewrite, new dependencies or business implementation in Foundation.

#### Scenario: Trace an existing capability into the modular port
- **WHEN** a maintainer follows a characterized case such as Training read and save
- **THEN** the matrix identifies its source contract and case, future owner, current client path and data authority, and relevant positive and failure behavior
- **AND** cross-module access is planned through authorized public interfaces instead of another module's repository or tables
- **AND** missing integration or client evidence is recorded as pending rather than credited from a directory map or documentation validation

### Requirement: Runtime-neutral JavaScript preservation handoff
The handoff SHALL inventory runtime-neutral JavaScript currently under `api/coach/core`, its frontend imports and dynamic loads, test/build consumers and generated prompt/catalogue inputs. It SHALL identify `shared/coach-core` as the subsequent canonical JavaScript location, with one editable JS source and independent Python compatibility vectors. Foundation SHALL preserve current locations and Node reference behavior. Relocation, generator/build updates, local coach compatibility and removal of active legacy-tree dependencies SHALL be acceptance requirements for the subsequent port and retirement, not reported as completed here.

#### Scenario: Preserve local coach before legacy removal
- **WHEN** Foundation prepares the port and retirement handoff
- **THEN** it records frontend coach-local and setup consumers, Vite/web Docker build inputs, relevant asset generators and tests with their planned disposition
- **AND** the later port must prove current web and pertinent mobile bundles plus local coach compatibility without imports from the retired API tree before that tree is removed
- **AND** a remaining runtime-neutral JavaScript library is distinguished from a permanently required Node business API

### Requirement: Reproducible synthetic contract cases
Characterization SHALL run against the real Node implementation and existing client/MCP public interfaces using only disposable synthetic state. It SHALL preserve inputs and independent expected results with stable case identifiers reusable by the future port. Existing behavioral suites SHALL be reused; additional tests SHALL cover gaps rather than duplicate internals. At least one successful and one negative case SHALL be executed per required area; public or unprotected areas SHALL use an applicable invalid-input/failure case. External push/coach transport SHALL use fixtures without contacting accounts or providers.

#### Scenario: Current behavior reproduced without personal state
- **WHEN** the contracts group executes from a clean checkout
- **THEN** HTTP cases start Node with temporary DATA_DIR and synthetic credentials, and client/MCP cases execute their identified fixtures
- **AND** results identify cases, source revision and commands without loading the instance environment or personal data

#### Scenario: Meaningful compatibility difference detected
- **WHEN** the comparator receives a synthetic response deliberately changed in status, payload types, missing versus null, ownership, semantic headers/cookies or Training stamps relative to an independent expected result
- **THEN** the case fails instead of regenerating expectations or normalizing that difference away
- **AND** only explicitly enumerated volatile fields such as a nonce, clock or temporary port can be normalized
- **AND** the unchanged current Node baseline is verified separately and is allowed to pass on its first run without manufacturing a legacy application failure

### Requirement: Characterization preserves the existing product
The change SHALL leave existing HTTP routes, authentication, Training rules, offline/guest behavior, media and consumer authority unchanged. Characterization SHALL distinguish observed current behavior from documented intent and future Python compatibility. Conflicting evidence SHALL be recorded and resolved for a reference case, without silently changing the legacy application or declaring an untested Python capability compatible.

#### Scenario: Reference and intended contract disagree
- **WHEN** a source document and an observed Node case disagree
- **THEN** the matrix records the discrepancy and the chosen current-reference expectation with evidence
- **AND** any intentional behavior change is deferred to an explicitly scoped later change

#### Scenario: Port handoff
- **WHEN** this change completes
- **THEN** the matrix and reproducible cases are available to the Python port while production still uses its original Node and file authorities
- **AND** session continuity, Python WebAuthn/provider compatibility, full GP and post-cutover acceptance remain explicitly unproven
