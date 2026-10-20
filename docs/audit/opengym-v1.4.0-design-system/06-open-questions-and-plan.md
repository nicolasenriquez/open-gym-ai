# 06 — Open questions, approval plan and readiness

## Executive conclusion

The repository already has a recognizable, source-defined design system: central tokens, controlled primitives, consistent inset groups/rows, shared sheets, domain-specific composites, a real theme/accent model and mobile-to-desktop adaptations. It does **not** need a new UI framework to make that system discoverable.

**Ready for an owner-reviewed canonical draft of the stable core; not ready for an unqualified, complete “v1.4.0 visually verified DESIGN.md.”** The requested release source was read, but the existing stack is v1.4.1. Known accessibility defects must remain debt rather than standards. Authenticated/populated/native/alternate-session states remain incomplete. The next action is approval and scope resolution, not immediate implementation.

## Open decisions (owner input required)

| Priority | Question | Why it blocks / proposed default |
|---|---|---|
| P0 | Is canonical scope release-exact1.4.0 or current maintained1.4.1? | Cannot label current screenshots1.4.0. Default: stable-core draft annotated by provenance; release-exact runtime needs separate approved environment |
| P0 | Should this become a root DESIGN.md plus a short CLAUDE.md link? | No canonical file was authorized. Default: keep these six documents non-normative until review |
| P1 | Approve overlay focus/name/role and switch-label remediation as separate work? | F01/F02 are confirmed interaction defects, not aesthetic preferences; common infrastructure affects many sheets |
| P1 | What accessible accent-text/ink policy should apply across themes/presets? | Existing light green tint fails normal-text contrast; source's large-text rationale is wrong. Separate palette identity from text/ink roles; no palette replacement assumed |
| P1 | May a temporary test account/populated fixture and exact-release runtime be provisioned later? | Coach/admin/sync/populated charts cannot be honestly validated in current guest. Separate disposable data/environment, explicit approval; no auth bypass or production seeding |
| P2 | Is44px an aspirational touch target or an enforced requirement, including chips? | Source intent and geometry differ. Test physical use/spacing before broad density changes; distinguish WCAG24px floor |
| P2 | What is the supported zoom/reduced-motion/autoplay policy on PWA/native? | Viewport restriction and JS/media gaps need physical device evidence; CSS suppression alone is insufficient |
| P2 | Which historical instruction/doc facts should be corrected with canonical adoption? | CLAUDE media count/service and dependency shorthand, old proposal comments and contrast claim drift; do not silently rewrite now |
| P3 | Are typography/spacing tokens actually needed beyond existing CSS? | Current system uses contextual literals; generating a formal scale now would invent design. Default: document roles, preserve implementation |
| P3 | Is a real second independent design pass worth doing? | Current qualitative review is explicitly single-context degraded. Optional; no need to install more skills to obtain basic coverage |

## Smallest safe next plan

1. **Review this audit.** Accept/reject its provenance and prioritized findings. Confirm maintained version and what canonical means. No installation needed.
2. **Review an exact documentation-only diff before canonical adoption.** Apply the editorial workflow in05 to condense04 into stable UI contracts and source pointers. Keep runtime findings and unresolved decisions in the audit; propose verified root-rule corrections separately. Approval of audit wording does not authorize DESIGN.md, CLAUDE.md or AGENTS.md changes.
3. **Resolve high-priority accessibility defects in separate scoped changes.** Shared overlays first, missing switch names, then theme/accent text/ink combinations. Preserve nested sheets, browser back, scrolling, autosave and timer behavior; test the contracts instead of adding a replacement UI stack.
4. **Close evidence gaps with explicit approval.** Exact release container/build in a separate disposable setup if1.4.0 matters; populated fixture/account for charts/sync/coach; real iOS/Android/PWA keyboard, touch, zoom/reduce; RTL/long copy; alternate Cards/List/Compact/Focus layouts. Do not restart or repurpose the user's existing stack automatically.
5. **Adopt lightweight maintenance.** Use05 checklist for affected states; update canonical guidance with implementation. CI screenshot infrastructure and new tools are optional future decisions, not prerequisites.

### Acceptance checks for the documentation proposal

- Every proposed normative statement is distinguished from observed behavior, historical evidence and unresolved policy.
- Source/runtime versions remain explicit; new skill availability does not imply new browser verification.
- The root pointer is conditional; detailed guidance has one authoritative home, with historical snapshots clearly identified.
- Proposed root-rule corrections are source-checked using the advisory scope of `rules-check-drift`.
- Local references resolve, and the preview contains only the named documentation files; canonical promotion requires separate approval.

