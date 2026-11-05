# Settings and backup

Users find preferences, persist appearance choices and export/import local data.

## Sub-features

- S01/S02: settings search and persisted light theme.
- D01: export JSON with recorded synthetic values.
- D02-D05: import/merge conflict, malformed backup, CSV and destructive reset.
- X01-X04: gated auth, sync, Coach and native features.

## How to get to it (user POV)

- Home > Ajustes gear > search or category row.
- Datos y copias > Exportar copia (JSON), Importar copia, Importar de otra app.
- Guest account card or sign-in banner > authentication.
- Equipment, units, workout, timer alerts, fine-tuning and appearance pages.

## Driving it with Playwright CLI

Preconditions: synthetic guest records from the smoke journey.

- Search: open Ajustes; fill Buscar en Ajustes with Tema and inspect the returned preference result.
- Appearance: /#/settings/look > Claro; reload and require document.documentElement.dataset.theme === light.
- Export: /#/settings/data > Exportar copia (JSON), await page.waitForEvent('download'), download.saveAs a proof path. Verify its parsed JSON contains the routine, completed session, 72.5 kg and waist 85.
- Proof: helpers/run.ps1 records S01/S02/D01 and validates the download after closing the browser.
- Manual exploration: use snapshot refs for rows, because some row controls are not semantic buttons.

## Gotchas

- Spanish labels and browser download support are preconditions for supplied selectors.
- JSON export is guest data backup; it must not be treated as proof of server account sync.
- Never import or reset in the user's browser. Import tests need a second isolated browser and a reviewed synthetic backup.
- Guests do not see reminders; /settings/reminders redirects to Settings. /admin and unavailable /coach/intake redirect Home; web /coach/setup redirects Settings. Verify both the final route and a nonblank screen.
- Real passkey creation, cross-device linking, push delivery, provider credentials and Capacitor shells remain conditional. No account/provider is provisioned by this skill.

