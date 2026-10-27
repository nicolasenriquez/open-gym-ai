## ADDED Requirements

### Requirement: Exclusive Python HTTP API v1
The Python platform SHALL expose all HTTP routes under `/api/v1`, including `/api/v1/health/live` and `/api/v1/health/ready`. It SHALL NOT expose unversioned aliases or redirects. The shared frontend SHALL select `/api/v1` at build time for Python and retain the existing `/api` contract for Node. Internal probes SHALL remain inaccessible through nginx. Swagger, ReDoc and HTTP OpenAPI endpoints SHALL remain disabled. Frozen Node fixtures SHALL remain unchanged; behavioral parity SHALL account explicitly for the Python URL prefix.

#### Scenario: Versioned Python request and removed previous URL
- **WHEN** a consumer calls an implemented Python operation under `/api/v1`
- **THEN** the operation preserves its existing authorization, payload, error and persistence behavior
- **AND** the former unversioned URL returns 404 without redirect, including preflight requests

#### Scenario: Python frontend and internal readiness
- **WHEN** a Python frontend is built and the platform starts
- **THEN** all client transports target `/api/v1`, and Compose checks `/api/v1/health/ready`
- **AND** nginx refuses public access to both internal probes

### Requirement: Phase-bounded compatible capability port
The platform SHALL port the current capabilities into the approved Python modular monolith, preserving the existing frontend, local/offline Training, catalogue, formats, access and authorized consumers. It SHALL use the approved platform-schema reference as the physical contract and platform-modularity as ownership authority. Each slice SHALL identify contracts, actor/resource permissions, owning tables/stores, public collaborations, transaction scope and existing client path. Business implementation SHALL follow the archived Foundation acceptance and explicit slice authorization; this specification SHALL NOT credit implementation or treat Foundation evidence as delivery of business tables.

Before delivery, each slice SHALL have a bounded behavioral task sequence, an independent first failing proof for new runtime behavior, an observable checkpoint and exact focused verification commands. The verification harness SHALL reuse the consolidated Platform verifier's execution and ownership mechanisms (`scripts/platform.mjs` and `scripts/synthetic-harness.mjs`) without sharing instance configuration. Suite/case mappings and test images SHALL be delivered incrementally with their slice; unknown or undelivered suites SHALL fail with exit 2, never count as passed/skipped. Shared-tooling extraction SHALL preserve the retained Platform regression coverage and exact resource ownership. Changes to admitted capabilities, clients, authorization guarantees or recovery objectives SHALL require promoter approval rather than being treated as technical implementation choices. Retired MCP SHALL NOT cause creation of consumer-token tables or adapters.

#### Scenario: Slice preparation is incomplete
- **WHEN** a proposed slice lacks executable verification, permission/error cases or a resolved material compatibility question
- **THEN** its delivery remains blocked while technical investigation and specification refinement proceed within their authorized scope
- **AND** another prepared slice does not authorize the whole transition or silently approve new test seams

#### Scenario: Training pilot follows identity
- **WHEN** the first functional Training slice is prepared
- **THEN** it requires compatible identity and declares HTTP, schemas, operation/repository, owner transaction, client reconciliation and positive/failure evidence
- **AND** public collaborators share the initiating transaction without independent commits or cross-module repository access

### Requirement: Legacy-compatible identity namespace and credentials
Identity SHALL preserve textual IDs, nonunique display names, normalized login aliases, optional passwords, WebAuthn material/counters, one-time links, invitations and signed session/version behavior. Alias claims SHALL prohibit cross-owner name/email collisions while allowing both purposes for the same owner, retaining email claims without passwords and releasing only expired temporary reset reservations transactionally. It SHALL preserve sessions when safe/compatible; exceptional reauthentication SHALL be documented and proven without clearing client pending state. Consumed invitations SHALL remain consumed after account deletion.

#### Scenario: Concurrent alias reservation and reset expiry
- **WHEN** two owners claim the same normalized name/email or a reset-only reservation expires
- **THEN** serialization and constraints prevent conflicting ownership and only an actually expired temporary claim can be released
- **AND** display-name duplicates remain valid without credentials and legacy Unicode/login lookup behavior is preserved

