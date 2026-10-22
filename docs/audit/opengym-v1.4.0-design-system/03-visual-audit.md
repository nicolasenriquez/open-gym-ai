---
type: Audit
title: 03 — Playwright visual and UX audit
description: Historical visual and UX findings from Playwright inspection.
---
# 03 — Playwright visual and UX audit

## What was actually exercised

**Mandatory browser inspection completed with `playwright-cli`**, not replaced by source reading. Runtime `http://localhost:8080/`, Edge155 Chromium headless, Spanish UI, 2026-10-19 UTC. Isolated guest profile; no existing account data. **Runtime reports v1.4.1**: visual findings cannot be advertised as release-exact v1.4.0 validation. See [01](01-environment-and-skills.md).

68 screenshots, with route, actual destination, CSS-pixel viewport, theme, state, timestamp and source in [evidence/screenshots.md](evidence/screenshots.md). 23 route-entry attempts × desktop/mobile form the initial batch; entries that redirected are explicitly not coverage of the requested page. Initial batch snapshots and geometry: [route-observations.json](evidence/route-observations.json), script [capture-routes.js](evidence/capture-routes.js). Additional screenshots cover search/filter/detail, light theme, disposable editor/session, rest and unsaved confirmation. Screenshots are viewport captures, not full-page promises; accessibility snapshots cover additional lower-page controls.

Primary commands used: `playwright-cli -s=opengym-audit open http://localhost:8080/ --browser=msedge --config=<audit>/evidence/browser-config.json`; `snapshot`, `screenshot --filename=...`, `resize`, `goto`, `run-code`, `eval`, `requests`, `console`. Actual CLI help and skill reference were read. Config outputs only inside this audit. No test runner, dependency, axe library or instrumentation script was installed.

### Coverage matrix

All routes below are hash paths. D=1440×900, M=390×844, T=768×1024. Themes were genuinely selected through Settings, not simulated OS appearance. No touchscreen/mobile-UA/device-scale emulation is claimed.

| Screen/flow | View/theme | State and result | Status / evidence |
|---|---|---|---|
| Login `/` | D/M dark | Passkey/register/guest offered; guest chosen only in fresh context | CONFIRMED `login-*` |
| Home `/home` | D/M dark+light | First-use welcome/empty stats in dark; later disposable routine/resume in light | CONFIRMED `home-*`; not authenticated onboarding |
| Library `/library` | D/M dark+light, T dark | Desktop two-column generic list; mobile list; system exercise photos; no page horizontal overflow in measured viewports | CONFIRMED `library-*` |
| Library search/filter | M dark | `sentadilla`:431; +legs:388; detail opened from named result | CONFIRMED `library-search-*`, `library-filter-*`; query ranking differs v1.4.0 |
| Exercise detail sheet | D/M dark | Weight/reps/plates, guidance, expandable media; Escape dismisses | CONFIRMED `exercise-detail-*`; populated history/1RM not observed |
| Plan `/plan` | D/M dark | Fixed week, no user routines initially; Schedule/Routines control visible | CONFIRMED `plan-*`; rotation, combine and day assignment not exercised |
| Routine editor `/plan/r/<temporary>` | M/D light | Created AUDIT — disposable, one barbell squat; values auto-save; add exercise picker | CONFIRMED `routine-edit-*`, `exercise-picker-*`; picker Type row is v1.4.1, not v1.4.0 |
| Workout `/workout` | D/M dark initially | Start chooser and empty-state instructions | CONFIRMED `workout-*` |
| Active workout | D/M dark+light | Single-exercise default Cards; one set marked, running rest; no full completion | CONFIRMED `workout-active-*`, `workout-rest-*`; List/Compact/Focus/supersets/intensifiers SOURCE_ONLY |
| Finish confirmation | M light | Opened before logging: “nothing logged”; Cancel; no session saved | CONFIRMED `workout-finish-confirm-*`; successful completion/PR/source reduction not verified |
| History `/history` | D/M dark | Empty month/week navigator, outline color legend, no rows | CONFIRMED empty only `history-*` |
| Stats `/stats` | D/M dark | Empty summary/effort/volume/heatmap; desktop `.cols`, narrow mobile | CONFIRMED empty only `stats-*`; populated charts/tooltip accuracy UNKNOWN |
| Settings `/settings` | D/M dark | Guest hub/search/categories | CONFIRMED `settings-*` |
| Actual settings subpages | D/M dark | look,workout,alerts,plan,units,equipment,data,about | CONFIRMED initial controls; light look D/M; lower rows via snapshot |
| `settings/advanced`, `settings/account` | D/M dark | Returned to settings hub, not pages | No page coverage; misleading filename corrected by register/actual URL |
| Muscles `/muscles` | D/M dark | Front/back body diagram and grouping/filter affordances | CONFIRMED entry `muscles-*`; no recovery-state interaction |
| Structural balance | D/M dark | Explanatory empty metric state | CONFIRMED empty `structural-balance-*` |
| Photos, measurements, check-in | D/M dark | Empty entries and permissioned/acquisition affordances only | CONFIRMED empty `progress-photos-*`, `measurements-*`, `checkin-*`; no camera/files/photo access |
| Coach `/coach` | D/M dark | Redirect Home; API coach/status401 | **Blocked**; `coach-*` are Home screenshots, not Coach UI |
| Additional guarded routes | M/light final | Admin/proposal→Home; settings coach/setup/reminders→Settings; intake route stayed but empty snapshot | Partial/unknown [gated-routes.log](evidence/gated-routes.log); invalid routes versus permissions not inferred solely from redirect |
| Native/account/admin/offline/error/loading | — | No credentials/native runtime/failure injection | SOURCE_ONLY/UNKNOWN; no blanket coverage claim |

