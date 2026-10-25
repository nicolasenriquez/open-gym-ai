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
  coach local y proveedores HTTP actuales; Claude Agent SDK/Codex CLI quedan
  temporalmente no disponibles por aprobación expresa Q6, sin fallback Node ni
  conversión de credenciales o selección a otros proveedores.
- Entregar imágenes/ambientes separados, logging estándar/diagnóstico privado y
  backup con parada controlada de escritores por wrapper host; mantener copias
  cada 3 h, al arranque si vencidas y antes de migrar, cifrado/retención/restore.
- Extender el harness Foundation por slice sin duplicar cleanup; no anticipar
  browser ni exporter/almacén de telemetría propios.
- Entregar port funcional y operación local recuperable como checkpoints separados;
  ensayar corte/retirada sintéticos y transferir S11 a cambio operativo autorizado.
- Restore: continuidad con evidencia o nueva vía local explícitamente autorizada,
  sin reactivar credenciales históricas dudosas ni elevar roles. Especificar
  autorización/entrega privada antes de ese slice; sin ledger nuevo. Conservar
  reparación hacia adelante tras nuevas escrituras, sin exportador inverso a Node.
- Entregar cleanup revisado del código sustituido y temporales propios antes de
  aceptación, preservando biblioteca neutral, pruebas útiles y recuperación protegida;
  no basta desactivar la implementación anterior ni se autoriza borrar originales.
- Mantener Recovery, Garmin, IA ampliada, despliegue remoto y arm64 fuera de la
  primera aceptación, tratando soporte/clientes actuales expresamente. No entregar
  launcher SDK/CLI, perfil seccomp coach ni scaffolding LangChain/LangGraph; mostrar
  la excepción en cliente/administración y conservar configuración e historia de los
  diferidos y originales protegidos sin activar sus credenciales.

**Estado:** cambio planificado; autoría documental y diagnóstico sintético acotado
Q4/Q5 autorizados, no implementación.
Todas sus tareas runtime están pendientes. Usa el handoff de Foundation archivada;
el [plan ejecutable](execution-plan.md) conserva casos y trazabilidad con readiness
por slice. S11 queda pendiente de transferencia explícita antes de archive; completar
ensayos no acepta plataforma ni autoriza Recovery. DDL/funciones conservan permisos;
no duplicar reglas Python/SQL ni funciones por simetría. Selección/configuración de
retención estándar y autorización/entrega privada de acceso nuevo son prerrequisitos
pendientes antes de S9/10.5, no requisitos del harness inicial. Validar Markdown no
resuelve esos contratos ni demuestra producto. Inventario real, acceso a datos, ejecución del corte o borrado requieren
su autorización operativa posterior. No reabre ni modifica la evidencia de Foundation.

## Capabilities

### New Capabilities

- `compatible-platform-persistence`: esquema y port modular compatible de identidad,
  Training, notificaciones, coach, auditoría y consumidores vigentes, con cleanup
  verificable; sin reconstruir el consumidor MCP retirado.
- `local-platform-operation`: ambientes/roles/imágenes, respaldo, restauración,
  diagnóstico, corte y retirada verificables para la instancia personal local.

### Modified Capabilities

Ninguna sincronizada todavía. La Foundation PostgreSQL histórica y sus specs
vigentes se conservan; estas deltas no acreditan entrega ni cambian el runtime actual.

## Impact

Futura implementación en backend Python, frontend intervenido por recorrido, shared,
Alembic, contenedores, CI y documentación operativa. Esta revisión modifica solo
documentación/OpenSpec en el repositorio; prevé Node 22+ host para el wrapper de
operación, no en API, sin autorizar su instalación. Los diagnósticos históricos Q4/Q5 usan scripts temporales
e imágenes desechables fuera del producto. No añade dependencias ni código de
producto, SQL entregable, credenciales, programaciones, migraciones o datos reales.

Autoridad: [PRD](../../../docs/open-gym-evolution.prd.md),
[arquitectura](../../../docs/open-gym-evolution.architecture.md),
[esquema](../../../docs/reference/platform-schema.md),
[seguridad](../../../docs/reference/platform-security.md),
[operación](../../../docs/reference/platform-operations.md) y
[modularidad](../../../docs/reference/platform-modularity.md).
Foundation está completada en [su cambio archivado](../archive/2026-10-25-add-python-platform-foundation/proposal.md).
Contribución esperada EV-01–EV-09 y G0/G1 operativo/GP/GO/G2/G3, todos sin acreditar
por esta especificación. Recovery solo comienza después del cierre de plataforma.
