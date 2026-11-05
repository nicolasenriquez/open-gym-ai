## Context

Delivered modular Python/FastAPI/PostgreSQL backend with the existing React/Vite/Zustand frontend. The Node API and transient comparison contracts are retired. This archive records accepted repository delivery; actual instance migration is a separate operation.

## Decisions

- HTTP uses /api/v1 exclusively; nginx protects internal probes. backend/openapi.yaml is the public contract.
- Feature modules own domain rules and SQL; service operations own transactions. Restricted roles, FORCE RLS and revalidation after waits protect actor/resource access.
- Training retains JSONB revisions, stamps, lineage, offline state and conflict reconciliation. Preserve absent/null and historical values; unrepresentable imports fail closed.
- Keep frontend-required JavaScript in shared/coach-core; preserve catalogue and format/mobile consumers.
- Audit failure cannot invalidate a confirmed business result. SQL account deletion records recoverable external cleanup; late Coach results revalidate access/consent.
- Single-worker Linux/amd64 Compose deployment separates runtime, migration, test and ops roles. Secrets remain external files; no runtime installation or automatic startup migration.

## 11. Q6: migración segura antes de evolución agéntica

Coach local and existing HTTP providers remain supported. Claude Agent SDK/Codex CLI are unavailable without fallback or provider remapping. Preserve non-secret selection/history and protected originals. Future agent runtimes require an independently approved change.

## Recovery and diagnostics

Host-controlled capture stops all writers, leaves PostgreSQL available and journals exclusive ownership. Restore only previously active services after process termination and schema verification. No TTL-only release. Encrypt/transfer after the pause; authenticate bundles through EOF before atomic publication. Restore into a fresh isolated target with normal access blocked.

Q1 requires credential-level review or an explicitly authorized new local access path; preserve identity/roles and Coach decryption material. Q2 repairs the surviving Python/PostgreSQL destination forward after new writes, preserving acknowledged data. Snapshots never prove current authorization.

Standard bounded logging provides private request correlation, health and backup age; retention is seven days/256 MiB. Real RPO/RTO and physical storage/custody require operational measurement.

## Commands and safety contract

Use [backend/README.md](../../../../backend/README.md) for commands and configuration, [platform-suites.json](../../../../backend/platform-suites.json) for executable case mappings and [operations](../../../../docs/reference/platform-operations.md) for recovery. Historical plans are superseded by these owning sources. Missing prerequisites or skipped mandatory proofs do not count as success.

## Delivered pre-cutover evidence validator (synthetic preparation)

The existing gates/pre_cutover inspector validates a sanitized index, bound release/provenance, coverage and checksummed artifacts. Structural success grants no operational permission. Consult the current verifier implementation and [operation contract](../../../../docs/reference/platform-operations.md) when preparing a separately authorized intervention.

## Delivered authorized-cutover evidence validator

The gates/authorized_cutover inspector additionally checks recorded approval/window, authority, protected originals and rollback/forward-repair evidence. It inspects evidence rather than executing cutover; human review and exact-resource permission remain required.

## Procedimiento ensayado de captura Node detenida

Retained host tooling captures a frozen source using drain proof, explicit writer custody, bounded copying and independent hashes. Protocol fixtures exercise refusal, interruption and quarantine; the retired Node API is not an active test/runtime dependency. Actual source access requires separate permission.

## Ensayo integrado: captura Node → importación PostgreSQL

The synthetic chain mounts captured files read-only into a new isolated PostgreSQL target, verifies SQL/files independently and leaves runtime CONNECT denied. Occupied targets and unrepresentable input fail closed.

## Ensayo integrado hasta backup cifrado y restore aislado

The rehearsal continues through host backup, verified encrypted publication and separate quarantined restore. Source cutoff, import and snapshot times remain distinct; a new bundle does not refresh the effective age of imported data.

## Contratos de ejecución consolidados

All 57 delivered slices and their final evidence are summarized in [tasks.md](tasks.md). Detailed schema/security/operation contracts have one owner in the references below; archive acceptance does not expand operational permissions.

## References

- [Schema](../../../../docs/reference/platform-schema.md): tables, constraints, migrations.
- [Security](../../../../docs/reference/platform-security.md): sessions, roles, SQL functions and lock order.
- [Operation](../../../../docs/reference/platform-operations.md): capture, encryption, restore, access review and cutover.
- [Observability](../../../../docs/reference/platform-observability.md): private diagnostics and retention.
- [Modularity](../../../../docs/reference/platform-modularity.md): ownership and collaboration.
- [Main specs](../../../specs/): accepted requirements.