#### Scenario: Credential and account access continuity
- **WHEN** legacy credentials/sessions are ported and password/reset/revocation operations run
- **THEN** independent vectors prove formats, counters, expiry, disabled-account rejection and version revocation
- **AND** passkey limits, last-way-in protection and one-time link consumption survive concurrent requests

### Requirement: Executable schema and privileged functions
Delivery SHALL implement the schema reference's ordered p001–p005 Alembic chain incrementally with its owning operation, including exact constraints, generated projections, FK deletion rules, indexes and explicit function grants. The security reference's typed SQL catalog, executor policies and global lock order SHALL govern preauthentication, administration and global coach/notification operations. Functions SHALL NOT accept arbitrary SQL, roles or table names; SECURITY DEFINER SHALL NOT be treated as bypassing FORCE RLS. DDL and data import SHALL remain separate, with forward-only operational repairs and no artificial stamp or destructive downgrade. Each privileged function SHALL justify its bounded access and atomic invariant; Python SHALL own transport, cryptography and coordination while SQL owns constraints and privileged concurrent invariants. No second independent implementation of the same business rule or function added solely for module symmetry SHALL be introduced. Reducing a signature SHALL require equivalent permission/concurrency/response proof, not broader runtime grants. This revision does not change approved roles, signatures or RLS.

#### Scenario: Migration failure and function grants
- **WHEN** migration is attempted from empty/previous head, interrupted or raced by another migrator, or runtime invokes privileged SQL
- **THEN** the dedicated lock bounds concurrency, failed revisions do not advance history and runtime cannot assume owner/executor roles or execute ungranted functions
- **AND** real metadata and behavior prove safe function owners/search_path/ACL, generated-column type rejection and explicit RLS policies, including backup visibility without runtime bypass

#### Scenario: Existing administrative Training projection is preserved
- **WHEN** an active administrator requests the current user list or user drill-down
- **THEN** explicit actor/target authorization permits exactly the legacy summary/history projection through Training's interface, without impersonating target owner
- **AND** media references, internal document metadata, credentials and future Recovery data are not exposed; non-admin and revoked actors are denied

### Requirement: Canonical compatible Training persistence
Training SHALL store the full compatible document as canonical JSONB with revision/write-id GENERATED STORED projections, validated without rounding or converting incompatible legacy types. It SHALL preserve missing versus null, internal stamps/lineage/reset metadata, allowed legacy writes, conflicts and local active-session behavior. The initiating transaction SHALL serialize by owner including an absent first document, revalidate access, compare bases and commit one document update.

#### Scenario: First write and competing revision
- **WHEN** concurrent writers target an absent document or send a stale baseRev/baseWid
- **THEN** owner serialization and existing conflict behavior prevent silent overwrite
- **AND** revision/write-id derive from the committed document, including the legacy response-versus-stored revision distinction

#### Scenario: No document and legacy metadata
- **WHEN** a user has no document or a full internal legacy document is imported
- **THEN** no document remains state null/revision zero and import preserves all required metadata and semantic types
- **AND** client offline/pending/active state is preserved and no general JSONB index or normalization is required

### Requirement: Compatible notification and coach state
The platform SHALL preserve push endpoint/device semantics, ownership, limits and local delivery dates while leaving preferences in Training. Coach SHALL separate settings, current jobs, pending proposals, history events and UTC usage counters according to the physical contract. Enqueue SHALL atomically enforce caps and count usage with job creation. It SHALL preserve single-flight, two global executions in the initial runtime, bounded 20-event personal/100-result instance history, lazy proposal expiry and no automatic replay after restart.

#### Scenario: Notification ownership and local dates
- **WHEN** subscription upsert, reminder/nudge delivery or activity/rest-timer operations run for authorized owners and devices
- **THEN** endpoint transfer, original creation date, valid device fallback, cap 20 and SSRF protections preserve their current contracts, while foreign unsubscribe/timer cancellation is denied
- **AND** local dates and Training preferences govern internal delivery, failures remain observable and process restart does not invent durable presence/timers or exactly-once external delivery

