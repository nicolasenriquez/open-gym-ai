---
type: Reference
title: UI accessibility contracts and regression checks
description: Coach routing, routine keyboard activation and shared modal behavior with repeatable browser checks.
---
# UI accessibility contracts and regression checks

## Implemented behavior

The current implementation and its regression helpers cover these contracts; run the
checks against the served checkout before claiming a result:

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

## Sources and verification limits

- [`Modals.jsx`](../../frontend/src/components/Modals.jsx) owns dialog lifecycle,
  stacking and dismissal; [`Toast.jsx`](../../frontend/src/components/Toast.jsx)
  routes feedback into the active dialog.
- [`CoachIntake.jsx`](../../frontend/src/views/CoachIntake.jsx) owns the guarded
  redirect; [`Workout.jsx`](../../frontend/src/views/Workout.jsx) owns routine selection.
- [`verify-ui-fixes.js`](../../frontend/scripts/verify-ui-fixes.js) owns browser
  assertions; the [guest verification skill](../../.agents/skills/verify-opengym/SKILL.md)
  covers the separate connected persistence journey.

Vitest's LinkeDOM modal tests stub only `showModal`/`close` lifecycle calls; they do
not simulate browser focus or inertness. Those assertions belong to the real-browser
helper. Media component tests cover arrow navigation; the nested browser viewer
check owns focus regression. Store results with the tested revision and environment
in run artifacts or the PR, not as accumulating test totals in this reference.
