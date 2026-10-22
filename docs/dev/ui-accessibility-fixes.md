---
type: Reference
title: UI accessibility fixes — 2026-10-20
description: Recorded accessibility fixes and checks from 2026-10-20.
---
# UI accessibility fixes — 2026-10-20

Three isolated fixes address the guest audit findings:

1. Coach intake redirects in an effect after store readiness. Real-router tests cover cold guest access, disabled Coach and delayed initialization.
2. Other routines use native non-submit buttons. Browser verification reaches them with Tab and starts a real routine with Enter and Space.
3. The shared sheet wrapper uses native modal dialogs for sheets, centered confirmations and media viewers. Existing history, drag and scroll bookkeeping stays in Modals. Native cancel is intercepted so `locked` and store-driven closure remain authoritative. The viewer retains its media arrow navigation and delegates focus to the wrapper.

Toasts portal into the upper dialog while it is open. This keeps validation messages and the real Undo action visible and operable above the native modal layer. No DOM nodes are manually moved and no dependencies or storage formats change.

## Repeatable browser regression

Serve the checkout, rather than testing an older web image. From `frontend/` in a dedicated terminal:

```powershell
$env:API_TARGET='http://localhost:8080'
npm.cmd run dev -- --host 127.0.0.1 --port 4174 --strictPort
```

The existing local stack supplies API health/config; all browser mutations use isolated guest profiles. From the repository root:

```powershell
$session = 'opengym-fixes-' + [DateTime]::UtcNow.ToString('yyyyMMddHHmmssfff')
playwright-cli "-s=$session" open http://127.0.0.1:4174 --browser=msedge
try {
  $output = & playwright-cli "-s=$session" run-code --filename=frontend/scripts/verify-ui-fixes.js
  $output | Set-Content .playwright-cli/ui-fixes-result.log -Encoding utf8
  $json = $output | Where-Object { $_.StartsWith('{"passed":') } | Select-Object -Last 1
  if (!$json) { throw 'No structured proof; inspect .playwright-cli/ui-fixes-result.log' }
  $result = $json | ConvertFrom-Json
  if ($result.passed.Count -ne 13 -or $result.warnings.Count -ne 0) { throw 'Incomplete or failed regression proof' }
} finally {
  playwright-cli "-s=$session" close
}
```

The CLI can print `### Error` without a failing exit code. Require the structured result, not just process success. The helper closes both child contexts in `finally`; the caller closes its named session. Stop only the Vite process started for this verification with Ctrl+C. Do not stop the existing Compose stack or clear the user's browser.

The 13 checkpoints cover Coach, both routine keyboard activations, and the following modal scenarios at desktop width 1280 and mobile viewport width 390:

- Initial focus, Tab/Shift+Tab, background and lower-sheet focus rejection, and opener focus restoration.
- Two stacked sheets; Escape, browser Back, backdrop click and drag each dismiss one layer.
- Empty measurement validation toast inside the active dialog.
- Keyboard adjustment and saving of the real rest-duration wheel.
- Removal of a set and its genuine Undo action inside another sheet.
- Locked finish summary resisting Escape and Back; a synthetic uploaded image opens a nested viewer and closing it restores focus to its thumbnail.

Native dialogs may yield focus to browser chrome. The test accepts that only when `document.hasFocus()` is false; focusing any background page control is a failure. It also rejects uncaught runtime errors in either child context. The uploaded image is a screenshot of synthetic test data, ingested through the production file input, without internal state setters.

Screenshots, synthetic media and console output survive cleanup under `.playwright-cli/ui-fixes-*`. The 390px run is viewport emulation, not a physical Android/iOS or Safari test. Native WebView, soft-keyboard and assistive-technology checks remain device-level follow-up work.

## Validation recorded

- 94 directed Vitest tests passed across eight files, including existing modal history/scroll/gesture tests and new real-router, routine-button, cancel-lock and toast-portal regressions.
- The 13 browser checkpoints passed in Edge against the checkout; no uncaught runtime errors were observed in the isolated scenarios.
- The existing guest journey passed 17 checkpoints against port 4174. Its real exported JSON contained one completed three-set workout, bodyweight 72.5, waist 85 and no active workout.
- Production build passed. Locale check passed: 18 locales, 2258 keys each.
- Full frontend run: 401 files passed, 3 files failed; 5051 tests passed, 10 failed. The same failures were reproduced using a separate archived copy of the pre-fix commit `666d9080` with the same dependencies/runtime: nine shell-spawn tests in `api-base.test.js`, one calendar-note assertion in `sheets.day-note.test.jsx`, and a parse failure loading `check-mobile-bundle.test.mjs`. They were not changed as part of these fixes. Logs: `.playwright-cli/frontend-regressions.log` and `.playwright-cli/baseline-failures.log`.

Vitest's LinkeDOM modal tests stub only `showModal`/`close` lifecycle calls; they do not claim to simulate browser focus or inertness. Those assertions belong to the real-browser helper. The media component test now checks arrow navigation; the nested browser viewer test owns its focus regression.
