---
type: Audit
title: 02 — Source design system and reusable UI inventory
description: Historical inventory of source design tokens and reusable UI.
---
# 02 — Source design system and reusable UI inventory

## Scope and evidence notation

Primary release source: **`v1.4.0` / `28b7e4dc`**, accessed with `git show`. Working-tree references are HEAD v1.4.1 unless qualified. The source CSS copy [evidence/index.v1.4.0.css](evidence/index.v1.4.0.css) preserves release-exact line numbers; HEAD lines after 236 are one higher. Runtime is **v1.4.1**, never v1.4.0. CONFIRMED means source and this runtime support a pattern, not that the release build itself was rendered or that the product owner approved every detail.

Status vocabulary: **CONFIRMED**, **SOURCE_ONLY**, **RUNTIME_ONLY**, **CONFLICTED**, **UNKNOWN**. No significant RUNTIME_ONLY pattern remained without a source location.

## Architecture and explicit principles

Verified expected locations exist: `frontend/src/{index.css,App.jsx,views,components,store,lib,locales}` and `frontend/package.json`. React 19, Vite, React Router HashRouter, Zustand, handwritten global CSS; no Tailwind/shadcn/component framework. Native Capacitor dependencies, QR and barcode helpers also exist: the instruction shorthand “React + Router + Zustand and nothing else” is a dependency-restraint principle, not a complete package inventory.

`frontend/src/index.css:1–18` explicitly establishes:

1. One type scale, mostly regular weight; titles versus content distinguished by size/meaning.
2. A neutral surface ramp; spend color on accent/status.
3. Hairlines rather than outlined boxes; inset list dividers after the icon rail.
4. Motion acknowledges interaction, not decoration; approximately 2% press scale, 140–220ms ease-out.

These are documented intentions, not invented brand metaphors. Qualify them: CSS `:151–154` says unused `.t-*` typography utilities were deliberately deleted rather than changing screens. `.hdr h1` is 700, buttons 600; sheet entrances are 340ms and center entrances 280ms. Thus “one scale” and “140–220ms everywhere” must not be canonized literally. No formal spacing scale or reusable typography-role token set exists.

## Token catalogue

All entries below are in **`frontend/src/index.css`**; selectors and release line ranges are given. Exact originals remain in the evidence CSS; do not normalize away alpha/color-mix expressions.

### Foundations, text and geometry (`:root:21–67`, light `:71–91`)

| Token | Dark/default | Light override | Purpose |
|---|---|---|---|
| `--bg` | `#000000` | `#f2f2f7` | Page ground |
| `--bg-el` | `#0e0e10` | `#f7f7fa` | Elevated backdrop/bars/sheets; light sheets locally use `--bg` |
| `--surface` | `#1c1c1e` | `#ffffff` | Card / inset group |
| `--surface-2` | `#2c2c2e` | `#ececef` | Nested/pressed surface |
| `--surface-3` | `#3a3a3c` | `#e3e3e8` | Segmented track / off switch |
| `--label` | `#ffffff` | `#000000` | Primary text |
| `--label-2` | `rgba(235,235,245,.60)` | `rgba(60,60,67,.60)` | Secondary text |
| `--label-3` | `rgba(235,235,245,.32)` | `rgba(60,60,67,.30)` | Dim/tertiary text; contrast not guaranteed |
| `--label-4` | `rgba(235,235,245,.18)` | `rgba(60,60,67,.16)` | Faint/decorative control details |
| `--sep` | `rgba(84,84,88,.60)` | `rgba(60,60,67,.29)` | Separators |
| `--sep-op` | `rgba(84,84,88,.34)` | `rgba(60,60,67,.20)` | Blur-surface edges |
| `--hair` | `.5px` | inherited | Separator thickness |
| `--r-sm`, `--r`, `--r-lg`, `--r-xl`, `--r-card` | `8px`, `12px`, `16px`, `22px`, `14px` | inherited | Small controls; default controls; large groups/dialogs; sheet top corners; cards |
| `--pad` | `16px` | inherited | Page inline padding |
| `--icon-stroke` | `1.7` | inherited | Default SVG line weight, context overrides exist |
| `--ease` | `cubic-bezier(.32,.72,0,1)` | inherited | Acknowledgment/entrance easing |
| `--fast`, `--med` | `140ms`, `220ms` | inherited | Normal control and view transitions |
| `--sat`, `--sab` | `max(env(safe-area-inset-… ,0px),var(--native-sa…,0px))` | inherited | Native/browser safe-area accommodation |
| `--conn` | `0px`, set at runtime | inherited | Connection-banner reserved height |

