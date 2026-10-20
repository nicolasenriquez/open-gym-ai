# Workout and history

Users log sets in a resumable workout and inspect the finished record and trends.

## Sub-features

- W01/W02: start, minimize, resume, reload, complete sets and finish.
- H01/H02: history entry and detail.
- W03-W08: free workout, partial finish, cancel, timers, notes, edit and backfill.
- A01: muscle/fatigue/structural analysis and periods.

## How to get to it (user POV)

- Home > Elegir otro entrenamiento > routine.
- Home's scheduled day card; Start/Empezar tab; free workout.
- Active workout > Minimizar > Seguir.
- Progreso > Todo <count> > saved workout; Home streak card also reaches progress.
- Progreso > structural balance / progress photos / measurements Abrir buttons.

## Driving it with Playwright CLI

Preconditions: P01 routine with squat, 3 × 10; no prior workouts in this browser.

- Start through Home chooser; click exact text E2E CLI Routine. Require Serie 1 hecha checkbox.
- Minimize and resume using buttons Minimizar and Seguir. Reload; active workout remains.
- Mark Serie 1 hecha, Serie 2 hecha, Serie 3 hecha via check commands.
- Completion: #modal-root button Terminar entrenamiento, wait for heading ¡Entrenamiento completado!, then ¡Genial!.
- History: Progreso > Todo 1; reload and open button matching /^E2E CLI Routine .*3 series/. Detail must show recorded sets.
- Proof: helpers/run.ps1 records W01/W02/H01/H02 and validates exported workout has three done sets.

## Gotchas

- The final set opens a sheet automatically. Clicking Terminar behind it times out correctly; resolve the sheet instead of forcing the click.
- The routine chooser row lacks button semantics in the audited build; exact visible text is the fallback locator.
- 0 kg volume is valid for an unweighted bodyweight squat. Do not fabricate a load merely to obtain a nonzero chart.
- Minutes and dates vary. Assert set counts and stored values; avoid fixed calendar dates and duration totals.
- Native rest alarms, background delivery and device wake lock need real-device verification.

