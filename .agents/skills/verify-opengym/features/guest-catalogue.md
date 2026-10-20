# Guest and catalogue

Users can train without an account and discover exercises by search, filters and muscles.

## Sub-features

- G01/G02: enter guest mode and see an empty Home.
- L01/L02: search without matches, inspect a known exercise and close its sheet.
- L03: combine body-part, type and equipment filters; clear them.
- L04: open muscle explorer and reach an exercise.
- C01: gym membership card import/scanning.

## How to get to it (user POV)

- Login > Continuar sin cuenta > Inicio.
- Ejercicios tab > search, filters, exercise row, Por músculo.
- Home > En el gimnasio Registrarse > Añadir tarjeta.

## Driving it with Playwright CLI

Preconditions: fresh session; use -s=<owned-session> on every command.

- Enter: `playwright-cli -s=opengym-manual click "getByRole('button', {name:'Continuar sin cuenta',exact:true})"`; Home shows guest notice and welcome actions.
- Catalogue: click the navigation button Ejercicios, fill textbox Buscar… with squat, then click the exact button sentadilla (squat) cuádriceps · peso corporal Plan. The sheet shows Añadir a mi plan, Historial and exercise instructions.
- Empty search: fill Buscar… with zzzz-e2e-no-match; require a zero-results signal and absence of exercise rows, then Borrar restores results.
- Escape: `playwright-cli -s=opengym-manual press Escape`; sheet disappears, library remains.
- Proof: run helpers/run.ps1 for G01/G02/L01/L02 screenshots and ARIA output; L03/L04/C01 require separate actions and evidence.

## Gotchas

- Catalogue includes nested Plan buttons: scope navigation to getByRole('navigation').
- Library search is Buscar…; exercise picker search is Buscar entre <count> ejercicios…; use /Buscar entre/ rather than a fixed catalogue count.
- Exercise names include English parentheses by default; instructions may explicitly remain English.
- Known audit bug: detail sheet has no dialog role and focus can remain on the background after Tab.
- Camera/card import needs a synthetic QR fixture and permission handling; do not scan a personal membership card for test data.