### Independent qualitative pass and static review

Assessment A was written **before** running the detector: [assessment-a.md](evidence/assessment-a.md). It carries `⚠️ DEGRADED: single-context (no sub-agent tool exposed).` There was no second agent or parallel independent critic. Source and visual review plus a subsequent static detector constitute distinct passes, not independent agents.

Impeccable's detector ran once over `ui.jsx`, `Modals.jsx`, `Login.jsx`; output [impeccable-detector.json](evidence/impeccable-detector.json) is `[]`. This narrow deterministic result means no matches in that scan, **not** no design/accessibility problems. The main critique came from actual UI observations and source tracing. No remote sidecar, overlay injection or screenshot upload.

## Findings, ranked (proposal only)

### F01 — Sheet semantics/focus do not match visual modality

**High · CONFIRMED · source unchanged in v1.4.0**. On opening ExerciseDetail, active element remained a background DIV. Next Tab focused background **Plan**, outside modal; zero `[role=dialog]`. Escape did dismiss the sheet. `C/Modals.jsx:48–143` has body pinning/dismissal but no common role/aria-modal, focus placement/containment/restoration or inert background. This can strand keyboard/assistive-tech users behind an opaque sheet. The visible2px focus ring itself works, so this is not “all keyboard access broken.” [interaction-observations.log](evidence/interaction-observations.log), `exercise-detail-mobile-dark.png`.

Proposed later work: one shared overlay accessibility contract, including nested/select/locked/viewer variants; regression checks for initial focus, Tab/Shift-Tab containment, Escape/back and return focus. Do not add an ad hoc trap in one screen or break scroll restoration. WCAG references: [Focus order](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html), [Name, role, value](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html).

### F02 — Several switch instances have no accessible name

**High · CONFIRMED · same source in v1.4.0**. Settings alerts and look each yielded three role=switch controls with no text/aria-label/aria-labelledby; snapshots expose unnamed switches. Visible row titles are adjacent, not labels. `ui.jsx Switch` forwards an accessible name if supplied, but `Settings.jsx` Sound/Vibration/Flash and look switches omit it. Paint is51×31; CSS `::before` expands ±7px (45px effective height), so **do not call it a31px touch target**. [accessibility-observations.log](evidence/accessibility-observations.log), `settings-alerts-mobile-dark.png`, `settings-look-mobile-light.png`.

Proposed: associate each instance with its visible row title without changing click/toggle semantics. Name/role/value reference above. Do not rewrite the switch merely because a caller omits a label.

### F03 — Light green accent is unsuitable for small text/tinted actions

**High · CONFIRMED for sampled control; cross-theme scope PARTIAL**. Library light “Por músculo” computes `#34c759`,15px/600, over16% green on `#f2f2f7`. Calculated contrast **~1.77:1**; same green on white **2.22:1**. Required normal-text AA is4.5:1; 15px/600 is not large text. Small green Plan actions/active-tab labels deserve the same audit. Dark green on black does not have this specific problem.