Semantic/system palette (`:root:41–43`, light `:86–88`):

| Token | Dark | Light | Existing role examples |
|---|---|---|---|
| `--blue` | `#0a84ff` | `#007aff` | Check-in, data, information |
| `--green` | `#30d158` | `#34c759` | Default accent / completed state |
| `--red` | `#ff453a` | `#ff3b30` | Destructive/error |
| `--orange` | `#ff9f0a` | `#ff9500` | Active workout / warnings / overrides |
| `--yellow` | `#ffd60a` | `#ffcc00` | Favorite star / warnings |
| `--teal` | `#40c8e0` | `#30b0c7` | Equipment/body-map settings |
| `--indigo` | `#5e5ce6` | `#5856d6` | Day note / equipment category |
| `--pink` | `#ff375f` | `#ff2d55` | Sound category |
| `--purple` | `#bf5af2` | `#af52de` | Failure F / effort / look |
| `--mint` | `#63e6e2` | `#00c7be` | Exercise-chip settings tint |
| `--brown` | `#ac8e68` | `#a2845e` | Available system palette; no universal semantic claim |
| `--grey` | `#8e8e93` | same | Neutral category icon |

Accent (`:root:46–50`, `[data-accent=…]:94–116`): `--acc:var(--green)`, `--acc-2:#248a3d`, `--on-acc:#000000`; `--acc-soft:color-mix(in srgb,var(--acc) 16%,transparent)`, `--acc-line:color-mix(in srgb,var(--acc) 38%,transparent)`. Preset keys: **lime, sky, orange, violet, pink, red, teal, gold**. `lime` names green, not the old yellow-lime brand. Light root uses white `--on-acc`, then active accent selectors override; lime and teal explicitly use black. Do not omit the data-accent layer when interpreting a token.

`lib/accent.js` and `lib/format.js` own preset/custom validation, stored `accentCustom`, theme adjustment and ink selection. Custom color is six-digit hex, not arbitrary CSS. Presets are not passed through custom contrast adjustment. Light/dark/system are persisted `S.theme`; `App.jsx resolveTheme/applyPrefs` resolves system preference to `data-theme` and updates meta/native bars. **CONFIRMED** for dark/light lime via real settings; other accents/custom/system live-change are **SOURCE_ONLY**.

### Type, spacing, surfaces and states

