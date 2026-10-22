---
type: Audit
title: 04 — Evidence-backed design-system draft (non-canonical)
description: Historical non-canonical design proposal and its evidence boundaries.
---
# 04 — Evidence-backed design-system draft (non-canonical)

**Proposal, not an instruction file.** Do not promote this whole audit automatically to `DESIGN.md`. Target source is v1.4.0; visual cross-check runtime is v1.4.1. The exact facts/values/component map live in [02](02-source-inventory.md); defects and confidence boundaries in [03](03-visual-audit.md). This draft intentionally does not rebrand openGym or mint a replacement token system.

## Product identity — CONFIRMED

openGym is a private, self-hosted gym and body-weight tracker: native-feeling controls, minimal ceremony during training, user-owned data. It is a PWA with optional Capacitor shells, not a marketing website. Task clarity and preserving a training session matter more than decorative novelty. Login/account/Coach/admin are conditional capabilities; a guest can use local-only tracking.

Visual identity is grounded in the stylesheet's four explicit principles: type-led hierarchy, neutral surfaces with selective semantic color, hairlines instead of outlined cards, acknowledgment motion. Apple/system-control influence is literal in CSS and palette; do not infer a broader brand strategy, proprietary font or mandated Apple-only platform.

## Foundations — candidate standards

| Candidate rule | Evidence/confidence | Important qualification |
|---|---|---|
| Reuse `index.css` tokens and existing theme/accent resolution; use semantic colors for status | CONFIRMED source + dark/light UI | Exact palette is incumbent, **not contrast certification**. F03 blocks approval of all text uses |
| Use system font stack; body17px; existing title/row/metadata classes instead of unrelated font families | CONFIRMED | No reusable type-role token scale exists. Heading34/700→30 on small screens; contextual type is real |
| Keep ground/elevated/surface ramp and flat inset groups; avoid gratuitous borders/shadows | CONFIRMED | Media thumbnails deliberately have white backing; timer/dialog/control shadows are exceptions |
| Use `--pad`16px and actual component radii; preserve inset divider icon rail | CONFIRMED | No documented universal spacing grid; do not round all local gaps into a fabricated scale |
| Reuse Button, Row, Section, field/selection controls and sheet stack before inventing screen-local alternatives | CONFIRMED reuse architecture | Existing call sites have accessibility gaps. Behavior fixes need a separately approved change |
| Preserve narrow pages at desktop while allowing catalogue/stat columns | CONFIRMED | App560px; desktop1080/full vs640/narrow at1000px; bottom navigation remains |
| Default short interaction transitions use140/220ms and shared easing; honor reduce | CONFIRMED basics | Sheet340/center280/resume ping exceptions; JS smooth scroll/media policy unresolved |
| Preserve UI/domain/persistence boundaries while styling | CONFIRMED architecture | Data ownership, completion, sync, units and timers are not presentation-only |

### Color and theme usage

- Use existing `--bg`, `--bg-el`, `--surface*`, `--label*`, `--sep*` roles from02, not raw replacement grays.
- Accent is preference-driven (`lime`, `sky`, `orange`, `violet`, `pink`, `red`, `teal`, `gold` or validated custom). `lime` resolves green; preserve legacy key, do not rename it as cosmetic cleanup.
- Theme and accent combine: resolved `data-theme` plus `data-accent`/inline custom variables determine final ink. System mode is a preference, not a third palette.
- Semantic red/orange/purple/F/timer/recovery colors convey domain state; selected accent is not allowed to erase those distinctions.
- **Hold for approval:** accessible small-text accent role versus filled accent, preset ink policy, faint label usage, active tab labels. Document existing shortcomings separately; never say every current token usage is an approved AA combination.

### Type, layout and anatomy

Pages generally comprise `.hdr` (back/title/context/actions), optional controls, content groups, persistent bottom navigation except active session, and shell overlays/feedback. Use `.narrow` intentionally for Home/editor and one-column reader/configuration content. Long text wraps; trailing values truncate selectively. Avoid converting established data-heavy rows into decorative dashboard cards.

Use `Section`/`Row` for grouped settings with title/value/accessory/control positions. Library needs result count, metadata, filters and list/cards display; it is not a generic SelectSheet. Routine editor, session, Stats and feature-specific sheets compose primitives but own their respective domain rules.

### Interaction and state contracts

- Button variants retain their meaning: primary fill, tinted, danger, ghost/plain and small/xs; inspect defaults, do not invent a “secondary” variant.
- SelectRow: choose → close → commit. MultiSelectRow: each toggle persists; Done closes. Segmented is controlled selection, not necessarily navigation.
- Routine editor saves each field; ExConfig stages values; session completion and change-history departure have their own confirmations. Never add/remove a Save button solely for stylistic consistency.
- Search/filter is not globally persistent; ExerciseViewToggle and Plan tab preference do persist. Map state ownership before changing controls.
- Modals owns stacking, escape/back/backdrop, scroll pin/restore and keyboard accommodation. **Focus semantics are a defect to fix, not desired behavior.** Do not implement another overlay layer to work around it.
- NumberField and Stepper own decimal/nullable/clamp/unit/hold behavior. Reuse them; exercise units, rest and progression are tested domain logic, not arbitrary display formatting.
- Active session set completion drives progression/rest/advancement via shared helpers; Cards/List/Compact/Focus must remain semantically equivalent.
- Toast/Undo, SyncBanner, media fallback and ErrorBoundary are established feedback channels. A new visual design must retain actionable recoverability and distinguish local from synced ownership.

## Accessibility policy — proposed, not falsely claimed as current

Retain visible focus, semantic native controls, readable hierarchy, explicit statuses, useful empty states, safe-area accommodation and reduce CSS. Require accessible names for icon/control instances and shared overlay focus semantics after approved remediation. Assess normal text at4.5:1, large at3:1 under the actual WCAG size definition; never infer large text from17px/600. Verify final composited colors and each theme/accent, not token names.

Target policy needs owner approval: many controls expand hit areas to~44px, but filter chips remain~30px; WCAG2.2 minimum is not the same as the source's aspirational44px. Zoom/native keyboard/reduced media still need device validation. No compliance certification is implied by this draft or an empty static detector result.

## Agent guardrails proposed for future adoption

1. Read canonical design guidance **if approved**, then inspect actual target component and consumers; source wins over an obsolete example until discrepancy is resolved.
2. Reuse existing frontend stack. Do not add frameworks, tokens, fonts, icon packs or libraries for visual cleanup without explicit approval.
3. Separate theme/style work from state/domain/auth changes; never rewrite progression or synchronization in a UI patch.
4. For visual change proposals, compare mobile390×844 and desktop1440×900, dark and light; add tablet/native/RTL/long-data cases when affected. These are audit test sizes, not newly mandated product breakpoints.
5. Record route, state, release/build, theme and viewport on evidence; a redirect screenshot does not cover the requested route.
6. Preserve intentional legacy keys/aliases and behavior. Do not reproduce known defects or elevate stale design proposals into current requirements.

## Not decided here

No new component library, naming migration, token taxonomy, formalized spacing/type scale, brand direction, palette replacement or screen redesign. No canonical lint enforcement, accessibility dependency, screenshot CI, new AGENTS.md or CLAUDE.md edits. Questions and approval plan: [06](06-open-questions-and-plan.md).