#### Scenario: Atomic limits and repeated job events
- **WHEN** concurrent enqueue attempts approach user/instance limits and a proposal later becomes applied/dismissed/expired
- **THEN** committed counters and current jobs remain consistent and multiple events may reference the same job without overwriting each other
- **AND** a restart records failed/restart rather than silently repeating provider work

#### Scenario: Forget and late provider response
- **WHEN** consent is withdrawn, coach content is forgotten or an owner is deleted while a provider runs
- **THEN** owner/consent/generation checks prevent late content resurrection and stale Training sync cannot reenable sharing
- **AND** forget preserves only applicable daily consumption, deletion removes owner usage and the instance aggregate has no personal link

#### Scenario: Provider feasibility before business port
- **WHEN** preparation reviews the first Python delivery
- **THEN** admitted server providers are anthropic, openai, gemini and compatible over HTTP, with a deterministic fixture for synthetic verification and the existing local client coach preserved
- **AND** claude (Agent SDK) and codex (CLI) are explicitly deferred by promoter decision, not silently replaced by an HTTP provider with a similar brand name

### Requirement: Explicitly bounded coach delivery
The first Python delivery SHALL preserve existing local and HTTP coach behavior, consent, ownership, proposal validation/approval, quotas, cancellation and forget semantics without adding agent tools or frameworks. It SHALL NOT deliver Claude Agent SDK, Codex CLI, their subprocess launchers or a custom seccomp profile. LangChain/LangGraph, new tools, memory and agent orchestration SHALL remain separate future work without speculative adapters, tables or dependencies.

Deferred provider selections and non-secret configuration SHALL remain identifiable during import without silent fallback, conversion or deletion. Required original credential material SHALL remain protected under the existing origin-retention policy, outside active runtime mounts; this SHALL NOT promise future credential reuse or authorize deleting originals. Runtime SHALL NOT execute, refresh, reconnect or enqueue work for deferred providers, including scheduled work. Their unavailable state and the compatibility exception SHALL be visible to operators and clients. User attempts SHALL use the compatible unavailable response (503/code off), create no job and consume no quota. Existing provider IDs SHALL NOT be reassigned.

#### Scenario: Imported deferred provider remains unavailable
- **WHEN** imported settings select claude or codex or an older client requests work using that selection
- **THEN** availability reports it unavailable, user work is rejected before enqueue/quota consumption and scheduled work does not invoke it
- **AND** no Node fallback, automatic switch to anthropic/openai, credential reinterpretation or exposure occurs; preserved history/proposals and permitted HTTP/local workflows retain their contracts

#### Scenario: Accepted delivery excludes agent infrastructure
- **WHEN** the first Python runtime, Compose configuration and capability checks are accepted
- **THEN** they contain no SDK/CLI launcher, custom coach seccomp profile, runtime Node dependency or LangChain/LangGraph scaffolding
- **AND** published compatibility evidence names deferred providers as unavailable rather than claiming complete parity with all legacy providers

### Requirement: Least-privilege access
The platform SHALL implement the security reference's separate owner/migrator/runtime/executor/backup privileges, explicit RLS and transaction-local owner context. Preauthentication SHALL expose only bounded credential verification operations; administration SHALL authorize concrete actor/resource actions without arbitrary owner impersonation.

#### Scenario: Preauthentication and pool reuse
- **WHEN** preauth executes without an authenticated owner and the pool subsequently serves different owners or missing context
- **THEN** preauth has only its explicit bounded privileges and no later borrower inherits another owner's protected access
- **AND** runtime cannot execute DDL, bypass RLS or assume privileged executors

### Requirement: Authenticated session to RLS ownership
For protected owner-scoped HTTP operations, Python identity SHALL verify the compatible cookie or bearer signature, expiry, current account state and session version before deriving the authorized actor. The transaction initiator SHALL derive its owner context exclusively from that verified actor, install it transaction-locally on the single leased connection and pass the same handle and authorized context to collaborators. Client-supplied owner identifiers in body, query parameters or headers SHALL NOT establish or replace the actor or RLS owner. An explicit foreign resource target SHALL require authorization for that actor/resource action; administration and preauthentication SHALL retain their bounded privileges rather than impersonating an arbitrary owner. Missing or invalid authentication SHALL grant no protected access.

