---
name: opsx-delivery-workflow
description: Implement and verify an explicitly authorized OpenSpec change using its tasks and bounded slices. Use for OpenSpec delivery or resuming implementation under this workflow. Stops before unauthorized closeout actions.
---

# OpenSpec Delivery Workflow

Own execution gates and verification policy. OpenSpec Apply is the sole
implementation and checkbox-update owner; specialists supply methods and evidence,
not competing trackers. Human-facing examples: [Usage](../opsx-spec-workflow/README.md).

## 1. Confirm authorization and prerequisites

- Identify the exact change and the user's implementation request.
- Read repository instructions and inspect existing uncommitted work; preserve
  unrelated edits. Read required area-specific docs before changing those areas.
- Read `openspec status --change "<name>" --json` and
  `openspec instructions apply --change "<name>" --json`.
- Read every context file returned by apply instructions.
- Confirm scope, seams, slice order, and verification prerequisites. Artifact
  completion alone does not establish implementation readiness.

If artifacts or material decisions are missing, pause for specification work.
Explicit approval of documented test seams carries forward; otherwise obtain it
before writing tests. Reconfirm only materially changed seams.

Check specialist tools and dependencies before relying on them. Use available
tools for equivalent operations and disclose material adaptations. Missing
capabilities that prevent required proof are blockers, not assumed successes.
Ask before dependency installation, destructive setup, or external publication.

Completion: authorized scope and an executable first slice are established.

## 2. Execute one slice at a time

Use the installed `openspec-apply-change` instructions with the change's explicit
execution order. This workflow adds evidence gates to task completion; it does
not authorize changing upstream skills. Continue through approved slices without
asking at every step; pause for material decisions, scope changes, or blockers.

For runtime behavior, consult `tdd` and follow its local contract:
- Add one focused behavioral test at an agreed public seam.
- Run it and observe failure for the intended reason.
- Implement only enough to satisfy that behavior.
- Run it and relevant focused regressions before advancing.

Import, syntax, or environment errors are not the intended behavioral RED.
For bugs, reuse `diagnosing-bugs` evidence, preserve the regression, and rerun
the original reproduction after fixing. A bug reproduction does not replace a
regression test where an appropriate seam exists.

For behavior-preserving refactors, establish passing characterization coverage
instead of manufacturing a RED. Record the applicable proof and agreed exception.
For docs-only slices, run the planned consistency check instead of TDD.
The local TDD contract reserves refactoring for review, outside RED/GREEN.

Use specialists only as needed: `react-testing` for React tests,
`frontend-a11y` for interactive accessibility, and `click-path-audit` for
shared-state changes and affected consumers. Select backend specialists by the
actual stack; installed FastAPI or Postgres skills do not make them relevant.

Completion: each slice's checkpoint and focused regressions pass before dependent work.

## 3. Persist honest progress

The Apply executor updates the OpenSpec tasks artifact. Mark a task complete
only when its own acceptance condition is met. A fail-first task may complete
with observed intended RED; implementation and verification require their own
passing evidence. Reviewers report findings; they do not update checkboxes.

Keep adjacent `Traceability:` and concise `Notes:` lines. Evidence identifies
the command or check, observed result, and a durable artifact path when relevant.
Distinguish passed, failed, blocked, and not run. Reopen completion invalidated
by later evidence. On resume, inspect the current diff and rerun affected checks;
historical notes do not prove a changed working tree.

For material scope, contract, migration, or design changes, pause and obtain the
needed decision; update and revalidate artifacts before affected work resumes.

Completion: task state accurately reflects evidence for the current work.

## 4. Verify and review the integrated change

Map every changed requirement to actual behavior and evidence:
- Domain/backend: focused tests and applicable API, persistence, integration checks.
- Web UI: relevant component tests and real interaction with the affected flow.
- Visual changes: screenshots or traces plus behavioral assertions.
- Authenticated, MCP, Coach, or native flows: dedicated coverage when affected.

Reuse `verify-opengym` and its feature map for the guest journeys they cover.
A save requires resulting state and persistence proof; a toast or screenshot alone
is insufficient. Distinguish Playwright CLI interactive verification from
Playwright Test regression coverage, consulting `playwright-cli` or `e2e-testing`
as needed. Run relevant broader regressions and repository-required checks.

Use `ponytail-review` for routine review, supplying the OpenSpec artifacts and
exact delivered diff, including uncommitted and newly added files. It reports;
the executor fixes blocking findings within approved scope, reruns affected
checks, and repeats review where conclusions changed. Necessary refactoring
belongs here, with tests kept green. New scope requires approval.
Use `code-review` only when its fixed-point, tracker, and execution prerequisites
are met. A review verdict does not authorize release.

Use an installed OpenSpec verification skill if available; otherwise explicitly
review requirement-to-code-and-evidence coverage. Artifact validation is not a
substitute. Consult `rules-check-drift` when changed structure or conventions may
invalidate AGENTS.md; edits require authorization.

Keep credentials and user data out of tracked evidence. Preserve evidence after
cleanup; close only resources this run owns, following the verification harness.

Completion: required checks pass, requirements have evidence, and blocking review
findings are resolved. Unexecuted required checks prevent readiness.

## 5. Prepare closeout and stop

Update applicable docs and release notes, then revalidate artifacts.
Report tasks and slices completed, checks executed, evidence references,
unexecuted checks, residual risks, and either blockers or `Ready for closeout`.
Required unresolved work blocks readiness; defer it only through an explicit
scope decision preserved in the artifacts.

Reuse the existing verification harness. Creation via `create-verification-skill`
or a global pass via `maintain-verification-skill` is separate, explicitly
requested work; neither is an automatic feature-delivery step. Report discovered
harness drift or missing coverage without silently expanding scope or creating PRs.

Synchronization and archive need explicit authorization covering those actions.
When granted, assess deltas, require verified scope and complete required checks,
and use `openspec-sync-specs` then `openspec-archive-change` as applicable.
Confirm postconditions and report actual sync/archive results, not just intent.
Implementation permission alone does not authorize commit, push, merge,
deployment, destructive operations, synchronization, or archiving.
