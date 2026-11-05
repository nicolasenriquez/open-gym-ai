# Plan and routines

Users build routines and assign them to fixed weekdays or a rotation.

## Sub-features

- P01/P02: create a named routine, add an exercise, reload.
- P03: assign a routine to Monday, reload.
- P04/P05: starter plans and rotation.
- P06/P07: copy, reorder, delete, supersets, progression and exercise settings.

## How to get to it (user POV)

- Home > Crear mi propio plan; Home > Cargar plan inicial.
- Plan > Rutinas > Nueva rutina; existing routine row opens its editor.
- Plan > Horario > weekday; Semana fija / Rotación.
- Catalogue detail > Añadir a mi plan; catalogue row's Plan shortcut.
- Settings > Plan y horario.

## Driving it with Playwright CLI

Preconditions: guest profile with no E2E CLI Routine; helpers/run.ps1 owns its profile.

- Create: Plan navigation > Rutinas > Nueva rutina; fill the editor's sole textbox E2E CLI Routine. Changes autosave.
- Add: Añadir ejercicio; scope to #modal-root and fill textbox /Buscar entre/ with squat; click Añadir «sentadilla (squat)». Press Escape. Editor shows sentadilla (squat) 3 × 10.
- Persist: reload; name and 3 × 10 must remain. No explicit save button exists here.
- Schedule: navigation Plan > Horario > Lunes; click E2E CLI Routine 1 ejercicio then Listo in #modal-root. Reload and inspect Lunes text for the routine.
- Proof: helpers/run.ps1 records P01/P02/P03; other entry points need their own proof.

## Gotchas

- Opening Nueva rutina immediately creates a routine; closing is not a cancel action.
- Monday assignment does not imply today's workout. Home's Elegir otro entrenamiento is weekday independent.
- Rotation and starter plan replacement affect many settings. Use a separate empty browser, not the user's guest state.
- Dynamic routine IDs are generated; do not hardcode a /plan/r/<id> from an old audit.