| Rule | Source selector/location | Value / purpose | Status |
|---|---|---|---|
| System typography | CSS `html`, `body:119–133` | Root 16px; body 17px / 1.29, tracking −.01em, tabular numerals; `-apple-system,BlinkMacSystemFont,'SF Pro Text','SF Pro Display','Segoe UI',Roboto,system-ui,sans-serif` | CONFIRMED computed stack; actual Windows glyph font not independently identified |
| Page heading | `.hdr h1:237–239` | 34px / 1.06, 700, −.028em; 30px ≤420px; wrapping title block | CONFIRMED |
| Small/title metadata | `.small`, `.hdr .sub`, `.sect-t`, `.lrow-t/.lrow-s`, `.item .tt/.ss` | 13px/1.38; subtitle 15; section 13/400; row 17 plus 13; exercise row 16/400 plus 13 | CONFIRMED; no global `h2` size inference |
| Numeric emphasis | `.card .big`, `.bw-read`, workout set CSS | Card 30px/600; weigh-in 52px/600; domain-specific sizes | Card layout confirmed; weigh-in editor SOURCE_ONLY |
| Card/group | `.card`, `.sect-b:290–310` | 14px radius; card padding16/margin-bottom12; group clips children | CONFIRMED |
| Row | `.lrow:312+` | min-height46, padding11px14px, gap12; `.5px` inset divider at14px or55px after icons | CONFIRMED |
| Buttons | `.btn:365–387` | 17px/600, padding14px18px/r12; small 15px/8px14px/r8; xs13px/5px10px/r7 | CONFIRMED primary/tinted/plain; danger SOURCE_ONLY as reusable variant |
| Press/disabled/focus | `.btn:active`, `.iconbtn`, `:focus-visible`, `.field:focus` | Scale .975 or .92, alternate surface/accent; button disabled .32; focus ring2.5px +2px offset, field inset2px | CONFIRMED keyboard ring presence; computed outline rounded to2px in this browser |
| Non-touch hover | `@media(hover:hover)` and pointer-fine queries | No sticky hover on touch; drag cursor/grip and Today row hover | SOURCE_ONLY fine-pointer intent; desktop rendering confirmed |
| Elevation | `.sw .knob`, `.seg-sel`, `.center`, `#timer`, desktop `#tabbar` | Local literal shadows; cards flat. E.g knob `0 3px 8px rgba(0,0,0,.15),0 1px 1px rgba(0,0,0,.16)`; centered dialog `0 20px 60px -12px rgba(0,0,0,.5)` | CONFIRMED layered surfaces, no named shadow-token scale |
| Reduced motion | CSS `:147` | All CSS animations/transitions disabled under reduce | CONFIRMED computed animation none, transition0s; JS smooth scroll and media not proven reduced |
| Entrance exceptions | `.sheet`, `.center`, `#app.vfade`, `.start.rec .cir::after` | 340ms sheet, 280ms dialog, 220ms viewfade; 1.9s repeating resume ping | CONFIRMED sheet/session appearance, durations SOURCE_ONLY except reduce test |

Spacing is component-based, not a proven 4/8px grid: 7px chip gap, 12px row gap, 14px desktop column gap and 18px sheet sides coexist. Do not fabricate spacing tokens. White exercise picture backgrounds are an intentional catalogue-media exception (`.thumb`, `.catvid`), not failed dark mode. Local control whites/shadows and semantic chart series are not automatically defects.

## Responsive contract

CSS `#app:163+`: centered **max560px**, inline16px, safe/banner-aware top, bottom88px+safe area. `.resting` and `.no-tabbar` change bottom reserve. Desktop `@media(min-width:1000px):1906+`: app max1080px, top32px+banner; `.narrow` max640px; full lists two columns, `.cols` two columns/gap14; narrow/sheet/routine lists stay single-column. Floating tab bar width520/bottom16/r22; desktop sheets640px centered horizontally, still docked at bottom. Mobile tab bar is full-width at bottom. **CONFIRMED** at1440×900 and390×844; at768×1024 app560/tab768, confirming the middle state. No desktop sidebar exists.

Other CSS query thresholds are **local fit exceptions**, not general design breakpoints: ≤420 title/settings, ≤360 library count, ≤400/429/359 and360–365 set-grid adaptations, ≤479 timer layout, ≤404 workout chips, ≤399/359 timer controls. Inspect their local selectors before reusing them. Exercise cards use `repeat(auto-fill,minmax(150px,1fr))`; they are not the desktop generic two-column rule. Physical touch/keyboard/safe areas remain SOURCE_ONLY.

## Component inventory and reuse assessment