#### Scenario: Verified session controls owner context despite client forgery
- **WHEN** authenticated owner A sends protected read/write requests with owner B identifiers in body, query parameters or headers, separately and in combination, using compatible cookie and bearer sessions
- **THEN** the actor and transaction-local RLS owner remain A, only A-authorized operations may succeed and explicit unauthorized targets are denied
- **AND** B's protected rows are neither exposed nor modified, including through conflict/error responses, while legitimate same-owner operations still succeed

#### Scenario: Invalid sessions never establish protected ownership
- **WHEN** requests omit authentication, alter a signed identity or signature, use expired/revoked sessions or refer to disabled/deleted accounts, even while supplying a valid owner's identifier
- **THEN** the API rejects protected access without establishing authorized owner context, exposing protected rows or persisting a business write

#### Scenario: Session expires while waiting for protected work
- **WHEN** a cookie or bearer session is valid at HTTP entry but expires while its request waits for pool acquisition or an owner lock, before protected work is authorized
- **THEN** the API rechecks expiry against the current trusted server time after the wait and rejects the operation without protected data disclosure or a committed business write
- **AND** tests coordinate each wait and expiry boundary deterministically, verify a still-valid session succeeds and confirm the next pooled borrower inherits no authorized owner context
- **AND** the expiry decision point is explicit; a request authorized before expiry is not retroactively reported as rolled back solely because expiry occurs after its acknowledged commit

#### Scenario: Mixed credentials and duplicate cookies resolve one actor
- **WHEN** HTTP requests carry a cookie for A and a bearer for B, identical or conflicting duplicate session cookies, or both current and legacy cookie names
- **THEN** identity selects credentials once using characterized Node-compatible rules: a nonempty unambiguous cookie takes precedence over bearer, and the current cookie name takes precedence over the legacy name when present
- **AND** identical duplicates of the selected cookie name behave as one cookie; different values for that name supply no cookie credential, never a first-value or last-value winner
- **AND** without a selected cookie, only an independently verified bearer may establish an actor; conflicting duplicates without such a bearer are denied, and a selected cookie that fails verification never falls back to bearer or a lower-priority cookie
- **AND** HTTP tests cover both A/B assignments and cookie orders, valid and invalid bearer/cookie combinations, duplicate values and current/legacy names in their applicable HTTP/HTTPS configurations; the response identity, authorization and transaction-local RLS owner agree on the single selected actor, with other-owner data unchanged

#### Scenario: Concurrent revocation is serialized with protected work
- **WHEN** a protected operation waits for a connection or owner lock while session revocation, account disabling or deletion runs concurrently
- **THEN** the implementation defines and proves an observable serialization order and revalidates current access under that ordering before protected work is authorized
- **AND** if revocation, disabling or deletion takes effect first, stale-session work is denied without protected data disclosure or a committed business write
- **AND** work ordered before the security change may complete only under its then-valid authorization, and subsequent requests using invalidated credentials are denied

#### Scenario: HTTP and real PostgreSQL prove the complete ownership path
- **WHEN** the Python port acceptance suite drives actual protected HTTP routes against disposable real PostgreSQL with two synthetic owners, compatible signed sessions and the restricted runtime login
- **THEN** independent observations verify authorized own-owner reads/writes, denied cross-owner access and owner forgery, invalid-session rejection, expiry during pool/lock waits, mixed-credential/duplicate-cookie selection and coordinated concurrent revocation outcomes
- **AND** runtime metadata and behavior verify ENABLE/FORCE RLS, USING/WITH CHECK enforcement and absence of ownership, superuser or BYPASSRLS privileges on protected tables
- **AND** a max-one pool serving A then B or missing context after commit, rollback, SQL error, timeout and cancellation leaks neither owner context nor protected access
- **AND** privileged connections are limited to disposable setup and independent inspection; mocked authentication/database calls, isolated SQL fixtures or historical Node results alone do not satisfy this Python HTTP acceptance

