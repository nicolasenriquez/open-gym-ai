---
type: Reference
title: 'Set types: drop sets, rest-pause and failure'
description: Set representation, intensifier planning, counting rules and compatibility limits.
---
# Set types: drop sets, rest-pause and failure

[`workout-model.js`](../../frontend/src/lib/workout-model.js) owns row shapes and
pure helpers; [`history.js`](../../frontend/src/lib/history.js) owns planned rows and
volume. This reference explains their distinctions, not a completed implementation plan.

## Independent dimensions

- `phase`: work or warm-up; legacy `warmup: true` remains readable.
- `type`: straight (default), dropset or restpause.
- `failure: true`: independent mark, written only when on. A drop-set or rest-pause
  can also be taken to failure; a warm-up is not a failure set.

Per-side rows carry actual left/right results in `sides`; their aggregate weight/reps
are for display, not a substitute for each limb's load when summing work.

## Extra work versus breakdown

```js
// Drops are additional work beyond the main row.
{ type: 'dropset', w: 100, r: 5, done: true,
  drops: [{ w: 80, r: 5 }, { w: 64, r: 5 }] }

// Clusters decompose the row's own total; never add them again.
{ type: 'restpause', w: 60, r: 12, done: true,
  clusters: [{ r: 6, restSec: 15 }, { r: 3, restSec: 15 },
    { r: 2, restSec: 15 }, { r: 1, restSec: 15 }] }
```

`extraVolumeOf` adds drop-set work and returns zero for rest-pause clusters.
`splitBurstReps` divides a total into bursts that sum back to it. UI edits to bursts
must also update the parent total; drop edits must not change the independent main
set's reps. Per-side intensifiers apply to each limb and resynchronize the aggregate.

## Planning and live edits

The shared exercise configuration saves `cfg.intensifier`. A drop-set plan applies
its descending chain to work rows. A rest-pause plan replaces the configured set list
with a warm-up and one rest-pause work row, not one protocol per requested set.
For per-side work, the configured total is split between limbs, including odd totals.

`applyIntensifierPlan` must run after prescription: drops depend on the final weight,
not the pre-progression seed. The exercise's loading grid also constrains drops.
The builder then applies `lastToFailure` to the last unlogged work row; a timed
left/right pair is marked together. Cardio is excluded from that failure plan.

[`Workout.jsx`](../../frontend/src/views/Workout.jsx) renders editable drop/burst
subrows and allows additions to unplanned straight sets. Rest-pause rests are
self-timed rather than a dedicated burst countdown. The exercise's `restSec` overrides
the profile rest-pause default.

An appended progression row may retain its planned type but must not copy already
logged drops/clusters from its seed. Those are work performed, not reusable results.

## Counting rules and limits

| Consumer | Interpretation |
| --- | --- |
| Volume | Completed work at each limb's actual load, plus drops; clusters already included in total reps; warm-ups excluded |
| Fatigue | Completed quality-weighted sets; drops add work; clusters do not double-count; warm-ups have their own effort rule |
| Progression and 1RM | Read row results, not an additional sum of nested clusters |
| Failure effort | Logged RIR/RPE wins; otherwise failure supplies RIR 0 |
| Muscle-balance map | Uses its own effective-set model; do not silently replace it with tonnage |

A rest-pause total is not necessarily comparable to a straight-set rep target.
The original design left progression grading against `target.reps` as a limitation,
not a validated training policy. Likewise, total reps above `onerm.js`'s rep cap do
not yield a 1RM estimate. Revisit those behaviors explicitly before changing them;
neither is fixed by adding clusters to the total again.

## Persistence, translation and verification

Persist row fields with the existing Training document. Preserve legacy shapes;
redeployment does not migrate or clear a running workout's local state. For testing
schema changes use a fresh disposable profile/session, not instructions to discard
someone's active workout. MCP shares domain helpers, so counting changes can affect
its results too.

UI strings follow the repository's all-locales rule and locale check; there is no
feature-specific English-fallback exception. Keep data interpretation in pure helpers
with adjacent tests: [workout model](../../frontend/src/lib/workout-model.test.js),
[history](../../frontend/src/lib/history.test.js),
[session construction](../../frontend/src/lib/session-start.test.js),
[progression](../../frontend/src/lib/progression.test.js),
[effort](../../frontend/src/lib/effort.test.js) and
[fatigue](../../frontend/src/lib/recovery.test.js).

Selecting specific planned sets for an intensifier, rather than the current exercise
configuration, is a separate product change. Imports must preserve supported meanings;
capabilities of external formats should be checked in their importers, not inferred
from this model.