Full release-exact declarations/props/import consumers for **35 files** are in [evidence/component-reference.v1.4.0.json](evidence/component-reference.v1.4.0.json). This is a static import index, not a dynamic call graph; declarations include internal functions. The table below supplies behavioral/reuse interpretation. Paths prefixed **C/** mean `frontend/src/components/`; **V/** means `frontend/src/views/`; **S/** means `frontend/src/sheets.jsx`. Common theme behavior: token-driven; common responsive behavior: inherits container except where stated. Do not interpret “shared” as “approved with no accessibility defects.” Screenshot basenames link through [evidence/screenshots.md](evidence/screenshots.md).

### Primitives in `C/ui.jsx` (actual exports)

| Name / props | Consumers and visual/interaction role | Theme/responsive / reuse / runtime |
|---|---|---|
| `Button(variant='plain',size,icon,trailingIcon,children,className,...rest)` | Login, settings, sheets, all main views; maps classes, not a native submit contract | primary/tinted/danger/ghost/plain; sm/xs CSS; shared; CONFIRMED login/library/workout. **Default plain is not filled secondary** |
| `TextField`, `TextArea(className,...rest)` | Settings/forms/notes; field/area with forwarded native props; TextField ref | Shared; `.field`/`.input` legacy styles coexist; plain form states SOURCE_ONLY |
| `SearchField(value,onChange,onClear,...rest)` | Settings and select sheets; magnifier plus conditional Clear | Shared; responsive width; CONFIRMED settings; Library uses legacy `.search` instead |
| `NumberField(value,onChange,decimal,nullable,fit,...)` | Stepper, session/config, weight entry; comma decimal, local focused draft, select-on-focus | Shared domain control; CONFIRMED workout; nullable/fit SOURCE_ONLY |
| `Switch(checked,onChange,disabled,...accessibility)` | Settings, routine deload; button role switch, aria-checked, immediate callback | Shared 51×31 paint; CONFIRMED, several callers unnamed (03) |
| `Segmented(options,value,onChange,className)` | Plan, settings, Stats; controlled selection, aria-pressed and sliding thumb | Shared; inline wraps below title; CONFIRMED; not ARIA tabs by default |
| `Stepper(value,step,min,max,onChange,decimal,label,unit,invalid,disabled,onStep,ariaLabel,...)` | Workout, ExConfig; hold-repeat, accelerated steps, clamp on blur; optional domain step callback | Shared; unit-aware; CONFIRMED workout appearance, hold acceleration SOURCE_ONLY |
| `Slider(value,min,max,step,onChange,disabled,...)` | Sheets/custom controls; pointer capture, role slider, arrow keys mirror RTL | Shared; SOURCE_ONLY; not a native range replacement to reinvent |
| `Check(checked,onChange,size,label,...)` | Set completion; button role checkbox and labeled set | Shared; CONFIRMED one set marked; set handlers own rest/progression |
| `Section(title,footer,children,...)` | Settings and sheets; semantic section, inset group, optional explanatory footer | Core shared structural primitive; CONFIRMED |
| `Row(icon,iconTint,title,subtitle,value,accessory,onClick,danger,children,...)` | Settings/config; button only if onClick, otherwise div; chevron/check accessories | Core shared row; value ellipsizes, title wraps; CONFIRMED |
| `SelectRow(...title,value,options,onChange,sheetTitle,stackedValue,search)` | Settings/stats/config; opens SelectSheet; selecting closes then commits | Shared; keyboard-aware searchable sheet; SOURCE_ONLY selection contract; row rendering CONFIRMED |
| `MultiSelectRow(...values,options,onToggle,noneLabel,doneLabel)` | Additive exercise metadata | Local sheet mirror updates check immediately, **onToggle persists per tap**, Done only closes; SOURCE_ONLY |

### Shared infrastructure/domain UI

| Component / exact file | Props / consumers / behavior | Reuse, theme/responsive and evidence |
|---|---|---|
| `Icon` / `C/Icon.jsx` | name,size,className,style; inline SVG paths, hidden decoration | Shared vocabulary; currentColor/1em/stroke token; CONFIRMED across screens |
| `TabBar` / `C/TabBar.jsx` | onStart; Shell; Home/Plan/Start/Stats/Library, route families map active tab, running resume | Shared shell, not a sidebar; CONFIRMED home/workout screenshots; hides during active session |
| `Modals`, internal `Sheet` / `C/Modals.jsx` | useUI sheet stack: render,kind,locked,id; backdrop/center/sheet/viewer; Escape/back/swipe; body pin and scroll restore | Shared overlay infrastructure; desktop640/mobile-full; CONFIRMED exercise detail and finish prompt; no common dialog semantics/focus trap |
| `Toast` / `C/Toast.jsx` | useUI msg/action; role status, optional Undo pauses on pointer | Shared feedback; initial status exists, message/action SOURCE_ONLY (not tested Undo) |
| `SyncBanner` / `C/SyncBanner.jsx` | store/config; connection/local/guest states, reserved --conn height, can dismiss | Shared; quiet line versus warning fill deliberate; CONFIRMED guest banner |
| `ErrorBoundary` / `C/ErrorBoundary.jsx` | children; Shell route-key reset, reload and optional discard fallback | Shared recoverability; SOURCE_ONLY, no error injected |
| `Elapsed` / `C/Elapsed.jsx` | start; TabBar/Workout running clock | Shared time display; CONFIRMED active session/resume |
| `RestTimer` / `C/RestTimer.jsx` | useUI state; adjust, pause, skip, ±15s; durationSheet | Shared shell-owned dock, no-tabs variation; CONFIRMED rest screenshot; sounds/native alarms not verified |
| `TimerFlash` / `C/TimerFlash.jsx` | store/UI flash option | Native/web feedback surface; SOURCE_ONLY, no flash triggered intentionally |
| `Media`, `Thumb` / `C/Media.jsx` | ex,id,compact,minimizable; library/sheets/workout | Builtin/custom split, autoplay/pause, fallback still/tile, lazy decorative thumbs; CONFIRMED detail/list; v1.4.1 internals differ (clip caching/app format) |
| `CustomMedia` / `C/CustomMedia.jsx` | ex,id,compact,minimizable; Media/WorkoutMedia; exports CustomThumb, MediaView, LinkCard | Shared custom file/link display; SOURCE_ONLY, no user media accessed |
| `CustomMediaField` / `C/CustomMediaField.jsx` | media,url,onChange; sheets/workout/progress photos | Shared acquisition/form field; SOURCE_ONLY, no permission/upload/file picker |
| `ExerciseViewToggle` / `C/ExerciseViewToggle.jsx` | store exerciseView; Library/picker/MuscleExplorer | Shared list/cards preference, **persisting action**; visible CONFIRMED, switch not exercised |
| `BodyMap` / `C/BodyMap.jsx` | load,thresholds,body,onMuscle,selected,className; explorer/stats/editor/sheets | Shared SVG muscle view, diagram not generic icon; CONFIRMED empty muscle explorer, loaded fatigue states SOURCE_ONLY |
| `MuscleExplorer` / `C/MuscleExplorer.jsx` | onPick,onDetail,onPlan; Muscles/picker | Shared body-map-plus-exercise discovery; CONFIRMED entry, pick/filter sequence not exercised |
| `Heatmap` / `C/Heatmap.jsx` | S,onDay,metric,onMetricChange; Stats | Shared yearly activity representation, horizontally contained; CONFIRMED empty grid, populated click SOURCE_ONLY |
| `LineChart` / `C/LineChart.jsx` | points,h,unit,color,axes,goal,invert,series; Home/Stats/Measurements/sheets/coach | Shared SVG chart340 viewBox, responsive width, bounded tooltip; **only empty chart state observed**, point tooltips SOURCE_ONLY |
| `SwipeCards` / `C/SwipeCards.jsx` | index,onChange,count,children; Workout | Shared session paging; SOURCE_ONLY gesture; single-card rendering observed |
| `SwipeRow` / `C/SwipeRow.jsx` | action/direction/disabled props (exact signature in JSON); Plan/editor/Workout | Shared swipe/Undo affordance, RTL-sensitive; CONFIRMED painted set rows, physical gestures SOURCE_ONLY |
| `QueueRow` / `C/QueueRow.jsx` | S,today,onStart,managed; Home | Rotation/externally-managed queue view; SOURCE_ONLY, fixed-week empty profile observed |
| `WorkoutChips` / `C/WorkoutChips.jsx` | entries/units/current selection callbacks, see JSON; Workout | Numbered progress dots, current/partial/done; CONFIRMED one exercise |
| `WorkoutThumb` / `C/WorkoutThumb.jsx` | exercise/expand callback, see JSON; Workout | Small media header control; CONFIRMED active session |
| `WorkoutScrollAnchor` / `C/WorkoutScrollAnchor.jsx` | layout/session anchor helpers; Workout | Behavior infrastructure, no independent visual primitive; SOURCE_ONLY |
| `WorkoutSettingsSheet` / `C/WorkoutSettingsSheet.jsx` | close/session settings; Workout options | Shared in-session preferences, domain-sensitive; SOURCE_ONLY internal controls |
| `WorkoutMedia` / `C/WorkoutMedia.jsx` | workout media acquisition/gallery/viewer; Workout/sheets | Shared session attachment UI; SOURCE_ONLY, no photos captured |
| `DurationWheel` / `C/DurationWheel.jsx` | value,onChange,min,max,off,readRef; settings/rest/config | Shared two spinbutton scroll-snap wheels; durationSheet uses onDone commit; SOURCE_ONLY wheel (row entry observed) |
| `Passkeys` / `C/Passkeys.jsx` | hooks/row/sheet components; Login/settings | Account management and one-time pairing; SOURCE_ONLY, no credentials generated |
| `PasswordAuth` / `C/PasswordAuth.jsx` | configuration/forms/proof/error helpers; Login/settings/server sync | Optional account UI, not a general form primitive; SOURCE_ONLY, not offered in observed login |
| `ServerSync` / `C/ServerSync.jsx` | connectionView,section,owed/kept-change sheets; Settings/banner/onboarding | Preserve ownership/pending-data safety contracts; SOURCE_ONLY authenticated states |
| `BackupFolderRow` / `C/BackupFolderRow.jsx` | Settings; native backup folder/status | Shared native settings row; SOURCE_ONLY, browser unavailable |
| `QrCanvas` / `C/QrCanvas.jsx` | value,size,className; Passkeys/CheckIn | Shared QR rendering; SOURCE_ONLY (empty check-in observed) |
| `CameraScan` / `C/CameraScan.jsx` | onFound,onCancel; CheckIn/scan helper | Permissioned camera surface; SOURCE_ONLY, never requested camera |
| `NumField`, `Stepper` / `C/{NumField,Stepper}.jsx` | Re-export NumberField/Stepper from ui.jsx | **Compatibility aliases, not duplicate implementations** |

### Screen-specific and sheet-composed patterns

- `V/Home.jsx`: `.narrow`, Today/week card, first-use welcome, weight card, streak. Not a reusable Dashboard component. `V/Plan.jsx`: Schedule/Routines, fixed week/rotation; `gym_plan_view` persists per-device **even though it looks like navigation**. `V/RoutineEdit.jsx`: auto-save name/exercises, always single-column, reorder/grip/arrows and linked supersets. No Save button by design. Confirmed disposable edit, no reorder/delete tested.
- `V/Workout.jsx`: StartChooser versus ActiveWorkout/ExerciseBlock; Cards/List/Compact and `V/FocusView.jsx`+`FocusView.css`. All layouts share completion pipeline. Only default Cards and one marked set/rest observed; other layouts SOURCE_ONLY. `docs/dev/LIST_VIEW.md` explains session snapshot versus saved default, so do not collapse these into one setting.
- `S/ConfirmDialog`, `confirmSheet`, `MenuSheet/menuSheet`: shared composition over Modals, not separate global dialog engines. Confirm/cancel/danger callbacks; locked behavior is per instance. Finish's “nothing logged” prompt observed; destructive confirmation execution not tested.
- `S/ExerciseDetail`, `exerciseDetailSheet`, `ExerciseHistory`, `OneRM`, `detailTags`: reused by Library, workout menus and pickers; actual detail also includes **persisting plate settings**, favorite and add-to-plan. Opening it is safe in this isolated profile; changing those controls is not inherently read-only.
- `S/ExercisePicker`: reuse for routine/workout add/swap; row opens configuration, separate + quick-add; query/filter/chosen/favorites/same-muscle options. **v1.4.0 has no Type row in this picker** (Library already does). v1.4.1 screenshot with Type is evidence of the release fix, not v1.4.0 behavior.
- `S/ExConfig`, `ProgressionFields`, bar/dumbbell/plate inventories: domain-owned planning controls, not generic forms to reconstruct. Intensifier/failure/timed/per-side/units behavior belongs in helpers. `S/DayAssign`, `DayOverride`, `Calendar`, `WorkoutDetail`, `WorkoutRow`, `BwSheet`, `GoalSheet`, `WeighIns`, notes, starter/import/export sheets are reusable feature compositions; unexercised states SOURCE_ONLY.
- `V/History.jsx`, `Stats.jsx`, `StructuralBalance.jsx`, `Measurements.jsx`, `ProgressPhotos.jsx`, `CheckIn.jsx`: share primitives but own page composition/data rules. Populated history/charts/photos/check-in not verified. Admin/coach/mobile onboarding are conditional, not universal navigation destinations.

## Existing UX contracts (do not change as “visual cleanup”)

| Contract | Evidence / classification |
|---|---|
| Hash navigation; forward top/back stored scroll; route-keyed ErrorBoundary; tabs remain escape route outside workout | `App.jsx`, TabBar; CONFIRMED route navigation, scroll-restoration SOURCE_ONLY |
| Sheet backdrop, Escape, browser back dismiss top unless locked; pin background scroll; swipe checks axis and scrollTop | `Modals.jsx`; CONFIRMED Escape only; backdrop/back/physical swipe SOURCE_ONLY |
| Single select closes and commits; multi-select persists every toggle; buttons controlled value/onChange | `ui.jsx`; SOURCE_ONLY interaction specifics |
| Library search/filter use component state; clear and All reset different subsets; unavailable filter fallback rather than dead end | `Library.jsx`, `sheets.jsx`; CONFIRMED search431 → legs388; clear/fallback SOURCE_ONLY |
| Routine fields save immediately; ExConfig buffers until save; workout edit departure asks; active session reload is durable | `RoutineEdit.jsx`, `sheets.jsx`, App exit guard, store; CONFIRMED routine survived navigation/session survived reload; edit-history guard SOURCE_ONLY |
| Finish prompts; completing a set drives rest/advancement via existing domain pipeline; active workout hides tabs | Workout/sheets/useUI; CONFIRMED one set/rest and unsaved finish prompt; no full completion claimed |
| Store persists gym_state_v1, sync uses ownership/revisions/stamps; UI store ephemeral except selected durable timers | useStore/useUI + README; SOURCE_ONLY signed-in behavior, guest local verified |
| Toast/status and explicit connection banner; failed media falls back; error boundary does not blank shell | Toast/SyncBanner/Media/ErrorBoundary; guest banner CONFIRMED, failure/recovery states SOURCE_ONLY |

## Drift, duplicates and historical exceptions

1. Legacy `.search .input` in Library/picker and `SearchField` in settings are two real implementations sharing visual intent. They differ in result-count, keyboard handling and contexts; investigate before consolidation.
2. `.chk` and `.ck` CSS, raw fields/rows and local header styles exist beside ui.jsx. Not every repetition warrants a new abstraction; trace actual callers first.
3. `Button` default `plain` plus `.dim` can still compute accent text because `.btn.ghost/.plain` wins specificity. Login screenshot confirms the result. Do not assume passed className always overrides a variant.
4. CSS header's contrast rationale misclassifies17px/600 as large text; do not reproduce it as accessibility guidance (03).
5. `docs/dev/COMBINE_ROUTINES.md` explicitly starts as a proposed spec and contains older/contradictory details, including three-layout lists, mid-session noProg statements and planner surfaces. Read implemented code/tests for current behavior rather than making this old proposal normative. `SET_TYPES.md` similarly contains historical locale counts; CONTRIBUTING's all-locales requirement wins.
6. README/CHANGELOG v1.4.0 media/catalogue supersede stale CLAUDE.md media-service/1324-exercise shorthand. Record, do not modify instructions during this audit.