### Requirement: Recoverable deletion and compatible audit
Deletion SHALL preserve legacy administrative safeguards, remove operational SQL data and transactionally record pending external cleanup. It SHALL disconnect personally bound coach credentials before releasing ownership, preserve consumed invitations and historical audit, and keep cleanup failures visible without reopening access. Media bytes/GC marks SHALL remain external and missing/unreadable references SHALL NOT trigger destructive collection. Legacy audit SHALL remain best effort with configured 90-day/5000-event defaults and IP off; audit failure SHALL NOT abort business SQL or change a committed success.

#### Scenario: External cleanup or audit failure
- **WHEN** user deletion commits but external cleanup fails, or a legacy audit write fails
- **THEN** cleanup remains recoverable and visibly pending, the deleted user has no access, and no credential is silently reassigned
- **AND** audit degradation is observable without converting a confirmed business success to failure or deleting historical invitations/events

### Requirement: Faithful import and retirement parity
Schema evolution and data import SHALL be separate. Import SHALL retain IDs, credential semantics, complete documents and ownership; unfaithful representations SHALL block import/cutover with a protected report instead of silent correction. Before retirement the port SHALL prove parity, update JS source/build/generator consumers to the canonical neutral library, preserve admitted provider/client contracts and eliminate active legacy-file dependencies. Synthetic current-reference success SHALL NOT be called Python or post-retirement acceptance.

#### Scenario: Unrepresentable legacy data
- **WHEN** prevalidation finds invalid Unicode/JSON, incompatible revision types or unresolved identity/ownership differences
- **THEN** import and cutover stop without silently rewriting or dropping data
- **AND** the discrepancy is resolved explicitly before equivalent fixtures can pass

#### Scenario: OpenAPI authority moves without contract drift
- **WHEN** the public API contract is moved from the legacy API tree to the Python backend
- **THEN** one editable canonical YAML remains, its generator and consumers use the new location and Python route/response checks plus independent HTTP cases verify the preserved contract
- **AND** framework-generated documentation or validation defaults do not silently introduce new public endpoints, status codes, coercions or cookie/header behavior

#### Scenario: Parity after removing the replaced backend
- **WHEN** the old business API and file readers are retired
- **THEN** current client, coach, media, formats and security scenarios still pass on Python/PostgreSQL
- **AND** relevant web/mobile bundles and generators no longer import the retired API tree while the neutral JavaScript library remains available

### Requirement: Bounded legacy and temporary artifact cleanup
The port SHALL include an explicit cleanup checkpoint after equivalent cutover and before platform acceptance. A reviewed path/consumer inventory SHALL classify artifacts as remove, retain with current purpose, or protected recovery material. Cleanup SHALL remove replaced business code, exclusive legacy readers/writers/configuration/dependencies and superseded temporary scaffolds rather than leave a disabled second implementation. Applicable behavioral tests SHALL be preserved or adapted before obsolete implementation-specific tests are removed. Required neutral JavaScript, catalogue assets, current operational tooling and still-useful Foundation evidence SHALL NOT be removed merely for being JavaScript, JSON or historical. Removal SHALL be based on obsolete purpose and verified consumers, not programming language.

Cleanup SHALL use exact owned paths/resources, preserve unrelated work and user/client data, and avoid broad prune or directory deletion without consumer review. Protected origin/release/configuration/secrets SHALL remain outside active dependencies for the agreed recovery window; its expiry SHALL NOT authorize their deletion. Temporary logs, captures and synthetic artifacts SHALL be removed only after necessary sanitized evidence is retained in the appropriate delivery/CI location; no duplicate permanent cleanup report SHALL be created. Post-cleanup builds, parity, security, restore and dependency checks SHALL pass before G3/GO acceptance.

#### Scenario: Active dependency prevents removal
- **WHEN** a cleanup candidate is still imported by a supported client, generator, test or operational command
- **THEN** the consumer is migrated and verified before removal, or the artifact is retained with an explicit current purpose
- **AND** cleanup cannot pass by leaving a required dependency broken or replacing behavioral coverage with documentation

#### Scenario: Cleanup preserves recovery and foreign artifacts
- **WHEN** cleanup runs with synthetic owned artifacts, a foreign sentinel and protected recovery material present
- **THEN** only reviewed obsolete owned artifacts are removed, the sentinel and protected material remain intact and no original user data is deleted
- **AND** clean-checkout builds and post-retirement capability/security/restore checks still pass without active imports of the retired backend
