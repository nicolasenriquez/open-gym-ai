# OpenGym verification map

Run from repository root. Spanish UI, kg units, fresh ephemeral named browser at http://localhost:8080. All values are synthetic; no account is created. Start with the skill's doctor. Guest mutations stay in the isolated browser, while requests for config, catalogue and session health still reach the shared local server.

## Features

- [Guest and catalogue](guest-catalogue.md): login, empty Home, search/filter/detail, muscle browser and gym card.
- [Plan and routines](plan-routines.md): create/edit, schedule, starter plan, rotation.
- [Workout and history](workout-history.md): start, resume, sets, finish, history and analysis.
- [Body tracking](body-tracking.md): bodyweight, measurements and progress photos.
- [Settings and backup](settings-backup.md): search, preferences, export/import and gated features.

## Coverage contract

The run.ps1 helper proves one connected journey across these files. It does not prove every listed sub-feature. Detailed IDs, expected outcomes and current statuses live in docs/audit/opengym-e2e-2026-10-20/test-cases.md. A feature with several entry points needs each entry checked; success through Home does not verify the Start tab or exercise-to-plan shortcut.

Each proof records case ID, preconditions, actions, ARIA/screenshot, resulting state and persistence check. Never mark conditional account/mobile/permission scenarios passed from a guest screenshot. Evidence survives browser teardown. All named sessions must have one driver.

