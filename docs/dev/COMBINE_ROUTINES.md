---
type: Reference
title: Combine routines — session model and compatibility
description: Ordered routine composition, progression exclusion and compatible planner and history readers.
---
# Combine routines — session model and compatibility

A combined workout concatenates entries from several routines into **one session**.
There is no composite-routine entity. This reference describes the implemented model;
source and adjacent tests own algorithm details, not the original implementation tickets.

## 1. Model

- `S.week[weekday]` holds routine IDs in merge order. Readers also accept legacy strings.
- `S.dayPlan[iso]` remains scalar: a routine ID, `'rest'`, or no override.
- Active sessions carry `routineIds`; entries carry their originating `rid`.
- Completed workouts retain `routineIds`, the legacy `routineId` mirror of the first
  ID, and each entry's `rid`/`noProg` when present.
- No mass migration rewrites existing profiles. Missing legacy fields remain readable.

## 2. Building entries

[`session-merge.js`](../../frontend/src/lib/session-merge.js) resolves ordered IDs,
deduplicates routine IDs (first wins), drops missing routines, builds each routine and
stamps its entries with `rid`. Repeated **exercise** IDs across routines are retained.
An empty routine list supports freestyle; a single-item list uses the same path.

[`session-start.js`](../../frontend/src/lib/session-start.js) owns prescription,
planned targets and row construction. Reuse that builder rather than copying its code
into a caller. `deriveSessionName` joins up to three names; longer lists show the first
two and the remaining count. Source owns the exact formatting.

## 3. Entry points

[`sheets.jsx`](../../frontend/src/sheets.jsx) owns live start, past-workout start and
adding a routine to a running session. Added blocks preserve the current position;
already-added and empty routines are unavailable in the add-routine picker. Past-workout
logging can select the planned combined day; it is not limited to the original
single-routine design.

[`Workout.jsx`](../../frontend/src/views/Workout.jsx) owns the header menu and
exercise additions. Layout selection is under `⋮ → Layout`; see
[workout views](LIST_VIEW.md) for layout state ownership.

## 4. Planner resolution

[`history.js`](../../frontend/src/lib/history.js) owns `effectiveRoutineIds`,
`effectiveRoutines`, singular compatibility wrappers and `nextTrainingDay`. Use those
helpers instead of inferring the day's session directly from `week`: rotation queue
and pinned-session semantics also participate in resolution.

A day is trainable when any resolved routine has exercises. Weekly counts are not
simply the number of routine IDs. Calendar/queue tally rules belong to their helpers.

## 5. Sharing and deletion

[`plan-share.js`](../../frontend/src/lib/plan-share.js) exports ordered day lists and
remaps every routine ID on import, including legacy scalar values. Do not sort the
inner list: order is part of the plan. Removing the final routine from a fixed-week
slot removes the key rather than writing an empty array. Deleting a routine must also
clean planner references without rewriting saved history.

## 6. Progression exclusion

`history.js` exposes `entryExcluded(w, entry)`: legacy whole-workout exclusion or
per-entry `noProg`. Exclusion suppresses progression/session read-back baselines,
not the fact that work occurred or its record weight.

- An excluded source routine builds its entries without a prescription and stamps `noProg`.
- An exercise menu can exclude one entry for this session without rebuilding its rows.
- [`session-noprog.js`](../../frontend/src/lib/session-noprog.js) distinguishes a whole-session
  choice (`active.noProg`) from independent entry choices; later additions join a whole-session
  exclusion. Turning the session choice off preserves routine-owned exclusions.
- A freehand add inherits the current block's `rid` and routine-owned exclusion;
  an independently excluded entry does not by itself exclude the new one.
- A swap preserves routine attribution. Rebuilding uses `builtOutOfProgression` to
  distinguish routine-owned exclusion from a manual flag; it must not reset today's load.

[`finish-workout.js`](../../frontend/src/lib/finish-workout.js) preserves the entry
flags and emits the legacy `excludeFromProgression` mirror only when every completed
entry is excluded. Mixed sessions omit it. `active.noProg` is not a saved field.

## 7. Coach fingerprint

Client [`coach.js`](../../frontend/src/lib/coach.js) and server
[`payload.js`](../../shared/coach-core/payload.js)/
[`plan-hash.js`](../../shared/coach-core/plan-hash.js) must agree on canonical plan and
fingerprint. Scalar and one-item-list days normalize identically; combined-day order
is significant. A Coach `week` operation remains scalar and replaces a day, rather
than composing several routines. See the [Coach guide](../AI_COACH.md).

## 8. Data-model invariants and limitations

Keep `dayPlan` scalar. A normal per-date override naming one routine replaces a
scheduled combined day with that routine (or rest); queue pins have their own resolver
semantics. A one-off combination remains possible by adding a routine during a workout.

Keep entry attribution and per-entry exclusion through start, add, swap, rebuild,
completion and history. Grouped history uses entry `rid`; old records without it stay
readable as an implicit group. Readers tolerate stray empty arrays as rest, while
fixed-week writers remove empty slots. Never rewrite imported history just to enforce
new-shape consistency.

## Verification

Start with adjacent tests for [merging](../../frontend/src/lib/session-merge.test.js),
[session building](../../frontend/src/lib/session-start.test.js),
[session exclusion](../../frontend/src/lib/session-noprog.test.js),
[history](../../frontend/src/lib/history.test.js),
[completion](../../frontend/src/lib/finish-workout.test.js),
[plan sharing](../../frontend/src/lib/plan-share.test.js) and
[Coach parity](../../frontend/src/lib/coach-parity.test.js).
Component/browser checks must exercise both scheduled and in-session entry points,
including mixed exclusions, duplicate exercises and legacy records. Test results
belong to the tested revision's run artifacts, not a permanent completed checklist.
