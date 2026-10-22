## Why

La arquitectura aprobada requiere demostrar conectividad, migraciones, aislamiento y recuperación PostgreSQL antes de migrar identidad y Training. Hoy la API y sus consumidores dependen de archivos JSON y no existe una base PostgreSQL verificada; este cambio prepara esa base sin modificar la autoridad de los datos actuales.

## What Changes

- Incorporar una superficie aislada y reproducible de ensayo PostgreSQL, exclusivamente con datos sintéticos; alcance local/CI confirmado por el usuario durante esta especificación.
- Preparar pool y transacciones Node/ESM con `pg`, límites, cierre y errores sin secretos.
- Preparar ejecución controlada de `node-pg-migrate`, historial único y credenciales separadas del runtime; probar concurrencia, fallo e interrupción.
- Demostrar privilegios mínimos y RLS mediante fixtures desechables, sin anticipar el esquema funcional Recovery.
- Ensayar respaldo consistente, cifrado, transferencia a destino de prueba y restauración aislada con verificación.
- Incorporar pruebas PostgreSQL reales en CI y documentar resultados, límites y pendientes del gate G1.

## Capabilities

### New Capabilities

- `postgres-foundation`: entorno sintético, conexiones, transacciones, roles, migraciones, pruebas de aislamiento, respaldo/restauración y evidencia operativa.

### Modified Capabilities

Ninguna. No existen main specs actualmente. No cambian los requisitos HTTP, autenticación, Training, coach, MCP ni medios.

## Impact

Cambio de tipo runtime, cuya implementación posterior afectará módulos nuevos de persistencia y herramientas de API, dependencias/lockfile, entorno de ensayo separado, CI y documentación operativa. Esta etapa solo elabora especificaciones.

Fuentes: `docs/open-gym-evolution.architecture.md` §§3, 7–12 y 14.1; `docs/open-gym-recovery.prd.md`; `GLOSSARY.md`. Commits de contexto: `3cc0e9d5` (arquitectura/PRD aprobados), `f2f83c16` (benchmark complementario), `56731cd9` (pruebas portables/POSIX).

Quedan fuera: corte de persistencia, importación de usuarios/Training, políticas reales Recovery, interfaz Recovery, cambios de origen/passkeys, proveedor contratado, despliegue, garantía RPO/RTO y satisfacción de G0/G2–G5. G1 operativo seguirá pendiente si el proveedor objetivo no se valida. La aprobación de esta especificación no autoriza implementar.