[evidence/interaction-observations.log](evidence/interaction-observations.log) captures actual styles; [contrast-calculations.json](evidence/contrast-calculations.json) shows compositing/method. This is computed-color math, not a full rendered-pixel scan. `.btn.tinted` in `index.css` and palette are unchanged between releases. Source comment `:15–18` calls17px/600 a large-text category and claims3:1 suffices; that rationale is **CONFLICTED**, not a norm. [Contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

Also `lib/accent.js` preset ink policy gives white on several light preset fills near2–4:1, using a3:1 adjustment target; custom accent thresholds do not certify normal button text either. These broader cases are SOURCE_ONLY pending matrix testing. Default light green primary uses **black** ink (~9.46:1), so “all green buttons fail” would be false. Preserve accent choice while separately deciding accessible ink/text roles; do not prescribe a replacement palette here.

### F04 — Zoom restriction is present; physical impact untested

**Medium · CONFIRMED configuration / SOURCE_ONLY consequence**. `frontend/index.html` and runtime viewport meta contain `user-scalable=no`. This risks pinch-zoom access on browsers that honor it; browser behavior differs. No physical-device pinch/browser zoom audit was performed. Propose review against [Resize text](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html), not an unqualified claim that every platform blocks zoom.

### F05 — Motion guidelines are partial, not a full accessibility policy

**Medium · CONFIRMED CSS suppression; SOURCE_ONLY exceptions**. Reduce emulation gives animation none, transition0s. Positive existing behavior. However JS smooth scrolling (DurationWheel/ui slider) and auto-playing media are not covered by global CSS; no physical reduced-motion/media playback verification. Regular sheet340ms, center280ms, repeating resume ping1.9s are real exceptions to header140–220ms. Propose explicitly classifying allowed motion/feedback and testing native/physical contexts, not deleting all feedback.

### F06 — Narrow-chip interaction density warrants real-touch testing

**Low / follow-up · CONFIRMED geometry, UNKNOWN usability**. Library chips are~30px tall and `::before inset:0 -6px` increases horizontal, not vertical, target. This is below the source's aspirational44px but not automatically below WCAG2.2's24px minimum. Rows, switches and many icon controls have expanded targets; do not score by paint alone. The row of filters can feel dense at390px, but only a pointer-driven headless audit was done. Confirm spacing/overlap and physical touch before changing density. [Target size minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

### F07 — Release and instruction drift is a maintenance risk

**Medium · CONFIRMED**. Current containers are1.4.1 while audit target is1.4.0. Some comments/proposals/locales counts and root instructions lag current source. Screenshot-derived standards could otherwise codify v1.4.1 fixes as old behavior or revive obsolete media/dependency assumptions. Mitigation is provenance plus owner-reviewed canonical document, not installing a new UI framework.

## Positive patterns to preserve

- Strong neutral surface hierarchy, restrained accent and meaningful colored category icons; no marketing-dashboard card explosion.
- Desktop widens lists/summary columns without discarding familiar bottom navigation; editors keep useful reading width. D/M/T measurements support this.
- Primary tasks are visible: add exercise, start session, resume and finish. Routine autosave avoids redundant Save; completed set/rest feedback acknowledges the action.
- Search/filter result counts and equipment/muscle metadata make a huge catalogue tractable; detail retains context through a sheet.
- Empty Home/history/stats/body pages explain next actions rather than presenting unexplained blank charts.
- Safe-area, keyboard insets, contained horizontal strips, reduced-motion CSS, fallback media, shared error recovery and Undo are existing mechanisms worth protecting. Some are source-only, not fully validated end-to-end.

## Diagnostic limits

Initial401 `/api/me` is expected unauthenticated bootstrap; `/api/coach/status`401 reflects access limitation, not proof of API outage. Final console additionally has third-party console wording about lazy image loading; no demonstrated layout/media failure. [browser-console.log](evidence/browser-console.log), [final-browser-console.log](evidence/final-browser-console.log), [final-browser-requests.log](evidence/final-browser-requests.log). Request log is a CLI request-buffer observation, not a packet capture or complete signed-in synchronization audit. No visual-regression baseline, screen reader, full contrast scan, long translations/RTL, browser zoom, offline simulation, native keyboard, performance benchmark or full training-path correctness test was run.
