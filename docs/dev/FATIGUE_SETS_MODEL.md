---
type: Reference
title: Training fatigue — model rationale and invariants
description: Sets-based fatigue, effort provenance and history-dependent recovery invariants.
---
# Training fatigue — model rationale and invariants

This is the Training estimate in [`recovery.js`](../../frontend/src/lib/recovery.js),
not the future personal Recovery domain or a clinical assessment. It estimates
per-muscle fatigue from completed work; it does not measure readiness or predict injury.

## Why effective sets instead of tonnage

Tonnage can let heavy compounds dominate unrelated small-muscle work. The model uses
quality-weighted sets and muscle involvement, capped per session, rather than comparing
absolute weight × reps across exercises. Secondary movers contribute according to
`musclesOf`. Drop-set drops add work; rest-pause clusters do not add it again because
the parent row already contains their total. Completed warm-ups contribute with their
own effort rule, unlike volume/record/progression counters that exclude them.

## Effort and load interpretation

Logged RIR/RPE wins; an explicit failure marker supplies RIR 0 only without a logged
rating. Otherwise the model can estimate RIR by inverting an Epley capacity anchor
from the exercise's rolling history. Unknown effort remains unknown, not a fabricated
rating. Unrated warm-ups use the floor weight; other unknowable effort receives full
set credit. Easier estimated/rated work is discounted, with a nonzero floor.

Loads are canonicalized to kg before comparison, using available set/target/entry/
workout stamps and profile fallback. Bodyweight-configured work includes body mass
from the workout, then profile context, then the source-defined fallback. Assisted work
is excluded from strength anchors. Do not interpret assistance load as lifted weight.
Constants, rep limits and precedence live in source, not a second table in this document.

## Time and adaptation

- `history.js` owns `workoutAt`; a real zero timestamp and a date-only workout at
  local noon must not be replaced by truthiness or UTC-midnight shortcuts.
- A rolling capacity anchor is computed at each session, never from future work.
- A bounded acute/chronic gain accounts for recent exposure with a novice prior.
- Effective stimuli decay chronologically by per-muscle half-life and map through
  `1 - exp(-v)`; muscle groups intentionally have different half-lives.
- The stimulus scan is shorter than its information pool. Source currently retains
  30 days of scored work plus the 90-day anchor lookback. Shortening the pool to
  the stimulus scan can make fatigue rise during rest when an anchor ages out.

## Invariants and deliberate limits

Rest must not increase fatigue. Imports outside the full information pool must not
affect it. Deleting the chronologically latest session must not increase fatigue;
“latest” means maximum timestamp, not final array position.

**Deleting a mid-history session may re-score later work.** Removing a capacity anchor
or chronic exposure changes later estimates. The earlier universal deletion-monotonicity
claim was superseded by this history-dependent model; do not restore it as an invariant.
Current catalogue muscle metadata is used when available, with entry snapshots for
deleted exercises. These choices make the model interpretable, not clinically validated.

## Stats and verification

[`effort.js`](../../frontend/src/lib/effort.js) uses logged ratings by default and can
accept the shared resolver from `recovery.js`. Stats must label estimated values and
show rating/estimate coverage rather than presenting every set as user-rated.

Use the [recovery tests](../../frontend/src/lib/recovery.test.js),
[view tests](../../frontend/src/lib/recovery-view.test.js) and
[effort tests](../../frontend/src/lib/effort.test.js). From `frontend/`, run
`pnpm run test:fatigue-probe` for the synthetic monotonicity probe. Its
[source](../../frontend/scripts/fatigue-monotonic-probe.mjs) owns the comparison matrix.
Private histories and one-off calibration results are not test fixtures or acceptance
proof. Record actual results against the tested revision separately.

## Background, not clinical guarantees

Original rationale drew on [sets/dose-response](https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877),
[muscle recovery](https://pmc.ncbi.nlm.nih.gov/articles/PMC6719818),
[training adaptation](https://pmc.ncbi.nlm.nih.gov/articles/PMC5023708) and
[protein-synthesis response](https://pmc.ncbi.nlm.nih.gov/articles/PMC5401959).
Acute/chronic normalization is a modeling heuristic, not an injury predictor; see
[ACWR background](https://pmc.ncbi.nlm.nih.gov/articles/PMC8138569) and
[criticism](https://www.globalperformanceinsights.com/post/has-the-acute-chronic-workload-ratio-been-debunked).
These sources motivate choices; they do not validate the app's constants or an
individual user's recovery time.
