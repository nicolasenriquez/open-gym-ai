## Why

La arquitectura aprobada requiere demostrar conectividad, migraciones, aislamiento y recuperación PostgreSQL antes de migrar identidad y Training. La API y sus consumidores siguen dependiendo de archivos JSON. Este cambio entrega una base PostgreSQL verificada únicamente en el entorno sintético, sin modificar la autoridad de los datos actuales.

Su evidencia prepara el handoff de `migrate-opengym-persistence` descrito en la arquitectura §14; no acredita el reemplazo de la persistencia existente ni autoriza retirar su código o eliminar sus datos. Las condiciones de retirada y conservación del origen pertenecen a la arquitectura §§9 y 11–12.

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

Ninguna. Se añade la capability postgres-foundation sin modificar requisitos HTTP, autenticación, Training, coach, MCP ni medios.

## Impact

Cambio runtime implementado y verificado en alcance sintético: módulos y herramientas aislados en api/foundation/, dependencias/lockfile propios, Compose separado, integración CI y documentación. Las 18 tareas están completadas; resultados, fallos y límites están consolidados en design.md. La API normal y su persistencia JSON no cambian.

Fuentes: `docs/open-gym-evolution.architecture.md` §§3, 7–12 y 14.1; `docs/open-gym-recovery.prd.md`; `GLOSSARY.md`. Commits de contexto: `3cc0e9d5` (arquitectura/PRD aprobados), `f2f83c16` (benchmark complementario), `56731cd9` (pruebas portables/POSIX).

Quedan fuera: corte de persistencia, importación de usuarios/Training, políticas reales Recovery, interfaz Recovery, cambios de origen/passkeys, proveedor contratado, despliegue, garantía RPO/RTO y satisfacción de G0/G2–G5. G1 operativo seguirá pendiente si el proveedor objetivo no se valida. El cierre autorizado cubre sync/archive del cambio sintético, no corte de persistencia, despliegue ni satisfacción de gates operativos.
