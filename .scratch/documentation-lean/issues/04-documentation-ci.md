# Evaluar comprobación documental en CI

Status: needs-triage

## Pregunta

¿Se debe ejecutar OKF en CI también para cambios exclusivamente documentales?

## Contexto

El mantenimiento actual es local según `docs/operations/okf-authoring-guide.md`.
La auditoría de deuda previa señaló que `.github/workflows/test.yml` no ejecutaba
la suite/check OKF ni cubría cambios solo documentales. No se cambia CI como parte
de la limpieza editorial. Confirmar configuración vigente antes de implementar.

## Cierre

Acordar triggers y Node soportado; reutilizar `node scripts/docs/okf.mjs check` y
`node --test scripts/docs/okf.test.mjs`, sin dependencias ni infraestructura nueva.
Verificar ejecución para cambios de docs/herramienta y revisar filtros de paths.
El check estructural no certifica exactitud semántica ni aceptación de plataforma.
