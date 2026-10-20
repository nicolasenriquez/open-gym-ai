# 05 — Proposed integration for future agents

**Documentation-only proposal. No root instructions were created or edited.** Existing root CLAUDE.md remains authoritative except that factual drift should be surfaced for owner resolution. This is not approval to add scripts, hooks, dependencies or application changes.

## Where guidance should live after approval

| Location | Purpose | Proposal / gate |
|---|---|---|
| `DESIGN.md` at repo root | Short canonical product/UI contract | Preferred home after version decision and owner review; copy only stable principles/tokens/patterns, not every incidental CSS literal |
| Existing `CLAUDE.md` | Entry-point link and safe workflow | Add a short design-reading rule and correct verified stale facts in a separate reviewed patch; do not duplicate whole token tables |
| `AGENTS.md` | Cross-harness entry point, if project wants one | Not found at root. Optional alternative thin entry point, **not necessary now**. Avoid two drifting authorities |
| `docs/audit/opengym-v1.4.0-design-system/` | Historical evidence, release caveats, findings/proposals | Retain immutable-ish audit context; not automatically authoritative instructions |
| Existing `docs/dev/` notes | Feature rationale/spec history | Keep proposal/implemented status visible; do not treat COMBINE_ROUTINES as current global spec |
| `.agents/skills` | Optional task procedures | Existing skills are enough. No new “design agent” skill or UI framework needed |

### Proposed small entry-point text (do not paste before approval)

> For frontend layout, styling, shared-control or interaction changes, read DESIGN.md for the approved UI contracts, then inspect the affected component and CSS consumers.

This is a **proposed insert**, not a new instruction governing this audit. If DESIGN.md is not yet approved, point only to this audit as non-normative discovery.

## Editorial workflow for the canonical proposal

Use `writing-for-agents` for composition and `prime-frontend` only when source context needs refreshing. Reserve `prime-codebase` for cross-project claims. `rules-check-drift` checks proposed root-rule corrections; it does not review the audit documents. `rules-create-global` and `codebase-onboarding` are optional references, not instructions to regenerate existing files.

1. **Classify:** place each candidate statement in approved guidance, implementation reference, historical evidence or unresolved proposal. Done when each normative statement has source support and owner approval; neither screenshots nor installed skills confer approval.
2. **Structure:** keep stable UI contracts in DESIGN.md, implementation values in CSS/JS and historical observations in this audit. Done when each maintained fact has one authoritative home and any necessary historical snapshot is explicitly scoped.
3. **Route:** keep only the conditional reading pointer in the root rules. Done when its trigger covers the intended frontend tasks and its target exists and is approved.
4. **Check:** verify source pointers, version scope and proposed root-rule corrections; return the exact diff for approval. Done when changed references resolve, unsupported claims remain questions and canonical edits are separately authorized.

Working principles that cannot be derived from source require owner input. Existing safety constraints remain in force; this workflow adds no new architecture, testing infrastructure or permissions.

## Reading order for a frontend change

1. Root instructions + CONTRIBUTING.md; then approved DESIGN.md when it exists.
2. `frontend/src/App.jsx`, affected route/component, `components/ui.jsx`/`Modals.jsx` and actual `index.css` selectors.
3. Store/UI state and helpers touched by the handler: distinguish local visual state, durable setting, staged form and immediate persistence. Training/read-back rules stay in pure helpers with adjacent tests.
4. Relevant feature docs **with status checked against code**, not all historical notes.
5. Actual runtime via Playwright CLI; verify login/data safety and source/runtime version correspondence first.
6. Evidence/verification summary; unresolved behavior questions are questions, not license to redesign.

## Minimal future change checklist

- [ ] Identify route, component, CSS selector, source commit and actual runtime version.
- [ ] Reuse shared control and explain any unavoidable local exception.
- [ ] Check mobile/desktop fit, both themes and affected accent semantics; no whole-app restyling hidden in feature work.
- [ ] Check accessible names, focus order/overlay containment, Escape/back, disabled/loading/empty/error and touch hit areas relevant to the change.
- [ ] Check longer translations/RTL/native keyboard if affected.
- [ ] Protect autosave/select/multi-select/timer/Undo and session layout equivalence; test domain logic where behavior changes.
- [ ] No valuable data mutation for visual tests. Use a disposable local profile/fixture only after checking guest/sync contract.
- [ ] Review diff for unintended source/dependency/instruction changes and record actual verification limits.

Not a demand for a heavy new test suite on every CSS change: choose affected states, but do not call a single screenshot a complete UX verification. No axe, Storybook, token generator or screenshot service is required by this proposal.

## Maintenance and approval boundaries

- Treat design guidance like source: reviewed changes alongside affected implementation, a maintainer-owned decision when intention conflicts with current behavior, and release/build scope on major examples.
- Canonical document should label **intentional rules**, **supported exceptions** and **known debt** separately. F01/F02/F03 must never become examples to emulate.
- Keep token source in CSS/JS; DESIGN.md explains roles and points to implementation. Avoid maintaining a giant duplicated list that becomes another stale truth.
- Inventory is navigational assistance, not a generated API specification: props/imports in source remain authoritative.
- New skill/tool installs, root instruction edits, design enforcement automation and architecture changes each require explicit approval. Optional missing tools and local fallbacks are in01.
- If multiple agents audit, require truly independent contexts or the same degraded banner used here; no claim of parallel review when no sub-agent tool exists.

Recommended first canonical pass is a small single document plus one entry-point link. A separate component-site/generator/organization-wide governance layer is unnecessary for this repository at present.
