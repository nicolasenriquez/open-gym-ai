---
name: verify-opengym
description: Verify OpenGym web guest workflows with Playwright CLI, capture real UI and persistence evidence, and use the feature map for regressions.
---

# Verify OpenGym

Primary surface: React PWA served with the API at http://localhost:8080. API, optional read-only MCP, Capacitor shells, authenticated sync and Coach need separate verification. Read [features/README.md](features/README.md) before selecting coverage.

## Launch

Run from repository root in PowerShell. Use an existing healthy local stack for guest tests; browser state is isolated, server identity is shared. If no stack exists, follow README: copy .env.example to .env only when absent, then `docker compose up -d --build`. Wait for /api/health to return ok:true. Record whether this run started the stack. Never rebuild or stop an existing user stack as routine cleanup.

Installed harness on the audited Windows host: `playwright-cli` 0.1.19 and Edge. Check `playwright-cli --version`. If absent, consult the project's playwright-cli skill before installing anything.

Run the proven guest journey (creates its own ephemeral browser; closes it even on failure):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/verify-opengym/helpers/run.ps1
```
Do not run two copies against the same named session. This helper uses a unique name per run, and does not attach to the Codex browser. Edge may require approved host execution outside the Windows sandbox; sandbox launch exited before navigation on the audited host. Do not weaken browser or OS security to work around that.

## Doctor

The helper first reads /api/health through page.request, checks ok:true, requires the visible Spanish button "Continuar sin cuenta", and verifies there is no guest, state or account in its new browser. Abort on a wrong origin, populated profile, missing UI, or unhealthy API. UI language must be Spanish and units kg for the supplied selectors. The audit saw web v1.4.1; inspect Settings > About for the running version. A live build may differ from checkout HEAD; report both instead of assuming equality.

## Drive

The helper invokes `playwright-cli -s=<unique> run-code --filename=.agents/skills/verify-opengym/helpers/guest-smoke.js`. This is a Playwright function expression, not an @playwright/test spec. It exercises guest entry, catalogue, custom routine, Monday schedule, workout start/resume/reload/finish, history, bodyweight, measurements, appearance and JSON export. It uses real UI actions; page.evaluate only reads state.

For additional mapped entry points, open a separate named session:
```powershell
playwright-cli -s=opengym-manual open http://localhost:8080 --browser=msedge
playwright-cli -s=opengym-manual snapshot
playwright-cli -s=opengym-manual click "getByRole('button', { name: 'Continuar sin cuenta', exact: true })"
```
Use fresh snapshot refs or the scoped selectors in the map. Scope tab buttons to navigation: catalogue rows also have buttons named Plan. Scope sheet actions to #modal-root: the background remains in the accessibility tree. Completing the last set opens a completion sheet automatically; choose its Terminar entrenamiento before ¡Genial!.

## Evidence

The helper prints a log path under .playwright-cli/verify-opengym-<run>.log. The JSON result includes per-case ARIA snapshots, completion status, API health and errors; screenshots and a synthetic backup use timestamped .playwright-cli/opengym-* paths. The PowerShell helper fails unless completed:true, screenshots exist, and the downloaded JSON contains the created workout, routine, weight and measurement.

Proof means the action plus its resulting state, a reload or second user-facing view for persistence, and an observed export for stored data. A toast or screenshot alone does not prove a save. Do not seed through localStorage setters, app stores, mocks or hidden endpoints. Keep credentials, cookies and storage-state dumps out of tracked evidence. Copy only reviewed synthetic artifacts into a dated docs/audit folder when delivering an audit. Report unexecuted paths as pending; route rendering is not full feature coverage.

## Cleanup

The runner closes only the browser session it opened in finally. Ephemeral guest state disappears with that browser. Evidence remains in .playwright-cli/ and the runner checks it after close. For manual sessions: `playwright-cli -s=opengym-manual close`. Do not use close-all, kill-all or process-name kills.

If this run alone started a disposable Compose stack, `docker compose stop` stops it without removing volumes. Do not remove data/, coach-auth/, user browser storage or existing stacks.

## Helpers

- `helpers/run.ps1`: launch, execute, validate downloaded synthetic JSON, cleanup, verify evidence survives; invoke as shown above.
- `helpers/guest-smoke.js`: UI journey called by run-code; requires a fresh named browser at the fixed local origin.
- [Feature map](features/README.md): additional entry points and pending cases.
- [Audit and test cases](../../../docs/audit/opengym-e2e-2026-10-20/README.md): observed limits and regressions.

