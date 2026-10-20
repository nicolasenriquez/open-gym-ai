# Body tracking

Users record weight and measurements and attach progress photos to workouts.

## Sub-features

- B01: record bodyweight and reload.
- B02/B03: reject empty measurements; persist a valid value.
- B04-B06: goals, custom fields, dates and conversions.
- F01: photo attachment, gallery, before/after and removal.

## How to get to it (user POV)

- Home > Peso corporal > Registrar or Meta.
- Progreso > Peso corporal > Registrar, Meta, Todos los pesajes.
- Progreso > Medidas corporales > Abrir > Registrar / Campos.
- Progreso > Fotos de progreso > Abrir; completed workout > Añadir foto o vídeo.

## Driving it with Playwright CLI

Preconditions: owned guest browser, kg/cm; no measurements today.

- Weight: Home Registrar > textbox Peso (kg) = 72.5 > #modal-root Guardar; reload and require 72,5.
- Measurements: Progreso card with heading Medidas corporales > Abrir > Registrar. Click Guardar empty; require Introduce al menos una medida and form remains.
- Valid measure: textbox Cintura cm = 85 > Guardar; reload and require 85 cm. Empty fields must remain empty in export.
- Proof: helpers/run.ps1 records B01/B02/B03 and checks synthetic values in JSON backup.

## Gotchas

- Home and measurements both have Registrar; navigate first and scope modal Guardar.
- Photo gallery reads photos attached to workouts, not a separate unlinked collection. A workout today is needed for the shortcut.
- Use generated synthetic images for uploads; never personal body photos.
- Permission and real file workflows remain pending until exercised with an owned fixture.

