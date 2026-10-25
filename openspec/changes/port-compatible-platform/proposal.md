## Why

El diseño de esquema SQL y operación local ya fue confirmado por el promotor.
Foundation prepara infraestructura y caracterización sintéticas, pero no porta
capacidades ni demuestra recuperación operativa. Hace falta convertir el diseño
acordado en requisitos y slices posteriores, sin ampliar Foundation ni presentar
la aprobación documental como implementación.

## What Changes

- Portar capacidades actuales por módulos con identidad mínima antes del piloto
  Training, frontend conservado y paridad verificable contra la referencia Node.
- Implementar en su fase el esquema aprobado, sus restricciones/índices, contratos
  de autorización, limpieza externa recuperable.
- Conservar JS neutral en shared/coach-core, catálogo, import/export, offline,
  providers coach y clientes admitidos con diferencias expresamente resueltas.
- Entregar imágenes/ambientes locales separados, diagnóstico privado, backup y
  restauración coordinados; ensayar corte, autoridad única y retirada posterior.
- Mantener Recovery, Garmin, IA ampliada, despliegue remoto y arm64 fuera de la
  primera aceptación, tratando soporte/clientes actuales expresamente.

**Estado:** cambio planificado; solo creación/actualización documental autorizada.
Todas sus tareas runtime están pendientes. Depende de terminar Foundation y preparar
los casos/seams de cada slice; no se declara Implementation Ready por validar
Markdown. Inventario real, acceso a datos, ejecución del corte o borrado requieren
su autorización operativa posterior. No cambia el estado de trabajo de Foundation.

## Capabilities

### New Capabilities

- `compatible-platform-persistence`: esquema y port modular compatible de identidad,
  Training, notificaciones, coach, auditoría y consumidores.
- `local-platform-operation`: ambientes/roles/imágenes, respaldo, restauración,
  diagnóstico, corte y retirada verificables para la instancia personal local.

### Modified Capabilities

Ninguna sincronizada todavía. La Foundation PostgreSQL histórica y sus specs
vigentes se conservan; estas deltas no acreditan entrega ni cambian el runtime actual.

## Impact

Futura implementación en backend Python, frontend intervenido por recorrido, shared,
Alembic, contenedores, CI y documentación operativa. Esta revisión escribe
únicamente documentación/OpenSpec; no añade dependencias, código, SQL ejecutable,
credenciales, programaciones, migraciones, imágenes ni datos reales.

Autoridad: [PRD](../../../docs/open-gym-evolution.prd.md),
[arquitectura](../../../docs/open-gym-evolution.architecture.md),
[esquema](../../../docs/reference/platform-schema.md),
[seguridad](../../../docs/reference/platform-security.md),
[operación](../../../docs/reference/platform-operations.md) y
[modularidad](../../../docs/reference/platform-modularity.md).
Foundation está completada en [su cambio archivado](../archive/2026-10-25-add-python-platform-foundation/proposal.md).
Contribución esperada EV-01–EV-09 y G0/G1 operativo/GP/GO/G2/G3, todos sin acreditar
por esta especificación. Recovery solo comienza después del cierre de plataforma.
