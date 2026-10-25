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
- Entregar imágenes/ambientes locales separados, diagnóstico privado, backup y
  restauración coordinados; ensayar corte, autoridad única y retirada posterior.
- Aplicar las decisiones confirmadas: revisión manual verificable por acceso tras
  restore y reparación hacia adelante tras nuevas escrituras; sin ledger nuevo ni
  exportador inverso a Node salvo aprobación expresa.
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
el [plan ejecutable](execution-plan.md) concreta S1–S11 con 57 tareas, casos/seams,
comandos futuros y checkpoints. DDL/funciones, cotas/herramientas de diagnóstico y
procedimientos de recuperación están especificados en sus referencias propietarias;
la revisión semántica de readiness es distinta de validar Markdown. Inventario real, acceso a datos, ejecución del corte o borrado requieren
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
documentación/OpenSpec en el repositorio; los diagnósticos Q4/Q5 usan scripts temporales
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
