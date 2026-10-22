## ADDED Requirements

### Requirement: Versioned capability and consumer reference
The change SHALL record a characterization matrix covering architecture section 9.1: HTTP/OpenAPI, identity/access/passwords/sessions, Training/sync and local/offline client state, administration/push/audit, catalogue/media/import/export, coach and MCP. Each entry SHALL identify producers, consumers, stores, current authority, observable contract, source revision, fixtures/test commands, coverage limits and the future parity gate. Every affected store SHALL have an explicit proposed disposition: replace, retain with justification or retire. Inventory alone SHALL NOT be reported as executed parity evidence.

#### Scenario: Complete baseline inventory
- **WHEN** the reference matrix is reviewed before the Python capability port
- **THEN** every required area and its persistent, in-memory, client, secret or media state is accounted for with a source and verification entry
- **AND** untested provider/client behavior and future migration decisions are identified without claiming GP or G0 satisfied

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