### Suggested acceptance checks for later work

- Exact source/runtime build provenance or clear divergence before taking “baseline” images.
- Modal initial focus, forward/reverse tab containment, accessible title/role, Escape/back/locked handling, nested close and return focus; background scroll restoration on both viewport sizes.
- Every switch/slider/icon action has an intelligible accessible name and correct state announcement.
- Normal text4.5:1 / large3:1 under actual definitions; all presets and custom extremes, both themes, selected/disabled/pressed states, composited tints. Do not confuse disabled/decorative exceptions with normal labels.
- Mobile/desktop and relevant intermediate fit, no unintended page overflow; native safe-area/keyboard and duration input remain usable.
- No change to domain helper outcomes, session completion/layout equivalence, data ownership, pending sync, Undo or confirmation/autosave semantics. Run affected repository tests for any implementation patch; none were run for this documentation-only audit.

## Deliverables and evidence map

| File | Purpose |
|---|---|
| [01-environment-and-skills.md](01-environment-and-skills.md) | Version/stack/safety verification, real skill inventory, missing-tool fallback/approval boundaries |
| [02-source-inventory.md](02-source-inventory.md) | Exact tokens, type/spacing/layout,35 component files plus shared-control/sheet map and interaction contracts |
| [03-visual-audit.md](03-visual-audit.md) | CLI browser procedure, coverage/status matrix, positives and ranked findings with source/evidence |
| [04-design-system-draft.md](04-design-system-draft.md) | Non-canonical stable-core draft; exceptions/debt separated from rules |
| [05-agent-integration-proposal.md](05-agent-integration-proposal.md) | Proposed future DESIGN/entry-point/checklist maintenance, no instruction edits |
| This file | Questions, approvals, sequence and readiness |
| [evidence/screenshots.md](evidence/screenshots.md) | Complete68-image register: actual route/view/theme/state/source/time; redirects explicit |
| [evidence/component-reference.v1.4.0.json](evidence/component-reference.v1.4.0.json) | Release-exact declaration/prop and static import index (35 files) |
| [evidence/index.v1.4.0.css](evidence/index.v1.4.0.css), [release-ui-delta.diff](evidence/release-ui-delta.diff) | Release source and relevant1.4.1 differences |
| [evidence/assessment-a.md](evidence/assessment-a.md), [impeccable-detector.json](evidence/impeccable-detector.json) | Qualitative-before-static pass; empty detector result is narrow, not compliance |
| [evidence/route-observations.json](evidence/route-observations.json), [gated-routes.log](evidence/gated-routes.log) | Actual destinations, DOM snapshots, geometry, access limitations |
| [evidence/accessibility-observations.log](evidence/accessibility-observations.log), [interaction-observations.log](evidence/interaction-observations.log), [contrast-calculations.json](evidence/contrast-calculations.json) | Reproducible switch/target/reduce/focus/theme/color findings |
| [evidence/final-verification.log](evidence/final-verification.log) | Final HEAD, working tree, tracked diff, unchanged Compose state |

Other timestamped YAML/console/screenshot/script/log files in evidence are raw CLI output. They remain within scope; no browser cookie/storage dump or external screenshot transmission. The disposable routine ID in some logs is not a real user's data.

## Preservation and final verification

The dedicated browser session was closed. Final `git status --short` retains the original `.gitignore`, `.agents/`, `.gitattributes`, `skills-lock.json` entries and adds only `?? docs/audit/` at Git's collapsed-directory level. Tracked diff remains **only the pre-existing `.gitignore` six-line addition**. No frontend/api/web/Compose/root-design/root-instruction tracked changes. Detached HEAD stays `464355ef`; both existing containers remain Up/healthy without restart.

All intentional writes by this audit are below `docs/audit/opengym-v1.4.0-design-system/`. No source, dependency, existing skill, Docker configuration, valuable dataset, authentication credential or canonical instruction/design document was intentionally changed. No downloads/installations. Existing `.agents/` filesystem drift during the run is disclosed in01, not attributed to this audit. Because the initial baseline was status/diff inspection rather than byte hashes of all pre-existing untracked files, **byte-for-byte preservation of every untracked file cannot be independently proven**; do not overstate that guarantee. The tracked status/diff and intentional-write scope have been checked.

Documentation link integrity was checked locally. No frontend/API/MCP tests or build were needed/run; no application implementation is delivered. Evidence limitation is part of the result, not a hidden follow-up promise.
