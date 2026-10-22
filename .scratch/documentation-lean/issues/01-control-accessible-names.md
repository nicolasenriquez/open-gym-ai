# Revalidar nombres accesibles de switches

Status: needs-triage

## Pregunta

¿Los switches de Ajustes > Alertas y Aspecto tienen nombre accesible asociado a su
etiqueta visible en la revisión servida?

## Contexto y alcance

La revisión visual del 2026-10-19 observó tres switches sin nombre en cada pantalla
sobre runtime v1.4.1; no se reejecutó durante la limpieza documental. La fuente
inspeccionada entonces era v1.4.0 `28b7e4dc`. Es evidencia histórica, no un defecto
actual confirmado. Inspeccionar `frontend/src/views/Settings.jsx` y
`frontend/src/components/ui.jsx` y sus tests antes de actuar.

## Cierre

Reproducir con navegador/perfil sintético y árbol de accesibilidad. Si persiste,
asociar el nombre visible sin cambiar semántica de toggle y añadir prueba en su
frontera. Si ya está corregido, cerrar con revisión/prueba identificables. No tocar
el wrapper de diálogos: su regresión vive en `docs/dev/ui-accessibility-fixes.md`.
